"""
Approval Service
Designer-approval workflow: create requests, approve (publish), reject.

When a non-designer posts, an ApprovalRequest is created and the designer is
emailed. On approval the stored posting config is published verbatim via the
shared publish_content() so it behaves identically to a normal post.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import (
    ApprovalRequest,
    ApprovalStatus,
    Content,
    ContentStatus,
)
from app.services import email_service
from app.services.publishing import publish_content
from app.utils.logger import logger

DEFAULT_REJECT_NOTE = "Rejected by the designer"


class ApprovalError(Exception):
    """Raised for invalid approval operations."""


def create_request(
    db: Session,
    *,
    content_id: int,
    platforms: list[str],
    draft_mode: bool = False,
    override_title: Optional[str] = None,
    override_body: Optional[str] = None,
    linkedin_account_labels: Optional[list[str]] = None,
    requested_by: Optional[str] = None,
) -> ApprovalRequest:
    """Create a pending approval request and email the designer."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ApprovalError(f"Content {content_id} not found")

    token_expires = datetime.utcnow() + timedelta(
        hours=settings.APPROVAL_TOKEN_EXPIRE_HOURS
    )
    approval = ApprovalRequest(
        content_id=content_id,
        status=ApprovalStatus.PENDING,
        platforms=platforms,
        draft_mode=draft_mode,
        override_title=override_title,
        override_body=override_body,
        linkedin_account_labels=linkedin_account_labels,
        requested_by=requested_by,
        review_token=secrets.token_urlsafe(32),
        review_token_expires_at=token_expires,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)

    # Email is best-effort; the request still lives in the in-app queue.
    try:
        email_service.send_approval_request(
            token=approval.review_token,
            title=override_title or content.title,
            body=override_body or content.body,
            platforms=platforms or [],
            media_path=content.media_path,
            media_type=content.media_type.value if content.media_type else None,
            requested_by=requested_by,
        )
    except Exception as e:
        logger.error(f"Approval email send failed for request {approval.id}: {e}")

    return approval


def approve(db: Session, approval: ApprovalRequest) -> list[dict]:
    """Approve a pending request and publish the post. Returns publish results."""
    if approval.status != ApprovalStatus.PENDING:
        raise ApprovalError(f"Request already {approval.status.value}")

    results = publish_content(
        db=db,
        content_id=approval.content_id,
        platforms=approval.platforms or [],
        draft_mode=bool(approval.draft_mode),
        override_title=approval.override_title,
        override_body=approval.override_body,
        linkedin_account_labels=approval.linkedin_account_labels,
    )

    approval.status = ApprovalStatus.APPROVED
    approval.decided_at = datetime.utcnow()
    approval.results = results

    content = db.query(Content).filter(Content.id == approval.content_id).first()
    if content:
        content.status = ContentStatus.APPROVED

    db.commit()
    db.refresh(approval)
    logger.info(f"Approval {approval.id} approved and published")
    return results


def reject(db: Session, approval: ApprovalRequest, note: Optional[str] = None) -> ApprovalRequest:
    """Reject a pending request; the post is not published."""
    if approval.status != ApprovalStatus.PENDING:
        raise ApprovalError(f"Request already {approval.status.value}")

    approval.status = ApprovalStatus.REJECTED
    approval.reviewer_note = note.strip() if note and note.strip() else DEFAULT_REJECT_NOTE
    approval.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(approval)
    logger.info(f"Approval {approval.id} rejected")
    return approval
