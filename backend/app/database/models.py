"""
SQLAlchemy ORM Models
Core database schema definitions
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database.db import Base


class ContentPlatform(str, PyEnum):
    """Supported social media platforms."""

    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
    FACEBOOK = "facebook"
    YOUTUBE = "youtube"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"


class ContentStatus(str, PyEnum):
    """Content generation status."""

    DRAFT = "draft"
    GENERATED = "generated"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class QAStatus(str, PyEnum):
    """QA check status."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    REVIEW = "review"


class MediaType(str, PyEnum):
    """Supported media types for upload."""

    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"


class PostStatus(str, PyEnum):
    """Social media post status."""

    PENDING = "pending"
    POSTING = "posting"
    PUBLISHED = "published"
    PARTIAL = "partial"
    FAILED = "failed"


class Content(Base):
    """Content generation records."""

    __tablename__ = "content"

    id = Column(Integer, primary_key=True)
    platform = Column(Enum(ContentPlatform), nullable=False)
    status = Column(Enum(ContentStatus), default=ContentStatus.DRAFT)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    meta_data = Column(JSON, nullable=True)  # Additional data (hashtags, keywords, etc.)

    # Media attachment (uploaded by graphic designer)
    media_path = Column(String(500), nullable=True)  # Local file path
    media_type = Column(Enum(MediaType), nullable=True)  # image/video/document
    media_original_name = Column(String(255), nullable=True)  # Original filename

    # Social posting status (per platform)
    linkedin_post_id = Column(String(255), nullable=True)
    linkedin_post_status = Column(Enum(PostStatus), default=PostStatus.PENDING)
    linkedin_accounts_results = Column(JSON, nullable=True)
    facebook_post_id = Column(String(255), nullable=True)
    facebook_post_status = Column(Enum(PostStatus), default=PostStatus.PENDING)
    instagram_post_id = Column(String(255), nullable=True)
    instagram_post_status = Column(Enum(PostStatus), default=PostStatus.PENDING)
    youtube_post_id = Column(String(255), nullable=True)
    youtube_post_status = Column(Enum(PostStatus), default=PostStatus.PENDING)

    generated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), default="system")

    # Relationships
    qa_reports = relationship("QAReport", back_populates="content", cascade="all, delete-orphan")
    calendar_events = relationship("CalendarEvent", back_populates="content")


class ScheduleStatus(str, PyEnum):
    """Lifecycle of a scheduled calendar event."""

    PENDING = "pending"        # waiting for its scheduled time
    PUBLISHING = "publishing"  # picked up by the worker, posting in progress
    PUBLISHED = "published"    # successfully posted to all platforms
    PARTIAL = "partial"        # posted to some platforms, failed on others
    FAILED = "failed"          # posting failed
    CANCELLED = "cancelled"    # cancelled by the user before publishing


class CalendarEvent(Base):
    """
    Content calendar scheduling.

    Each row represents a piece of Content scheduled to be auto-published to one
    or more social platforms at `scheduled_date` (stored in UTC). A background
    worker polls for due events and publishes them.
    """

    __tablename__ = "calendar_event"

    id = Column(Integer, primary_key=True)
    content_id = Column(Integer, ForeignKey("content.id"), nullable=False)
    scheduled_date = Column(DateTime, nullable=False)  # UTC datetime to publish
    scheduled_time = Column(String(10), nullable=True)  # legacy HH:MM (optional)
    status = Column(String(50), default=ScheduleStatus.PENDING.value)
    notes = Column(Text, nullable=True)

    # Posting configuration captured at schedule time
    platforms = Column(JSON, nullable=True)  # ["linkedin", "facebook", "instagram"]
    draft_mode = Column(Boolean, default=False)
    override_title = Column(Text, nullable=True)
    override_body = Column(Text, nullable=True)
    linkedin_account_labels = Column(JSON, nullable=True)  # optional subset of LI accounts

    # Execution results (filled in by the worker)
    published_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    results = Column(JSON, nullable=True)  # per-platform posting results

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    content = relationship("Content", back_populates="calendar_events")


