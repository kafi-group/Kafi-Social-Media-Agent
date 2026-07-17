"""
Background Post Scheduler

Polls the calendar_event table on a fixed interval and auto-publishes any
event whose scheduled time has arrived. Reuses the exact same publishing
pipeline as the manual "post now" flow, so scheduled posts behave identically
across LinkedIn, Facebook, Instagram, and YouTube.

Design notes:
- A single APScheduler BackgroundScheduler runs one interval job.
- Each tick opens its own DB session, claims due events by flipping them to
  'publishing', then posts them. Because we only ever select 'pending' rows,
  an event can't be picked up twice.
- Times are compared in UTC (scheduled_date is stored in UTC).
"""

import threading
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database.db import SessionLocal
from app.database.models import (
    CalendarEvent,
    Content,
    ContentStatus,
    ScheduleStatus,
)
from app.services.calendar import CalendarService
from app.services.publishing import publish_content, summarize_statuses
from app.utils.logger import logger

_scheduler: Optional[BackgroundScheduler] = None

# An event 'publishing' longer than this is considered orphaned (e.g. the server
# restarted mid-publish, or a publish was interrupted). It is marked 'failed'
# rather than auto-retried, because an interrupted publish may have already
# posted to some platforms — re-running it could create real duplicates on
# networks that don't dedupe (Facebook/Instagram). The user can review and use
# "Publish now" to deliberately republish.
RECLAIM_STALE_MINUTES = 15


def reclaim_stuck_events(db, stale_minutes: Optional[int] = None) -> int:
    """
    Mark events orphaned in the 'publishing' state as 'failed' so they don't
    stay stuck forever, while avoiding accidental double-posting on retry.

    Args:
        db: active DB session
        stale_minutes: if None, reclaims ALL 'publishing' events (used on
            startup, where nothing can legitimately be in-flight). Otherwise
            only reclaims events not touched within the given window.

    Returns:
        Number of events reclaimed.
    """
    query = db.query(CalendarEvent).filter(
        CalendarEvent.status == ScheduleStatus.PUBLISHING.value
    )
    if stale_minutes is not None:
        cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)
        query = query.filter(CalendarEvent.updated_at <= cutoff)

    stuck = query.all()
    for ev in stuck:
        ev.status = ScheduleStatus.FAILED.value
        ev.error_message = (
            "Publishing was interrupted (server restart or timeout). It may have "
            "partially posted — review the post, then use 'Publish now' to retry."
        )
        ev.updated_at = datetime.utcnow()

    if stuck:
        db.commit()
        logger.warning(
            f"Reclaimed {len(stuck)} stuck 'publishing' event(s) -> failed "
            f"(needs manual review)"
        )
    return len(stuck)


def _overall_to_content_status(overall: str) -> ContentStatus:
    """Map an overall publish result to the Content lifecycle status."""
    if overall == "published":
        return ContentStatus.PUBLISHED
    if overall == "draft":
        # Simulated post — leave it marked as scheduled/generated rather than live
        return ContentStatus.SCHEDULED
    if overall == "partial":
        return ContentStatus.PUBLISHED
    return ContentStatus.SCHEDULED


def publish_event(db, event: CalendarEvent) -> str:
    """
    Publish a single calendar event now and record the outcome on the event.
    Returns the overall status string. Safe to call from the worker or an API.
    """
    event.status = ScheduleStatus.PUBLISHING.value
    event.updated_at = datetime.utcnow()
    db.commit()

    platforms = event.platforms or []
    if not platforms:
        event.status = ScheduleStatus.FAILED.value
        event.error_message = "No platforms configured for this scheduled event"
        db.commit()
        return ScheduleStatus.FAILED.value

    try:
        results = publish_content(
            db=db,
            content_id=event.content_id,
            platforms=platforms,
            draft_mode=bool(event.draft_mode),
            override_title=event.override_title,
            override_body=event.override_body,
            linkedin_account_labels=event.linkedin_account_labels,
        )

        overall = summarize_statuses(results)

        if overall in ("published", "draft"):
            event.status = ScheduleStatus.PUBLISHED.value
            event.error_message = None
        elif overall == "partial":
            event.status = ScheduleStatus.PARTIAL.value
            event.error_message = "Some platforms failed to publish"
        else:
            event.status = ScheduleStatus.FAILED.value
            errors = [r.get("error_message") for r in results if r.get("error_message")]
            event.error_message = "; ".join(e for e in errors if e) or "Publishing failed"

        event.results = results
        event.published_at = datetime.utcnow()
        event.updated_at = datetime.utcnow()

        # Update the underlying content lifecycle status
        content = db.query(Content).filter(Content.id == event.content_id).first()
        if content:
            content.status = _overall_to_content_status(overall)
            content.updated_at = datetime.utcnow()

        db.commit()
        logger.info(
            f"Published scheduled event {event.id} (content {event.content_id}) "
            f"-> {event.status}"
        )
        return event.status

    except Exception as e:
        logger.error(f"Failed to publish scheduled event {event.id}: {e}")
        try:
            event.status = ScheduleStatus.FAILED.value
            event.error_message = str(e)
            event.updated_at = datetime.utcnow()
            db.commit()
        except Exception:
            db.rollback()
        return ScheduleStatus.FAILED.value


