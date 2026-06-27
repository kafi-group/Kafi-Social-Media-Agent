"""
API Routes - Designer Approval Workflow (QA Checker)

GET  /approvals/config            - public config for the frontend gate
POST /designer/verify-pin         - validate the designer PIN
POST /approvals                   - submit a post for approval (non-designer)
GET  /approvals                   - list approval requests (queue + history)
GET  /approvals/{id}              - approval request detail
POST /approvals/{id}/approve      - approve & publish (requires PIN)
POST /approvals/{id}/reject       - reject (requires PIN)

Security:
  - PIN verification is rate-limited (5 attempts / minute per IP) and has an
    in-memory lockout (configurable via PIN_MAX_ATTEMPTS / PIN_LOCKOUT_MINUTES).
  - All route-level error detail strings avoid leaking internal state.
"""

import secrets
import threading
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import ApprovalRequest, ApprovalStatus, Content
from app.dependencies import get_db
from app.middleware.rate_limiter import limiter
from app.schemas.approval import (
    ApprovalConfigResponse,
    ApprovalCreateRequest,
    ApprovalResponse,
    PinRequest,
    PinVerifyResponse,
    RejectRequest,
)
from app.services import approval_service
from app.services.approval_service import ApprovalError
from app.services.media import MediaService
from app.utils.logger import logger
from app.utils.sanitize import safe_error_detail

router = APIRouter()
media_service = MediaService()

# ── PIN brute-force protection ─────────────────────────────────────────────────
# Tracks failed PIN attempts per IP address.  Uses a threading.Lock so it is
# safe when uvicorn runs with multiple threads (sync request handlers).
_pin_failures: dict[str, list[datetime]] = {}
_pin_lock = threading.Lock()


def _is_pin_locked(ip: str) -> bool:
    """Return True when the IP has exceeded the allowed failure count."""
    window = timedelta(minutes=settings.PIN_LOCKOUT_MINUTES)
    with _pin_lock:
        attempts = _pin_failures.get(ip, [])
        now = datetime.utcnow()
        recent = [t for t in attempts if now - t < window]
        _pin_failures[ip] = recent          # prune stale entries
        return len(recent) >= settings.PIN_MAX_ATTEMPTS


def _record_pin_failure(ip: str) -> None:
    with _pin_lock:
        _pin_failures.setdefault(ip, []).append(datetime.utcnow())


def _clear_pin_failures(ip: str) -> None:
    with _pin_lock:
        _pin_failures.pop(ip, None)


def verify_pin(pin: str) -> bool:
    """Constant-time compare against the configured designer PIN."""
    if not settings.DESIGNER_PIN:
        return False
    return secrets.compare_digest(str(pin), str(settings.DESIGNER_PIN))


def _public_media_url(media_path: Optional[str]) -> Optional[str]:
    if not media_path:
        return None
    try:
        return media_service.get_public_url(media_path)
    except Exception as e:
        logger.warning(f"Could not resolve media URL for {media_path}: {e}")
        return None


def _to_response(approval: ApprovalRequest, db: Session) -> ApprovalResponse:
    """Merge an approval row with a snapshot of its content for the review UI."""
    content = db.query(Content).filter(Content.id == approval.content_id).first()
    return ApprovalResponse(
        id=approval.id,
        content_id=approval.content_id,
        status=approval.status.value if approval.status else "pending",
        platforms=approval.platforms,
        draft_mode=bool(approval.draft_mode),
        override_title=approval.override_title,
        override_body=approval.override_body,
        linkedin_account_labels=approval.linkedin_account_labels,
        requested_by=approval.requested_by,
        reviewer_note=approval.reviewer_note,
        results=approval.results,
        decided_at=approval.decided_at,
        created_at=approval.created_at,
        title=approval.override_title or (content.title if content else None),
        body=approval.override_body or (content.body if content else None),
        media_path=content.media_path if content else None,
        media_type=(content.media_type.value if content and content.media_type else None),
        media_url=_public_media_url(content.media_path) if content else None,
        platform=(content.platform.value if content and content.platform else None),
    )


@router.get("/approvals/stats")
def get_approval_stats(db: Session = Depends(get_db)):
    """
    Return approval counts used for the dashboard QA Pass Rate stat.
    pass_rate = approved / (approved + rejected) * 100, or null when no decisions yet.
    """
    row = db.query(
        func.count(ApprovalRequest.id).label("total"),
        func.sum(case((ApprovalRequest.status == ApprovalStatus.PENDING, 1), else_=0)).label("pending"),
        func.sum(case((ApprovalRequest.status == ApprovalStatus.APPROVED, 1), else_=0)).label("approved"),
        func.sum(case((ApprovalRequest.status == ApprovalStatus.REJECTED, 1), else_=0)).label("rejected"),
    ).one()

    total = int(row.total or 0)
    pending = int(row.pending or 0)
    approved = int(row.approved or 0)
    rejected = int(row.rejected or 0)
    decided = approved + rejected
    pass_rate = round(approved / decided * 100) if decided > 0 else None
    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "pass_rate": pass_rate,  # null = no decisions made yet
    }


