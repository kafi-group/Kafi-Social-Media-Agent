"""
Pydantic Schemas - Designer Approval Workflow DTOs
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApprovalCreateRequest(BaseModel):
    """Request to submit a post for designer approval."""

    content_id: int = Field(..., description="ID of the content to submit")
    platforms: list[str] = Field(..., description="Platforms to publish on approval")
    draft_mode: bool = Field(default=False)
    override_title: Optional[str] = Field(default=None)
    override_body: Optional[str] = Field(default=None)
    linkedin_account_labels: Optional[list[str]] = Field(default=None)
    requested_by: Optional[str] = Field(default=None, description="Submitter name")


class PinRequest(BaseModel):
    """A request carrying the designer PIN."""

    pin: str = Field(..., description="Designer PIN")


class RejectRequest(PinRequest):
    """Reject a request with the designer PIN and an optional reason."""

    note: Optional[str] = Field(default=None, description="Rejection reason")


class ApprovalResponse(BaseModel):
    """A designer approval request."""

    id: int
    content_id: int
    status: str
    platforms: Optional[list[str]] = None
    draft_mode: bool = False
    override_title: Optional[str] = None
    override_body: Optional[str] = None
    linkedin_account_labels: Optional[list[str]] = None
    requested_by: Optional[str] = None
    reviewer_note: Optional[str] = None
    results: Optional[list[dict]] = None
    decided_at: Optional[datetime] = None
    created_at: datetime

    # Snapshot of the content for the review UI
    title: Optional[str] = None
    body: Optional[str] = None
    media_path: Optional[str] = None
    media_type: Optional[str] = None
    media_url: Optional[str] = None
    platform: Optional[str] = None

    class Config:
        from_attributes = True


class ApprovalConfigResponse(BaseModel):
    """Public approval config used by the frontend gate."""

    approval_required: bool


class PinVerifyResponse(BaseModel):
    valid: bool