def refresh_rivals_job() -> None:
    """Background tick: refresh competitor analytics snapshots (Rival Review)."""
    from app.services.rival_service import RivalService

    db = SessionLocal()
    try:
        service = RivalService(db)
        if not service.list_rivals():
            service.seed_defaults()
        results = service.refresh_all()
        logger.info(f"Rival auto-refresh complete: {len(results)} rival(s)")
    except Exception as e:
        logger.error(f"Rival auto-refresh failed: {e}")
    finally:
        db.close()


def refresh_meta_tokens_job() -> None:
    """Extend Meta long-lived user token and re-derive the Page token."""
    from app.services.meta_token_service import refresh_meta_tokens

    try:
        result = refresh_meta_tokens(force=False)
        status = result.get("status", "unknown")
        if status in ("refreshed", "ok", "skipped"):
            logger.info(f"Meta token maintenance: {status} — {result.get('reason', '')}")
        else:
            logger.warning(f"Meta token maintenance: {status} — {result}")
    except Exception as e:
        logger.error(f"Meta token maintenance failed: {e}")


def publish_due_events() -> None:
    """One scheduler tick: find and publish all events that are due."""
    db = SessionLocal()
    try:
        # Recover any events orphaned in 'publishing' beyond the stale window
        reclaim_stuck_events(db, stale_minutes=RECLAIM_STALE_MINUTES)

        service = CalendarService(db)
        due = service.get_due_events()
        if not due:
            return
        logger.info(f"Scheduler: {len(due)} due event(s) to publish")
        for event in due:
            publish_event(db, event)
    except Exception as e:
        logger.error(f"Scheduler tick failed: {e}")
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the background scheduler (called on app startup)."""
    global _scheduler

    if not settings.SCHEDULER_ENABLED:
        logger.info("Post scheduler is disabled (SCHEDULER_ENABLED=false)")
        return

    if _scheduler and _scheduler.running:
        return

    # Reclaim orphaned 'publishing' rows in the background so API startup is not
    # blocked waiting on a slow/unreachable database.
    def _startup_reclaim() -> None:
        db = SessionLocal()
        try:
            reclaim_stuck_events(db, stale_minutes=None)
        except Exception as e:
            logger.error(f"Startup reclaim failed: {e}")
        finally:
            db.close()

    threading.Thread(target=_startup_reclaim, name="scheduler-startup-reclaim", daemon=True).start()

    interval = max(5, settings.SCHEDULER_POLL_INTERVAL_SECONDS)
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        publish_due_events,
        trigger="interval",
        seconds=interval,
        id="publish_due_events",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    # Optional: periodically refresh competitor analytics for Rival Review.
    if settings.RIVAL_AUTO_REFRESH:
        rival_interval = max(300, settings.SCRAPER_SCHEDULE_INTERVAL)
        _scheduler.add_job(
            refresh_rivals_job,
            trigger="interval",
            seconds=rival_interval,
            id="refresh_rivals",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        logger.info(f"Rival auto-refresh enabled (every {rival_interval}s)")

    # Keep Facebook / Instagram Page tokens renewable without manual re-auth.
    meta_interval = max(3600, int(settings.META_TOKEN_REFRESH_INTERVAL_SECONDS or 86400))
    _scheduler.add_job(
        refresh_meta_tokens_job,
        trigger="interval",
        seconds=meta_interval,
        id="refresh_meta_tokens",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info(f"Meta token auto-refresh enabled (every {meta_interval}s)")

    _scheduler.start()
    logger.info(f"Post scheduler started (polling every {interval}s)")


def shutdown_scheduler() -> None:
    """Stop the background scheduler (called on app shutdown)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Post scheduler stopped")
    _scheduler = None