@router.get("/approvals/config", response_model=ApprovalConfigResponse)
async def get_approval_config():
    """Public config the frontend uses to decide whether to show the gate."""
    return ApprovalConfigResponse(approval_required=settings.APPROVAL_REQUIRED)


@router.post("/designer/verify-pin", response_model=PinVerifyResponse)
@limiter.limit("5/minute")
async def verify_designer_pin(request: Request, body: PinRequest):
    """
    Validate the designer PIN.

    Rate-limited to 5 attempts per minute per IP.
    After PIN_MAX_ATTEMPTS failures within PIN_LOCKOUT_MINUTES the IP is
    locked out and receives a 429 regardless of the supplied PIN.
    """
    client_ip = request.client.host if request.client else "unknown"

    if _is_pin_locked(client_ip):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many failed PIN attempts. "
                f"Try again in {settings.PIN_LOCKOUT_MINUTES} minutes."
            ),
        )

    valid = verify_pin(body.pin)

    if valid:
        _clear_pin_failures(client_ip)
    else:
        _record_pin_failure(client_ip)

    return PinVerifyResponse(valid=valid)


@router.post("/approvals", response_model=ApprovalResponse)
@limiter.limit("10/minute")
async def create_approval(
    request: Request,
    body: ApprovalCreateRequest,
    db: Session = Depends(get_db),
):
    """Submit a post for designer approval via the QA Checker queue."""
    try:
        approval = approval_service.create_request(
            db,
            content_id=body.content_id,
            platforms=body.platforms,
            draft_mode=body.draft_mode,
            override_title=body.override_title,
            override_body=body.override_body,
            linkedin_account_labels=body.linkedin_account_labels,
            requested_by=body.requested_by,
        )
        return _to_response(approval, db)
    except ApprovalError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Create approval error: {e}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e, "Failed to submit for approval"))


@router.get("/approvals", response_model=list[ApprovalResponse])
async def list_approvals(
    status: str = Query(None, description="Filter: pending, approved, rejected"),
    db: Session = Depends(get_db),
):
    """List approval requests for the QA queue and history."""
    query = db.query(ApprovalRequest)
    if status:
        try:
            query = query.filter(ApprovalRequest.status == ApprovalStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    approvals = query.order_by(ApprovalRequest.created_at.desc()).all()
    return [_to_response(a, db) for a in approvals]


@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
async def get_approval(approval_id: int, db: Session = Depends(get_db)):
    """Get a single approval request."""
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    return _to_response(approval, db)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
@limiter.limit("10/minute")
async def approve_request(
    request: Request,
    approval_id: int,
    body: PinRequest,
    db: Session = Depends(get_db),
):
    """Approve a request and publish (requires the designer PIN)."""
    client_ip = request.client.host if request.client else "unknown"

    if _is_pin_locked(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed PIN attempts. Try again in {settings.PIN_LOCKOUT_MINUTES} minutes.",
        )

    if not verify_pin(body.pin):
        _record_pin_failure(client_ip)
        raise HTTPException(status_code=403, detail="Invalid designer PIN")

    _clear_pin_failures(client_ip)

    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    try:
        approval_service.approve(db, approval)
        return _to_response(approval, db)
    except ApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Approve error: {e}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e, "Failed to approve request"))


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
@limiter.limit("10/minute")
async def reject_request(
    request: Request,
    approval_id: int,
    body: RejectRequest,
    db: Session = Depends(get_db),
):
    """Reject a request (requires the designer PIN)."""
    client_ip = request.client.host if request.client else "unknown"

    if _is_pin_locked(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed PIN attempts. Try again in {settings.PIN_LOCKOUT_MINUTES} minutes.",
        )

    if not verify_pin(body.pin):
        _record_pin_failure(client_ip)
        raise HTTPException(status_code=403, detail="Invalid designer PIN")

    _clear_pin_failures(client_ip)

    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    try:
        approval_service.reject(db, approval, note=body.note)
        return _to_response(approval, db)
    except ApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Reject error: {e}")
        raise HTTPException(status_code=500, detail=safe_error_detail(e, "Failed to reject request"))
