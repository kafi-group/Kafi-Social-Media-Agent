"""
Rival Review service.

Owns competitor CRUD, on-demand analytics refresh (writes a RivalSnapshot per
platform), snapshot history for trend charts, and seeding of a curated default
list of top Pakistani spice/rice/chutney exporters. The default list is editable
from the UI - it's only used to bootstrap an empty table.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.database.models import Rival, RivalSnapshot
from app.services import rival_collectors
from app.utils.logger import logger

# Curated, editable defaults (researched top Pakistani exporters). Handles/usernames
# are best-effort starting points; users can correct them in the UI.
DEFAULT_RIVALS = [
    {
        "name": "Shan Foods",
        "category": "spice",
        "website": "https://www.shanfoods.com",
        "youtube_handle": "@ShanFoodsGlobal",
        "instagram_username": "shanfoodsglobal",
    },
    {
        "name": "National Foods",
        "category": "spice",
        "website": "https://www.nfoods.com",
        "youtube_handle": "@nationalfoodgroup",
        "instagram_username": "nationalfoodspakistan",
    },
    {
        "name": "Mehran Foods",
        "category": "spice",
        "website": "https://mehrangroup.com",
        "youtube_handle": "@mehranfoods9995",
        "instagram_username": "mehranfoodsofficial",
    },
    {
        "name": "Ahmed Foods",
        "category": "spice",
        "website": "https://ahmedfood.com",
        "youtube_handle": "@AHMEDFOODSOFFICIAL",
        "instagram_username": "ahmedfoodsofficial",
    },
    {
        "name": "Matco Foods (Falak)",
        "category": "rice",
        "website": "https://matcofoods.com",
        "youtube_handle": "@matcofoods8903",
        "instagram_username": "matcofoods",
    },
    {
        "name": "Guard Rice",
        "category": "rice",
        "website": "https://guardagri.com",
        "youtube_handle": "@GuardRiceBasmati",
        "instagram_username": "guard_rice",
    },
    {
        "name": "Galaxy Rice",
        "category": "rice",
        "website": "https://galaxyrice.com",
        "youtube_handle": "@GalaxyRiceMill",
        "instagram_username": "galaxybasmatirice",
    },
]


def serialize_snapshot(snapshot: RivalSnapshot) -> dict:
    return {
        "id": snapshot.id,
        "platform": snapshot.platform,
        "status": snapshot.status,
        "metrics": snapshot.metrics or {},
        "recent_items": snapshot.recent_items or [],
        "message": snapshot.message,
        "captured_at": snapshot.captured_at.isoformat() if snapshot.captured_at else None,
    }


class RivalService:
    """Business logic for the Rival Review feature."""

    def __init__(self, db: Session):
        self.db = db

    # ---- CRUD -------------------------------------------------------------

    def list_rivals(self, active_only: bool = False) -> list[Rival]:
        query = self.db.query(Rival)
        if active_only:
            query = query.filter(Rival.is_active.is_(True))
        return query.order_by(Rival.name.asc()).all()

    def get_rival(self, rival_id: int) -> Optional[Rival]:
        return self.db.query(Rival).filter(Rival.id == rival_id).first()

    def create_rival(self, data: dict) -> Rival:
        rival = Rival(**data)
        self.db.add(rival)
        self.db.commit()
        self.db.refresh(rival)
        return rival

    def update_rival(self, rival_id: int, data: dict) -> Optional[Rival]:
        rival = self.get_rival(rival_id)
        if not rival:
            return None
        for key, value in data.items():
            setattr(rival, key, value)
        rival.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(rival)
        return rival

    def delete_rival(self, rival_id: int) -> bool:
        rival = self.get_rival(rival_id)
        if not rival:
            return False
        self.db.delete(rival)
        self.db.commit()
        return True

    # ---- Snapshots / refresh ---------------------------------------------

    def refresh_rival(self, rival_id: int) -> Optional[dict]:
        """Run all collectors for a rival and persist one snapshot per platform."""
        rival = self.get_rival(rival_id)
        if not rival:
            return None

        results = rival_collectors.collect_all(rival)
        for result in results:
            self.db.add(RivalSnapshot(
                rival_id=rival.id,
                platform=result["platform"],
                status=result["status"],
                metrics=result["metrics"],
                recent_items=result["recent_items"],
                message=result.get("message"),
            ))
        self.db.commit()
        logger.info(f"Refreshed rival '{rival.name}' (id={rival.id})")
        return self.rival_with_latest(rival)

    def refresh_all(self, *, active_only: bool = False) -> list[dict]:
        rivals = self.list_rivals(active_only=active_only)
        out = []
        for rival in rivals:
            try:
                refreshed = self.refresh_rival(rival.id)
                if refreshed:
                    out.append(refreshed)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to refresh rival {rival.id}: {exc}")
        return out

    def needs_auto_refresh(self, rival: Rival) -> bool:
        """
        True when cached snapshots are missing or YouTube/Instagram stats are
        stale/empty but we can now collect them (e.g. after OAuth was fixed).
        """
        latest = self.latest_snapshots(rival.id)
        if not latest:
            return True

        has_yt_target = bool(
            (rival.youtube_channel_id or "").strip() or (rival.youtube_handle or "").strip()
        )
        if has_yt_target and rival_collectors.youtube_is_configured():
            yt = latest.get("youtube")
            if yt is None:
                return True
            metrics = yt.metrics or {}
            has_views = bool(metrics.get("total_views"))
            has_subs = bool(metrics.get("subscribers"))
            if yt.status != "ok" or (not has_views and not has_subs):
                return True

        has_ig_target = bool((rival.instagram_username or "").strip())
        if has_ig_target and rival_collectors.instagram_is_configured():
            ig = latest.get("instagram")
            if ig is None:
                return True
            metrics = ig.metrics or {}
            if ig.status != "ok" or not metrics.get("followers"):
                return True

        return False

    @staticmethod
    def refresh_rival_isolated(rival_id: int) -> None:
        """Refresh one rival using its own DB session (safe for thread pool)."""
        db = SessionLocal()
        try:
            RivalService(db).refresh_rival(rival_id)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Auto-refresh rival {rival_id} failed: {exc}")
        finally:
            db.close()

    def auto_refresh_stale(self, rivals: list[Rival], *, max_workers: int = 4) -> int:
        """Refresh rivals with missing/stale YouTube snapshots. Returns count refreshed."""
        stale_ids = [r.id for r in rivals if self.needs_auto_refresh(r)]
        if not stale_ids:
            return 0

        workers = min(max_workers, len(stale_ids))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(self.refresh_rival_isolated, stale_ids))

        logger.info(f"Auto-refreshed {len(stale_ids)} rival(s) with stale analytics data")
        return len(stale_ids)

    def latest_snapshots(self, rival_id: int) -> dict[str, RivalSnapshot]:
        """Map of platform -> most recent snapshot for that platform."""
        snapshots = (
            self.db.query(RivalSnapshot)
            .filter(RivalSnapshot.rival_id == rival_id)
            .order_by(RivalSnapshot.captured_at.desc())
            .all()
        )
        latest: dict[str, RivalSnapshot] = {}
        for snap in snapshots:
            latest.setdefault(snap.platform, snap)
        return latest

    def list_snapshots(
        self, rival_id: int, platform: Optional[str] = None, limit: int = 60
    ) -> list[RivalSnapshot]:
        query = self.db.query(RivalSnapshot).filter(RivalSnapshot.rival_id == rival_id)
        if platform:
            query = query.filter(RivalSnapshot.platform == platform)
        return query.order_by(RivalSnapshot.captured_at.desc()).limit(limit).all()

    # ---- Serialization ----------------------------------------------------

    def rival_with_latest(self, rival: Rival) -> dict:
        """A rival enriched with its latest snapshot per platform (for the UI)."""
        latest = self.latest_snapshots(rival.id)
        captured = [s.captured_at for s in latest.values() if s.captured_at]
        return {
            "id": rival.id,
            "name": rival.name,
            "category": rival.category,
            "website": rival.website,
            "youtube_channel_id": rival.youtube_channel_id,
            "youtube_handle": rival.youtube_handle,
            "instagram_username": rival.instagram_username,
            "rss_url": rival.rss_url,
            "notes": rival.notes,
            "is_active": rival.is_active,
            "created_at": rival.created_at.isoformat() if rival.created_at else None,
            "updated_at": rival.updated_at.isoformat() if rival.updated_at else None,
            "platforms": {p: serialize_snapshot(s) for p, s in latest.items()},
            "last_refreshed_at": max(captured).isoformat() if captured else None,
        }

    # ---- Seeding ----------------------------------------------------------

    def seed_defaults(self) -> int:
        """Insert the curated default rivals that aren't already present."""
        existing = {r.name.lower() for r in self.list_rivals()}
        added = 0
        for data in DEFAULT_RIVALS:
            if data["name"].lower() in existing:
                continue
            self.db.add(Rival(**data))
            added += 1
        if added:
            self.db.commit()
            logger.info(f"Seeded {added} default rival(s)")
        return added