class QAReport(Base):
    """QA/Compliance check results."""

    __tablename__ = "qa_report"

    id = Column(Integer, primary_key=True)
    content_id = Column(Integer, ForeignKey("content.id"), nullable=False)
    status = Column(Enum(QAStatus), default=QAStatus.PENDING)
    score = Column(Float, default=0.0)  # 0-100
    issues = Column(JSON, nullable=True)  # List of issues found
    recommendations = Column(JSON, nullable=True)  # List of recommendations
    checked_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    content = relationship("Content", back_populates="qa_reports")


class ApprovalStatus(str, PyEnum):
    """Designer approval request status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(Base):
    """
    A request for a designer to approve a post before it is published.

    Created when a non-designer tries to post. Stores the exact posting
    configuration so the post can be published verbatim once approved.
    """

    __tablename__ = "approval_request"

    id = Column(Integer, primary_key=True)
    content_id = Column(Integer, ForeignKey("content.id"), nullable=False)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)

    # Posting configuration captured at submit time
    platforms = Column(JSON, nullable=True)  # ["linkedin", "facebook", ...]
    draft_mode = Column(Boolean, default=False)
    override_title = Column(Text, nullable=True)
    override_body = Column(Text, nullable=True)
    linkedin_account_labels = Column(JSON, nullable=True)

    requested_by = Column(String(100), nullable=True)  # submitter name (optional)
    review_token = Column(String(64), unique=True, nullable=False)  # email magic link
    review_token_expires_at = Column(DateTime, nullable=True)  # token TTL (48 h default)
    reviewer_note = Column(Text, nullable=True)  # rejection reason / approval note
    results = Column(JSON, nullable=True)  # per-platform publish results on approval

    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    content = relationship("Content")


class ScraperLog(Base):
    """Scraper execution logs."""

    __tablename__ = "scraper_log"

    id = Column(Integer, primary_key=True)
    scraper_name = Column(String(100), nullable=False)
    status = Column(String(50), default="running")  # running, completed, failed
    records_fetched = Column(Integer, default=0)
    records_saved = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    meta_data = Column(JSON, nullable=True)


class Rival(Base):
    """A tracked competitor of Kafi Commodities (Rival Review)."""

    __tablename__ = "rival"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    category = Column(String(50), nullable=True)  # spice, rice, chutney, mixed
    website = Column(String(500), nullable=True)
    youtube_channel_id = Column(String(100), nullable=True)
    youtube_handle = Column(String(100), nullable=True)  # e.g. @ShanFoodsGlobal
    instagram_username = Column(String(100), nullable=True)
    rss_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    snapshots = relationship(
        "RivalSnapshot", back_populates="rival", cascade="all, delete-orphan"
    )


class RivalSnapshot(Base):
    """A point-in-time analytics capture for a rival on one platform."""

    __tablename__ = "rival_snapshot"

    id = Column(Integer, primary_key=True)
    rival_id = Column(Integer, ForeignKey("rival.id"), nullable=False)
    platform = Column(String(50), nullable=False)  # youtube, instagram, website
    status = Column(String(50), default="ok")  # ok, not_configured, unavailable, error
    metrics = Column(JSON, nullable=True)  # normalized stats (followers, views, etc.)
    recent_items = Column(JSON, nullable=True)  # recent posts/videos with engagement
    message = Column(Text, nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    rival = relationship("Rival", back_populates="snapshots")


class AnalyticsMetric(Base):
    """Analytics & performance metrics."""

    __tablename__ = "analytics_metric"

    id = Column(Integer, primary_key=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    platform = Column(String(50), nullable=True)
    recorded_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class PlatformCredential(Base):
    """
    Persisted OAuth secrets for social platforms (Meta / YouTube).
    Survives deploys so analytics tokens do not need manual re-paste into .env.
    """

    __tablename__ = "platform_credential"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    """System users (placeholder for authentication)."""

    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
