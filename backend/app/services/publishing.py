"""
Publishing Service
Shared logic for posting stored Content to social platforms.

Used by:
- The immediate "post now" route (POST /content/{id}/post)
- The background scheduler that publishes due CalendarEvents

Keeping this in one place guarantees scheduled posts behave identically to
posts triggered manually from the UI.
"""

from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import Content, ContentStatus, PostStatus as DBPostStatus
from app.services.content import ContentService
from app.services.media import MediaService
from app.services.social_publisher import SocialPublisher
from app.utils.logger import logger

# Single shared media service instance (mirrors the route module)
media_service = MediaService()


def _map_post_status(status: str) -> DBPostStatus:
    """Map a publisher result status string to the DB PostStatus enum."""
    if status == "published":
        return DBPostStatus.PUBLISHED
    if status == "draft":
        return DBPostStatus.PENDING
    if status == "partial":
        return DBPostStatus.PARTIAL
    return DBPostStatus.FAILED


def publish_content(
    db: Session,
    content_id: int,
    platforms: list[str],
    draft_mode: bool = False,
    override_title: Optional[str] = None,
    override_body: Optional[str] = None,
    linkedin_account_labels: Optional[list[str]] = None,
) -> list[dict]:
    """
    Publish a stored Content record (caption + any attached media) to the
    requested social platforms and persist the per-platform posting status.

    Args:
        db: Active SQLAlchemy session
        content_id: ID of the Content row to publish
        platforms: Platform names, e.g. ["linkedin", "facebook", "instagram"]
        draft_mode: When True, simulates posting without hitting live APIs
        override_title: Optional edited caption title
        override_body: Optional edited caption body
        linkedin_account_labels: Optional subset of LinkedIn accounts to post from

    Returns:
        A list of result dicts (one per platform / LinkedIn account) with keys:
        content_id, platform, status, post_url, post_id, error_message, account_label

    Raises:
        ValueError: If the content_id does not exist.
    """
    service = ContentService(db)
    content = service.get_content(content_id)

    if not content:
        raise ValueError(f"Content {content_id} not found")

    post_title = override_title if override_title else content["title"]
    post_body = override_body if override_body else content["body"]

    if override_title or override_body:
        logger.info(f"Using edited caption for content {content_id}")

    # Resolve media for upload
    media_file_path = None
    media_type_val = None
    media_supabase_url = None
    temp_file_path = None

    if content.get("media_path"):
        media_type_val = content.get("media_type")

        if media_service.is_supabase_configured:
            try:
                temp_file_path = media_service.download_to_temp(content["media_path"])
                media_file_path = temp_file_path
                media_supabase_url = media_service.get_public_url(content["media_path"])
                logger.info(
                    f"Using Supabase storage: temp={temp_file_path}, url={media_supabase_url}"
                )
            except Exception as e:
                logger.error(f"Failed to download media from Supabase: {e}")
        else:
            upload_dir = Path(__file__).parent.parent.parent / "uploads"
            full_path = upload_dir / content["media_path"]
            if full_path.exists():
                media_file_path = str(full_path.absolute())

    publisher = SocialPublisher(draft_mode=draft_mode)

    youtube_tags = content.get("meta_data", {}).get("hashtags", []) if content else []

    platform_results = publisher.post_to_multiple(
        platforms=platforms,
        title=post_title,
        body=post_body,
        media_file_path=media_file_path,
        media_type=media_type_val,
        media_relative_path=content.get("media_path"),
        media_url=media_supabase_url,
        tags=youtube_tags,
        linkedin_account_labels=linkedin_account_labels,
    )

    if temp_file_path:
        media_service.cleanup_temp_file(temp_file_path)

    # Persist per-platform status onto the Content row
    responses: list[dict] = []
    db_content = db.query(Content).filter(Content.id == content_id).first()

    for platform_name, result in platform_results.items():
        response_status = result.get("status", "failed")
        post_id_value = result.get("post_id")

        if db_content:
            if platform_name == "linkedin":
                account_results = result.get("accounts") or []
                db_content.linkedin_post_status = _map_post_status(response_status)
                db_content.linkedin_post_id = post_id_value
                if account_results:
                    db_content.linkedin_accounts_results = account_results
            elif platform_name == "facebook":
                db_content.facebook_post_status = _map_post_status(response_status)
                db_content.facebook_post_id = post_id_value
            elif platform_name == "instagram":
                db_content.instagram_post_status = _map_post_status(response_status)
                db_content.instagram_post_id = post_id_value
            elif platform_name == "youtube":
                db_content.youtube_post_status = _map_post_status(response_status)
                db_content.youtube_post_id = post_id_value

        if platform_name == "linkedin" and result.get("accounts"):
            for account_result in result["accounts"]:
                responses.append(
                    {
                        "content_id": content_id,
                        "platform": platform_name,
                        "status": account_result.get("status", "failed"),
                        "post_url": account_result.get("post_url"),
                        "post_id": account_result.get("post_id"),
                        "error_message": account_result.get("error_message"),
                        "account_label": account_result.get("label"),
                    }
                )
        else:
            responses.append(
                {
                    "content_id": content_id,
                    "platform": platform_name,
                    "status": response_status,
                    "post_url": result.get("post_url"),
                    "post_id": post_id_value,
                    "error_message": result.get("error_message"),
                    "account_label": None,
                }
            )

    if db_content:
        overall = summarize_statuses(responses)
        if overall in ("published", "partial"):
            db_content.status = ContentStatus.PUBLISHED
        db.commit()

    return responses


def summarize_statuses(responses: list[dict]) -> str:
    """
    Reduce a list of per-platform results into one overall status string:
    'published', 'partial', 'draft', or 'failed'.
    """
    if not responses:
        return "failed"

    statuses = [r.get("status", "failed") for r in responses]
    ok = [s for s in statuses if s in ("published", "draft")]

    if len(ok) == len(statuses):
        # All succeeded — distinguish draft simulations from live publishes
        return "draft" if all(s == "draft" for s in statuses) else "published"
    if ok:
        return "partial"
    return "failed"
