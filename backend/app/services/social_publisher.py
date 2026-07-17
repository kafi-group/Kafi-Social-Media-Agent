"""
Social Media Publisher Service
Handles posting content (captions + media) to LinkedIn, Facebook, and Instagram.
Supports draft/test mode for development with dummy accounts.
"""

import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests

from app.config import settings
from app.utils.logger import logger


@dataclass
class LinkedInAccountConfig:
    """Credentials for a single LinkedIn personal profile.

    `person_id` is optional — when omitted it is resolved automatically from the
    access token at runtime (via the OpenID `userinfo` endpoint), which guarantees
    the author URN always matches the token owner.
    """

    label: str
    access_token: str
    person_id: str = ""


def load_linkedin_accounts() -> list[LinkedInAccountConfig]:
    """Load up to 3 LinkedIn accounts from environment variables.

    Only an access token is required per account. The person/member ID is optional
    and resolved from the token at runtime if not provided. This avoids the common
    403 "Field Value validation failed ... [/author]" error caused by a configured
    person ID that doesn't match the token owner.
    """
    accounts: list[LinkedInAccountConfig] = []

    # Account 1 supports both the legacy primary vars (LINKEDIN_ACCESS_TOKEN /
    # LINKEDIN_PERSON_ID) and the numbered vars (LINKEDIN_ACCOUNT_1_*).
    primary_token = (
        (settings.LINKEDIN_ACCESS_TOKEN or "").strip()
        or (getattr(settings, "LINKEDIN_ACCOUNT_1_ACCESS_TOKEN", "") or "").strip()
    )
    primary_person = (
        (settings.LINKEDIN_PERSON_ID or "").strip()
        or (getattr(settings, "LINKEDIN_ACCOUNT_1_PERSON_ID", "") or "").strip()
    )
    if primary_token:
        accounts.append(
            LinkedInAccountConfig(
                label=(settings.LINKEDIN_ACCOUNT_1_LABEL or "Account 1").strip() or "Account 1",
                access_token=primary_token,
                person_id=primary_person,
            )
        )
    elif primary_person:
        logger.warning("LinkedIn account 1 has a person ID but no access token — skipping")

    for num in (2, 3):
        label = (getattr(settings, f"LINKEDIN_ACCOUNT_{num}_LABEL", "") or f"Account {num}").strip()
        token = (getattr(settings, f"LINKEDIN_ACCOUNT_{num}_ACCESS_TOKEN", "") or "").strip()
        person_id = (getattr(settings, f"LINKEDIN_ACCOUNT_{num}_PERSON_ID", "") or "").strip()
        if token:
            accounts.append(
                LinkedInAccountConfig(
                    label=label or f"Account {num}",
                    access_token=token,
                    person_id=person_id,
                )
            )
        elif person_id:
            logger.warning(
                f"LinkedIn account {num} has a person ID but no access token — skipping"
            )

    return accounts


class SocialPublisherError(Exception):
    """Base error for social media publishing."""

    pass


class LinkedInClient:
    """LinkedIn API client for posting content with media (Posts API).

    Uses the newer LinkedIn REST Posts API (not the legacy UGC API).
    Requires a LinkedIn Developer App with w_member_social scope.
    """

    API_BASE_URL = "https://api.linkedin.com/rest"
    MEDIA_API_URL = "https://api.linkedin.com/rest/images?action=initializeUpload"
    VIDEO_API_URL = "https://api.linkedin.com/rest/videos?action=initializeUpload"
    VIDEO_FINALIZE_URL = "https://api.linkedin.com/rest/videos?action=finalizeUpload"
    API_VERSION = "202604"  # LinkedIn API version header (YYYYMM)

    def __init__(
        self,
        access_token: str,
        person_id: str = "",
        account_label: str = "Account 1",
        draft_mode: bool = False,
    ):
        self.access_token = access_token
        self.person_id = (person_id or "").strip()
        self.account_label = account_label
        self.draft_mode = draft_mode
        self._resolved_person_id: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        # Only a token is required — the person ID is resolved from the token itself.
        return bool(self.access_token)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Linkedin-Version": self.API_VERSION,
            "Content-Type": "application/json",
        }

    def _resolve_person_id(self) -> str:
        """Resolve the member ID that actually owns this access token.

        Calls the OpenID `userinfo` endpoint and uses its `sub` claim, which is the
        only ID guaranteed to be accepted as the post author for this token. Falls
        back to the configured person_id only if the lookup fails. The result is
        cached for the lifetime of the client.
        """
        if self._resolved_person_id:
            return self._resolved_person_id

        try:
            resp = requests.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=20,
            )
            if resp.ok:
                sub = (resp.json().get("sub") or "").strip()
                if sub:
                    if self.person_id and sub != self.person_id:
                        logger.warning(
                            f"LinkedIn {self.account_label}: configured person_id "
                            f"'{self.person_id}' does not match token owner '{sub}'. "
                            f"Using token owner ID from userinfo."
                        )
                    self._resolved_person_id = sub
                    return sub
            else:
                logger.warning(
                    f"LinkedIn {self.account_label}: userinfo lookup failed "
                    f"({resp.status_code}); falling back to configured person_id"
                )
        except Exception as e:
            logger.warning(
                f"LinkedIn {self.account_label}: userinfo lookup error ({e}); "
                f"falling back to configured person_id"
            )

        self._resolved_person_id = self.person_id
        return self._resolved_person_id

    def _person_urn(self) -> str:
        """Person URN for REST/assets APIs (owner field)."""
        return f"urn:li:person:{self._resolve_person_id()}"

    def _author_urn(self) -> str:
        """Person URN for UGC/REST post author field.

        LinkedIn expects `urn:li:person:{id}` here (not urn:li:member). The id must
        be the token owner's ID as returned by the userinfo `sub` claim.
        """
        return f"urn:li:person:{self._resolve_person_id()}"

    def _upload_image_ugc(self, image_path: str) -> Optional[str]:
        """Upload image via UGC Assets API (Share on LinkedIn product)."""
        try:
            init_response = requests.post(
                "https://api.linkedin.com/v2/assets?action=registerUpload",
                headers=self._headers(),
                json={
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                        "owner": self._person_urn(),
                        "serviceRelationships": [
                            {
                                "relationshipType": "OWNER",
                                "identifier": "urn:li:userGeneratedContent",
                            }
                        ],
                    }
                },
                timeout=30,
            )
            init_response.raise_for_status()
            upload_data = init_response.json()["value"]
            upload_url = upload_data["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]["uploadUrl"]
            asset_urn = upload_data["asset"]

            with open(image_path, "rb") as f:
                image_data = f.read()

            upload_response = requests.put(upload_url, data=image_data, timeout=120)
            if not upload_response.ok:
                logger.error(
                    f"LinkedIn UGC image binary upload failed: {upload_response.status_code} "
                    f"{upload_response.text[:500]}"
                )
                upload_response.raise_for_status()

            logger.info(f"LinkedIn UGC image uploaded: {asset_urn}")
            return asset_urn
        except Exception as e:
            logger.error(f"LinkedIn UGC image upload failed: {str(e)}")
            return None

    def _create_ugc_post(
        self,
        commentary: str,
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
    ) -> dict:
        """Create a post via UGC API (Share on LinkedIn product)."""
        share_content: dict = {
            "shareCommentary": {"text": commentary},
            "shareMediaCategory": "NONE",
        }

        if media_path and media_type == "image":
            asset_urn = self._upload_image_ugc(media_path)
            if asset_urn:
                share_content["shareMediaCategory"] = "IMAGE"
                share_content["media"] = [
                    {
                        "status": "READY",
                        "description": {"text": commentary[:200]},
                        "media": asset_urn,
                        "title": {"text": commentary[:100]},
                    }
                ]

        post_data = {
            "author": self._author_urn(),
            "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        response = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=self._headers(),
            json=post_data,
            timeout=30,
        )

        if not response.ok:
            # DUPLICATE_POST means LinkedIn already has this exact content live
            # (e.g. a previous attempt succeeded then this one retried). Treat it
            # as success and recover the existing share URN so retries are idempotent.
            if response.status_code == 422 and "DUPLICATE_POST" in response.text:
                existing = re.search(r"urn:li:(?:share|ugcPost):(\d+)", response.text)
                share_urn = existing.group(0) if existing else None
                share_id = existing.group(1) if existing else None
                logger.warning(
                    f"LinkedIn {self.account_label}: duplicate detected — content already "
                    f"posted ({share_urn}); treating as published."
                )
                return {
                    "status": "published",
                    "post_id": share_urn or share_id,
                    "post_url": (
                        f"https://www.linkedin.com/feed/update/{share_urn}"
                        if share_urn
                        else None
                    ),
                    "error_message": None,
                }

            hint = ""
            if response.status_code == 403:
                hint = (
                    " (403: token invalid/expired, person_id does not match token owner, "
                    "or token was generated before w_member_social was enabled — regenerate token)"
                )
            elif response.status_code == 401 and "RESTRICTED_MEMBER" in response.text:
                hint = (
                    " (401 RESTRICTED_MEMBER: this LinkedIn account is restricted/suspended "
                    "or is a test account — remove it from .env or use a valid account)"
                )
            elif response.status_code == 422:
                hint = " (422: person_id format wrong — use numeric ID from urn:li:member: in page source)"
            if "fields [/author]" in response.text:
                hint = (
                    " (author rejected: person_id does not match token owner — "
                    "each person must generate their own token AND use their own urn:li:member:ID)"
                )
            logger.error(
                f"LinkedIn UGC post failed for {self.account_label}: "
                f"{response.status_code} {response.text[:500]}{hint}"
            )
            response.raise_for_status()

        post_id = response.headers.get("x-restli-id", "")
        if not post_id:
            location = response.headers.get("location", "")
            if location:
                post_id = location.split("/")[-1]

        logger.info(f"LinkedIn UGC post created for {self.account_label}: {post_id}")
        return {
            "status": "published",
            "post_id": post_id,
            "post_url": f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None,
            "error_message": None,
        }

    def _upload_image(self, image_path: str) -> Optional[str]:
        """
        Upload an image to LinkedIn and return the asset URN.
        Steps:
        1. Register upload with LinkedIn API
        2. Upload binary to the returned URL
        3. Return the asset URN
        """
        try:
            # Step 1: Initialize upload
            init_response = requests.post(
                self.MEDIA_API_URL,
                headers=self._headers(),
                json={
                    "initializeUploadRequest": {
                        "owner": self._person_urn(),
                    }
                },
                timeout=30,
            )
            init_response.raise_for_status()
            upload_data = init_response.json()

            # New simpler response format: value.uploadUrl (string) and value.image (URN)
            # Old format (value.uploadMechanism.com.linkedin...uploadUrl and value.asset) is deprecated
            upload_url = upload_data["value"]["uploadUrl"]
            asset_urn = upload_data["value"]["image"]

            # Step 2: Upload actual binary
            with open(image_path, "rb") as f:
                image_data = f.read()

            upload_response = requests.put(
                upload_url,
                data=image_data,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Linkedin-Version": self.API_VERSION,
                },
                timeout=120,
            )

            if not upload_response.ok:
                logger.error(
                    f"LinkedIn image binary upload failed: {upload_response.status_code} "
                    f"{upload_response.text[:500]}"
                )
                upload_response.raise_for_status()

            logger.info(f"LinkedIn image uploaded: {asset_urn}")
            return asset_urn

        except requests.exceptions.HTTPError as e:
            response_body = e.response.text[:1000] if e.response is not None else "N/A"
            logger.error(
                f"LinkedIn image upload HTTP error: {e.response.status_code if e.response else 'N/A'} - "
                f"{response_body}"
            )
            return None
        except Exception as e:
            logger.error(f"LinkedIn image upload failed: {str(e)}")
            return None

    def _upload_video(self, video_path: str) -> Optional[str]:
        """
        Upload a video to LinkedIn and return the video URN.

        Uses the LinkedIn Videos API (/rest/videos) which requires:
        1. Initialize upload (get upload URLs and video URN)
        2. Upload binary chunks with Content-Range headers
        3. Finalize upload (submit ETags to complete registration)

        The video becomes available after LinkedIn processes it (async).
        """
        try:
            file_size = os.path.getsize(video_path)

            # Step 1: Initialize video upload
            init_response = requests.post(
                self.VIDEO_API_URL,
                headers=self._headers(),
                json={
                    "initializeUploadRequest": {
                        "owner": self._person_urn(),
                        "fileSizeBytes": file_size,
                    }
                },
                timeout=30,
            )
            init_response.raise_for_status()
            upload_data = init_response.json()

            video_urn = upload_data["value"]["video"]
            upload_token = upload_data["value"].get("uploadToken", "")
            upload_instructions = upload_data["value"]["uploadInstructions"]

            # Step 2: Upload binary chunks
            etags = []
            with open(video_path, "rb") as f:
                for instruction in upload_instructions:
                    upload_url = instruction["uploadUrl"]
                    first_byte = instruction["firstByte"]
                    last_byte = instruction["lastByte"]
                    chunk_size = last_byte - first_byte + 1

                    f.seek(first_byte)
                    chunk_data = f.read(chunk_size)

                    upload_response = requests.put(
                        upload_url,
                        data=chunk_data,
                        headers={
                            "Authorization": f"Bearer {self.access_token}",
                            "Content-Type": "application/octet-stream",
                            "Content-Range": f"bytes {first_byte}-{last_byte}/{file_size}",
                            "X-Restli-Protocol-Version": "2.0.0",
                            "Linkedin-Version": self.API_VERSION,
                        },
                        timeout=300,
                    )

                    if not upload_response.ok:
                        logger.error(
                            f"LinkedIn video chunk upload failed (bytes {first_byte}-{last_byte}): "
                            f"{upload_response.status_code} {upload_response.text[:500]}"
                        )
                        upload_response.raise_for_status()

                    etag = upload_response.headers.get("ETag", "")
                    if etag:
                        etags.append(etag)

            # Step 3: Finalize video upload
            finalize_response = requests.post(
                self.VIDEO_FINALIZE_URL,
                headers=self._headers(),
                json={
                    "finalizeUploadRequest": {
                        "video": video_urn,
                        "uploadToken": upload_token,
                        "uploadedPartIds": etags if etags else [""],
                    }
                },
                timeout=60,
            )

            if not finalize_response.ok:
                logger.error(
                    f"LinkedIn video finalize failed: {finalize_response.status_code} "
                    f"{finalize_response.text[:500]}"
                )
                finalize_response.raise_for_status()

            logger.info(f"LinkedIn video uploaded and finalized: {video_urn}")
            return video_urn

        except requests.exceptions.HTTPError as e:
            response_body = e.response.text[:1000] if e.response is not None else "N/A"
            logger.error(
                f"LinkedIn video upload HTTP error: {e.response.status_code if e.response else 'N/A'} - "
                f"{response_body}"
            )
            return None
        except Exception as e:
            logger.error(f"LinkedIn video upload failed: {str(e)}")
            return None

    def _create_rest_video_post(
        self,
        title: str,
        body: str,
        commentary: str,
        media_path: str,
    ) -> dict:
        """Video posts still use REST Posts API (requires Community Management API)."""
        post_data: dict = {
            "author": self._author_urn(),
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        video_urn = self._upload_video(media_path)
        if video_urn:
            post_data["content"] = {
                "media": {
                    "title": title or "Video",
                    "id": video_urn,
                }
            }

        response = requests.post(
            f"{self.API_BASE_URL}/posts",
            headers=self._headers(),
            json=post_data,
            timeout=30,
        )
        if not response.ok:
            logger.error(
                f"LinkedIn REST video post failed for {self.account_label}: "
                f"{response.status_code} {response.text[:500]}"
            )
            response.raise_for_status()

        post_id = response.headers.get("x-restli-id", "") or response.headers.get("location", "").split("/")[-1]
        return {
            "status": "published",
            "post_id": post_id,
            "post_url": f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None,
            "error_message": None,
        }

    def create_post(
        self,
        title: str,
        body: str,
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
    ) -> dict:
        """
        Create a post on LinkedIn using the UGC API (Share on LinkedIn product).

        Args:
            title: Post title/headline
            body: Post body text
            media_path: Local filesystem path to media file (optional)
            media_type: Type of media ('image' or 'video')

        Returns:
            Dict with status, post_id, post_url, error_message
        """
        if self.draft_mode:
            logger.info(
                f"[DRAFT] LinkedIn post for {self.account_label} would be created:\n"
                f"Title: {title}\nBody: {body}"
            )
            return {
                "status": "draft",
                "post_id": None,
                "post_url": None,
                "error_message": None,
            }

        if not self.is_configured:
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": "LinkedIn API not configured. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID.",
            }

        try:
            commentary = f"{title}\n\n{body}" if title else body

            # Share on LinkedIn product uses the UGC API, not REST /posts.
            # REST /posts requires Community Management API (separate product).
            if media_path and media_type == "video":
                return self._create_rest_video_post(title, body, commentary, media_path)

            return self._create_ugc_post(commentary, media_path, media_type)

        except Exception as e:
            logger.error(f"LinkedIn post failed: {str(e)}")
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": str(e),
            }


class FacebookClient:
    """Facebook Graph API client for posting to Facebook Pages."""

    GRAPH_API_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, draft_mode: bool = False):
        self.page_id = settings.FACEBOOK_PAGE_ID or ""
        self.page_access_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN or ""
        self.draft_mode = draft_mode

    @property
    def is_configured(self) -> bool:
        return bool(self.page_id and self.page_access_token)

    def create_post(
        self,
        title: str,
        body: str,
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
    ) -> dict:
        """
        Create a post on Facebook Page.

        Args:
            title: Post title
            body: Post body/message
            media_path: Local filesystem path to media file (optional)
            media_type: Type of media ('image' or 'video')

        Returns:
            Dict with status, post_id, post_url, error_message
        """
        if self.draft_mode:
            logger.info(f"[DRAFT] Facebook post would be created:\nTitle: {title}\nBody: {body}")
            return {
                "status": "draft",
                "post_id": None,
                "post_url": None,
                "error_message": None,
            }

        if not self.is_configured:
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": "Facebook API not configured. Set FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN.",
            }

        try:
            message = f"{title}\n\n{body}" if title else body
            params = {
                "access_token": self.page_access_token,
            }

            if media_path and media_type == "image":
                # Upload photo
                with open(media_path, "rb") as f:
                    files = {"source": f}
                    data = {
                        "message": message,
                        "access_token": self.page_access_token,
                    }
                    response = requests.post(
                        f"{self.GRAPH_API_URL}/{self.page_id}/photos",
                        data=data,
                        files=files,
                        timeout=180,
                    )
            elif media_path and media_type == "video":
                # Upload video
                with open(media_path, "rb") as f:
                    files = {"source": f}
                    data = {
                        "description": message,
                        "access_token": self.page_access_token,
                    }
                    response = requests.post(
                        f"{self.GRAPH_API_URL}/{self.page_id}/videos",
                        data=data,
                        files=files,
                        timeout=300,
                    )
            else:
                # Text-only post
                params["message"] = message
                response = requests.post(
                    f"{self.GRAPH_API_URL}/{self.page_id}/feed",
                    params=params,
                    timeout=60,
                )

            response.raise_for_status()
            result = response.json()
            post_id = result.get("id", "")
            logger.info(f"Facebook post created: {post_id}")

            return {
                "status": "published",
                "post_id": post_id,
                "post_url": f"https://www.facebook.com/{post_id}",
                "error_message": None,
            }

        except Exception as e:
            logger.error(f"Facebook post failed: {str(e)}")
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": str(e),
            }


class InstagramClient:
    """
    Instagram Graph API client for posting to Instagram Business accounts.

    IMPORTANT:
    The Instagram Content Publishing API requires ALL media (images AND videos) to be
    accessible via a **publicly reachable URL**. Direct file uploads are NOT supported.

    NOTE on video posting:
    Instagram has deprecated `media_type=VIDEO`. Videos must now use `media_type=REELS`,
    which publishes the video to the main feed (not just the Reels tab).
    See: https://developers.facebook.com/docs/instagram-api/reference/ig-user/media#creating

    For local development / staging:
    - Use `draft_mode=True` (default) to simulate posting without making API calls
    - For live posting, you MUST provide a public URL via the `media_url` parameter
      (e.g., a Supabase Storage public URL)

    Reference:
    https://developers.facebook.com/docs/instagram-api/reference/ig-user/media
    https://developers.facebook.com/docs/instagram-api/reference/ig-user/media_publish
    """

    GRAPH_API_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, draft_mode: bool = False, server_base_url: str = ""):
        self.instagram_account_id = settings.INSTAGRAM_ACCOUNT_ID or ""
        self.page_access_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN or ""  # Uses FB token
        self.draft_mode = draft_mode
        self.server_base_url = server_base_url or "http://localhost:8000"

    @property
    def is_configured(self) -> bool:
        return bool(self.instagram_account_id and self.page_access_token)

    def _graph_api_url(self) -> str:
        version = (settings.META_GRAPH_API_VERSION or "v21.0").strip()
        return f"https://graph.facebook.com/{version}"

    def _wait_for_container_ready(self, container_id: str, media_type: str) -> tuple[bool, str]:
        """
        Poll the IG media container until Meta finishes processing.

        Images and videos both return IN_PROGRESS briefly; publishing before
        FINISHED triggers OAuth error #9007 (subcode 2207027).
        """
        if media_type == "video":
            max_retries = 24
            retry_delay = 5
        else:
            max_retries = 20
            retry_delay = 2

        graph_url = self._graph_api_url()
        for attempt in range(1, max_retries + 1):
            logger.info(
                f"Instagram container processing check ({attempt}/{max_retries}) "
                f"for {container_id} ({media_type})..."
            )
            time.sleep(retry_delay)

            status_response = requests.get(
                f"{graph_url}/{container_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": self.page_access_token,
                },
                timeout=30,
            )

            if not status_response.ok:
                logger.warning(f"Instagram status check failed: {status_response.text[:500]}")
                continue

            status_data = status_response.json()
            status_code = (status_data.get("status_code") or "").upper()
            logger.info(f"Instagram container {container_id} status: {status_code}")

            if status_code == "FINISHED":
                return True, ""
            if status_code in ("ERROR", "EXPIRED"):
                error_detail = status_data.get("status") or status_data.get(
                    "error_message", "Unknown processing error"
                )
                return False, f"Instagram media processing failed: {error_detail}"

        timeout_seconds = max_retries * retry_delay
        return (
            False,
            (
                "Instagram media processing timed out after "
                f"{timeout_seconds} seconds. Meta could not fetch or process the "
                "public media URL — confirm the image/video URL is HTTPS, "
                "publicly accessible, and returns the correct content type."
            ),
        )

    def create_post(
        self,
        title: str,
        body: str,
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
        media_relative_path: Optional[str] = None,
        media_url: Optional[str] = None,
    ) -> dict:
        """
        Create a post on Instagram Business Account.

        Instagram's Content Publishing API requires ALL media to be accessible via
        a publicly reachable URL. The `media_url` parameter (e.g., Supabase public URL)
        is used as `image_url` for images or `video_url` for videos.

        Args:
            title: Post title
            body: Post caption
            media_path: Local filesystem path to media file (not used for upload, but
                       required to confirm media is attached)
            media_type: Type of media ('image' or 'video')
            media_relative_path: Relative path for constructing public URL
                                 (e.g., "images/abc.jpg") — fallback if media_url not set
            media_url: Direct public URL (overrides constructed URL if provided).
                       When using Supabase, this is the Supabase public URL.

        Returns:
            Dict with status, post_id, post_url, error_message
        """
        if self.draft_mode:
            logger.info(
                f"[DRAFT] Instagram post would be created:\nCaption: {body}\nMedia: {media_path}"
            )
            return {
                "status": "draft",
                "post_id": None,
                "post_url": None,
                "error_message": None,
            }

        if not self.is_configured:
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": "Instagram API not configured. Set INSTAGRAM_ACCOUNT_ID and FACEBOOK_PAGE_ACCESS_TOKEN.",
            }

        if not media_path:
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": "Instagram requires media (image/video) to create a post.",
            }

        try:
            caption = f"{title}\n\n{body}" if title else body

            if media_type in ("image", "video"):
                # Instagram REQUIRES a public URL for ALL media types (image AND video)
                # Priority: 1) direct media_url, 2) constructed from media_relative_path
                public_url = media_url
                if not public_url and media_relative_path:
                    public_url = f"{self.server_base_url}/uploads/{media_relative_path}"
                if not public_url:
                    return {
                        "status": "failed",
                        "post_id": None,
                        "post_url": None,
                        "error_message": (
                            "Instagram posting requires a publicly accessible URL. "
                            "Set media_url, media_relative_path, or deploy the server "
                            "to a public URL. "
                            "When using Supabase Storage, ensure SUPABASE_URL and "
                            "SUPABASE_SECRET_KEY are configured in .env."
                        ),
                    }

                # Build params: image_url for images, media_type=VIDEO + video_url for videos
                params = {
                    "caption": caption,
                    "access_token": self.page_access_token,
                }
                if media_type == "video":
                    # Instagram deprecated media_type=VIDEO; must use REELS
                    # This publishes the video to the main feed (not Reels tab)
                    params["media_type"] = "REELS"
                    params["video_url"] = public_url
                else:
                    params["image_url"] = public_url

                logger.info(f"Instagram media container URL: {public_url}")

                container_response = requests.post(
                    f"{self._graph_api_url()}/{self.instagram_account_id}/media",
                    params=params,
                    timeout=120,
                )

            else:
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": f"Unsupported media type for Instagram: {media_type}",
                }

            container_response.raise_for_status()
            container_id = container_response.json().get("id", "")

            if not container_id:
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": "Failed to create Instagram media container",
                }

            container_ready, container_error = self._wait_for_container_ready(
                container_id, media_type
            )
            if not container_ready:
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": container_error,
                    "container_id": container_id,
                }

            # Publish the media container once Meta reports FINISHED.
            publish_response = requests.post(
                f"{self._graph_api_url()}/{self.instagram_account_id}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": self.page_access_token,
                },
                timeout=60,
            )
            publish_response.raise_for_status()
            published_id = publish_response.json().get("id", "")

            logger.info(f"Instagram post created: {published_id}")

            return {
                "status": "published",
                "post_id": published_id,
                "post_url": f"https://www.instagram.com/p/{published_id}",
                "error_message": None,
            }

        except requests.exceptions.HTTPError as e:
            response_detail = ""
            if e.response is not None:
                try:
                    error_json = e.response.json()
                    response_detail = str(error_json.get("error", error_json))[:1000]
                except Exception:
                    response_detail = e.response.text[:1000]
            logger.error(f"Instagram API error: {response_detail}")
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": f"Instagram API error: {response_detail}",
            }
        except Exception as e:
            logger.error(f"Instagram post failed: {str(e)}")
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": str(e),
            }


class YouTubeClient:
    """
    YouTube Data API v3 client for uploading videos.

    Uses OAuth 2.0 with a refresh token to authenticate.
    Videos are uploaded via the resumable upload protocol.

    YouTube automatically classifies uploaded videos:
    - < 60 seconds + vertical (9:16) = Short
    - >= 60 seconds or landscape = Regular video
    No special flag is needed — YouTube handles this automatically.

    Requirements (set in .env):
        YOUTUBE_CLIENT_ID
        YOUTUBE_CLIENT_SECRET
        YOUTUBE_REFRESH_TOKEN
        YOUTUBE_CHANNEL_ID (optional, for analytics)

    Reference:
        https://developers.google.com/youtube/v3/docs/videos/insert
    """

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    UPLOAD_API_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
    VIDEO_API_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, draft_mode: bool = False):
        def _clean(value: str) -> str:
            clean = (value or "").strip()
            if len(clean) >= 2 and clean[0] == clean[-1] and clean[0] in ("'", '"'):
                clean = clean[1:-1].strip()
            return clean

        self.client_id = _clean(settings.YOUTUBE_CLIENT_ID or "")
        self.client_secret = _clean(settings.YOUTUBE_CLIENT_SECRET or "")
        self.refresh_token = _clean(settings.YOUTUBE_REFRESH_TOKEN or "")
        self.channel_id = _clean(settings.YOUTUBE_CHANNEL_ID or "")
        self.category_id = settings.YOUTUBE_VIDEO_CATEGORY_ID or "22"
        self.draft_mode = draft_mode
        self._access_token: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        return bool(
            self.client_id
            and self.client_secret
            and self.refresh_token
        )

    def _resolve_oauth_channel(self, access_token: str) -> Optional[dict]:
        """Return the YouTube channel tied to this OAuth token (upload target)."""
        try:
            response = requests.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20,
            )
            if not response.ok:
                logger.warning(
                    f"YouTube channel lookup failed: {response.status_code} "
                    f"{response.text[:200]}"
                )
                return None
            items = response.json().get("items", [])
            if not items:
                return None
            channel = items[0]
            snippet = channel.get("snippet", {})
            return {
                "id": channel.get("id", ""),
                "title": snippet.get("title", ""),
                "custom_url": snippet.get("customUrl", ""),
            }
        except requests.RequestException as exc:
            logger.warning(f"YouTube channel lookup error: {exc}")
            return None

    def _refresh_access_token(self) -> Optional[str]:
        """
        Exchange the refresh token for a new access token.

        Returns:
            Access token string, or None if refresh fails
        """
        try:
            response = requests.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )

            if not response.ok:
                logger.error(
                    f"YouTube token refresh failed: {response.status_code} "
                    f"{response.text[:500]}"
                )
                return None

            data = response.json()
            self._access_token = data.get("access_token", "")
            logger.info("YouTube OAuth token refreshed successfully")
            return self._access_token

        except Exception as e:
            logger.error(f"YouTube token refresh error: {str(e)}")
            return None

    def _get_headers(self) -> dict:
        """Get authenticated headers for YouTube API calls."""
        token = self._access_token or self._refresh_access_token()
        if not token:
            return {}
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: Optional[list[str]] = None,
        privacy_status: Optional[str] = None,  # private, unlisted, public
    ) -> dict:
        """
        Upload a video to YouTube using the resumable upload protocol.

        Args:
            video_path: Local filesystem path to the video file
            title: Video title
            description: Video description (optionally with hashtags)
            tags: List of tags/keywords for the video
            privacy_status: 'private', 'unlisted', or 'public' (defaults to YOUTUBE_DEFAULT_PRIVACY_STATUS)

        Returns:
            Dict with status, video_id, video_url, error_message
        """
        privacy_status = privacy_status or settings.YOUTUBE_DEFAULT_PRIVACY_STATUS

        if self.draft_mode:
            logger.info(
                f"[DRAFT] YouTube video would be uploaded:\n"
                f"  Title: {title}\n"
                f"  File: {video_path}\n"
                f"  Privacy: {privacy_status}"
            )
            return {
                "status": "draft",
                "post_id": None,
                "post_url": None,
                "error_message": None,
            }

        if not self.is_configured:
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": (
                    "YouTube API not configured. Set YOUTUBE_CLIENT_ID, "
                    "YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN in .env."
                ),
            }

        if not os.path.exists(video_path):
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": f"Video file not found: {video_path}",
            }

        try:
            # Step 1: Get a fresh access token
            token = self._refresh_access_token()
            if not token:
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": "Failed to obtain YouTube access token. Check YOUTUBE_REFRESH_TOKEN.",
                }

            oauth_channel = self._resolve_oauth_channel(token)
            configured_channel_id = self.channel_id.strip()
            if oauth_channel and configured_channel_id:
                oauth_id = oauth_channel.get("id", "")
                if oauth_id and oauth_id != configured_channel_id:
                    label = (
                        oauth_channel.get("title", "").strip()
                        or oauth_channel.get("custom_url")
                        or oauth_id
                    )
                    error_message = (
                        f"Upload blocked: your refresh token is tied to '{label}' ({oauth_id}), "
                        f"but YOUTUBE_CHANNEL_ID is set to {configured_channel_id}. "
                        "Revoke the app at https://myaccount.google.com/permissions, switch to "
                        "the correct channel in YouTube (Essence Food), then re-authorize at "
                        "/api/v1/auth/youtube in an incognito window."
                    )
                    logger.error(error_message)
                    return {
                        "status": "failed",
                        "post_id": None,
                        "post_url": None,
                        "error_message": error_message,
                    }
                logger.info(
                    "YouTube upload target channel: %s (%s)",
                    oauth_channel.get("title", oauth_id),
                    oauth_id,
                )

            auth_header = {"Authorization": f"Bearer {token}"}

            # Step 2: Build video metadata (snippet + status)
            snippet = {
                "title": title[:100],  # YouTube max title length
                "description": description[:5000],  # YouTube max description length
                "categoryId": self.category_id,
            }
            if tags:
                # YouTube limits tags to ~500 characters total when serialized
                # Join tags, truncate to 500 chars, then split back
                joined_tags = ",".join(tags)
                if len(joined_tags) > 500:
                    # Find break point: truncate to last complete tag under 500 chars
                    truncated = joined_tags[:500]
                    last_comma = truncated.rfind(",")
                    if last_comma > 0:
                        truncated = truncated[:last_comma]
                    snippet["tags"] = truncated.split(",")
                else:
                    snippet["tags"] = tags

            body = {
                "snippet": snippet,
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            # Step 3: Initiate resumable upload session
            # First request: get the upload URL
            init_headers = {
                **auth_header,
                "Content-Type": "application/json",
                "X-Upload-Content-Length": str(os.path.getsize(video_path)),
                "X-Upload-Content-Type": "video/*",
            }

            init_response = requests.post(
                f"{self.UPLOAD_API_URL}?uploadType=resumable&part=snippet,status",
                headers=init_headers,
                json=body,
                timeout=30,
            )

            if not init_response.ok:
                error_detail = init_response.text[:500]
                logger.error(f"YouTube upload session initiation failed: {init_response.status_code} - {error_detail}")
                if init_response.status_code == 403 and "insufficient" in error_detail.lower():
                    return {
                        "status": "failed",
                        "post_id": None,
                        "post_url": None,
                        "error_message": (
                            "YouTube token lacks upload permission. Your refresh token was "
                            "authorized without the youtube.upload scope. Re-authorize at "
                            "https://kafi-social-agent.up.railway.app/api/v1/auth/youtube "
                            "(token auto-saves; no .env paste needed)."
                        ),
                    }
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": f"YouTube upload session failed: {error_detail}",
                }

            # Get the upload URL from the Location header
            upload_url = init_response.headers.get("Location", "")
            if not upload_url:
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": "YouTube did not return an upload URL.",
                }

            # Step 4: Upload the actual video bytes
            file_size = os.path.getsize(video_path)
            with open(video_path, "rb") as f:
                video_data = f.read()

            upload_headers = {
                **auth_header,
                "Content-Length": str(file_size),
                "Content-Type": "video/*",
            }

            upload_response = requests.put(
                upload_url,
                headers=upload_headers,
                data=video_data,
                timeout=600,  # 10 min timeout for large video uploads
            )

            if not upload_response.ok:
                error_detail = upload_response.text[:500]
                logger.error(f"YouTube video binary upload failed: {upload_response.status_code} - {error_detail}")
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": f"YouTube video upload failed: {error_detail}",
                }

            # Step 5: Parse response for video ID
            upload_result = upload_response.json()
            video_id = upload_result.get("id", "")

            if not video_id:
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": "YouTube upload succeeded but no video ID returned.",
                }

            # Construct the watch URL
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            logger.info(f"YouTube video uploaded successfully: {video_id} ({video_url})")

            result = {
                "status": "published",
                "post_id": video_id,
                "post_url": video_url,
                "error_message": None,
            }
            return result

        except requests.exceptions.Timeout:
            logger.error("YouTube video upload timed out (file may be too large)")
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": "YouTube upload timed out. Try a smaller file or check your connection.",
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"YouTube upload request error: {str(e)}")
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": f"YouTube upload request failed: {str(e)}",
            }
        except Exception as e:
            logger.error(f"YouTube video upload failed: {str(e)}")
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": str(e),
            }


class SocialPublisher:
    """
    Orchestrates posting content to multiple social media platforms.
    Handles both draft/testing mode and live publishing.
    """

    def __init__(self, draft_mode: Optional[bool] = None):
        # Use passed draft_mode, fall back to env var setting, default to True (safe)
        self.draft_mode = draft_mode if draft_mode is not None else settings.DRAFT_MODE
        self.linkedin_accounts = [
            LinkedInClient(
                access_token=acct.access_token,
                person_id=acct.person_id,
                account_label=acct.label,
                draft_mode=self.draft_mode,
            )
            for acct in load_linkedin_accounts()
        ]
        self.facebook = FacebookClient(draft_mode=self.draft_mode)
        self.instagram = InstagramClient(draft_mode=self.draft_mode)
        self.youtube = YouTubeClient(draft_mode=self.draft_mode)

    def post_to_multiple(
        self,
        platforms: list[str],
        title: str,
        body: str,
        media_file_path: Optional[str] = None,
        media_type: Optional[str] = None,
        media_relative_path: Optional[str] = None,
        media_url: Optional[str] = None,
        tags: Optional[list[str]] = None,
        privacy_status: Optional[str] = None,
        linkedin_account_labels: Optional[list[str]] = None,
    ) -> dict[str, dict]:
        """
        Post content to multiple platforms at once.

        Args:
            platforms: List of platform names (e.g., ['linkedin', 'facebook', 'youtube'])
            title: Post title
            body: Post body/content
            media_file_path: Full filesystem path to media file (optional)
            media_type: Type of media ('image', 'video')
            media_relative_path: Relative path for Instagram public URL (e.g., "images/abc.jpg")
            media_url: Direct public URL for Instagram (e.g., Supabase public URL)
            tags: List of tags (used for YouTube)
            privacy_status: Privacy setting (used for YouTube)

        Returns:
            Dict mapping platform names to their posting results
        """
        youtube_privacy = privacy_status or settings.YOUTUBE_DEFAULT_PRIVACY_STATUS
        results = {}
        for platform in platforms:
            try:
                results[platform] = self.post_to_platform(
                    platform, title, body, media_file_path, media_type,
                    media_relative_path=media_relative_path,
                    media_url=media_url,
                    tags=tags,
                    privacy_status=youtube_privacy,
                    linkedin_account_labels=linkedin_account_labels,
                )
            except Exception as e:
                logger.error(f"Failed to post to {platform}: {str(e)}")
                results[platform] = {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": str(e),
                }
        return results

    def post_to_platform(
        self,
        platform: str,
        title: str,
        body: str,
        media_file_path: Optional[str] = None,
        media_type: Optional[str] = None,
        media_relative_path: Optional[str] = None,
        media_url: Optional[str] = None,
        tags: Optional[list[str]] = None,
        privacy_status: Optional[str] = None,
        linkedin_account_labels: Optional[list[str]] = None,
    ) -> dict:
        """
        Post content to a specific platform.

        Args:
            platform: One of 'linkedin', 'facebook', 'instagram', 'youtube'
            title: Post title
            body: Post body/content
            media_file_path: Full filesystem path to media file (optional)
            media_type: Type of media ('image', 'video')
            media_relative_path: Relative path for Instagram URL
            media_url: Direct public URL for Instagram (overrides constructed URL)
            tags: List of tags (used for YouTube)
            privacy_status: Privacy setting (used for YouTube: 'private', 'unlisted', 'public')

        Returns:
            Dict with posting result from the platform client
        """
        logger.info(
            f"Posting to {platform}: title='{title[:50]}...', "
            f"media={'yes' if media_file_path else 'no'}"
        )

        if platform == "linkedin":
            return self._post_to_linkedin(
                title, body, media_file_path, media_type,
                account_labels=linkedin_account_labels,
            )
        elif platform == "facebook":
            return self.facebook.create_post(title, body, media_file_path, media_type)
        elif platform == "instagram":
            return self.instagram.create_post(
                title, body, media_file_path, media_type,
                media_relative_path=media_relative_path,
                media_url=media_url,
            )
        elif platform == "youtube":
            if not media_file_path:
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": "YouTube requires a video file to upload. Attach a video to your content first.",
                }
            return self.youtube.upload_video(
                video_path=media_file_path,
                title=title,
                description=body,
                tags=tags,
                privacy_status=privacy_status or settings.YOUTUBE_DEFAULT_PRIVACY_STATUS,
            )
        else:
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": f"Unsupported platform: {platform}",
            }

    def _post_to_linkedin(
        self,
        title: str,
        body: str,
        media_file_path: Optional[str] = None,
        media_type: Optional[str] = None,
        account_labels: Optional[list[str]] = None,
    ) -> dict:
        """Post to configured LinkedIn accounts sequentially."""
        if not self.linkedin_accounts:
            return {
                "status": "failed",
                "post_id": None,
                "post_url": None,
                "error_message": "No LinkedIn accounts configured. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID.",
                "accounts": [],
            }

        clients = self.linkedin_accounts
        if account_labels:
            selected = {label.strip().lower() for label in account_labels if label.strip()}
            clients = [
                client for client in self.linkedin_accounts
                if client.account_label.strip().lower() in selected
            ]
            if not clients:
                return {
                    "status": "failed",
                    "post_id": None,
                    "post_url": None,
                    "error_message": "No matching LinkedIn accounts for the selected labels.",
                    "accounts": [],
                }

        account_results = []
        for client in clients:
            result = client.create_post(title, body, media_file_path, media_type)
            account_results.append(
                {
                    "label": client.account_label,
                    "status": result.get("status", "failed"),
                    "post_id": result.get("post_id"),
                    "post_url": result.get("post_url"),
                    "error_message": result.get("error_message"),
                }
            )

        statuses = [a["status"] for a in account_results]
        if all(s == "draft" for s in statuses):
            aggregate_status = "draft"
        elif all(s == "published" for s in statuses):
            aggregate_status = "published"
        elif all(s == "failed" for s in statuses):
            aggregate_status = "failed"
        else:
            aggregate_status = "partial"

        first_success_id = next((a["post_id"] for a in account_results if a["post_id"]), None)
        first_success_url = next((a["post_url"] for a in account_results if a["post_url"]), None)
        error_message = None
        if aggregate_status == "failed":
            errors = [a["error_message"] for a in account_results if a.get("error_message")]
            error_message = "; ".join(errors) if errors else "All LinkedIn accounts failed to post"

        return {
            "status": aggregate_status,
            "post_id": first_success_id,
            "post_url": first_success_url,
            "error_message": error_message,
            "accounts": account_results,
        }

    def check_platform_config(self) -> dict[str, bool]:
        """Check which platforms are configured and ready."""
        return {
            "linkedin": len(self.linkedin_accounts) > 0,
            "facebook": self.facebook.is_configured,
            "instagram": self.instagram.is_configured,
            "youtube": self.youtube.is_configured,
        }


def fetch_connected_account_details() -> dict:
    """
    Resolve human-readable account names for configured platforms (no secrets).
    Used by Settings to confirm live posting targets the correct accounts.
    """
    from app.config import settings

    details: dict = {
        "draft_mode": settings.DRAFT_MODE,
        "facebook": None,
        "instagram": None,
        "youtube": None,
    }

    graph_version = (settings.META_GRAPH_API_VERSION or "v21.0").strip()
    graph_url = f"https://graph.facebook.com/{graph_version}"
    page_id = (settings.FACEBOOK_PAGE_ID or "").strip()
    page_token = (settings.FACEBOOK_PAGE_ACCESS_TOKEN or "").strip()

    if page_id and page_token:
        try:
            page_resp = requests.get(
                f"{graph_url}/{page_id}",
                params={
                    "fields": "name,id,instagram_business_account{id,username,name}",
                    "access_token": page_token,
                },
                timeout=15,
            )
            if page_resp.ok:
                page_data = page_resp.json()
                details["facebook"] = {
                    "id": page_data.get("id", page_id),
                    "name": page_data.get("name"),
                    "configured_id": page_id,
                    "id_matches": str(page_data.get("id", "")) == page_id,
                }
                ig_data = page_data.get("instagram_business_account") or {}
                if isinstance(ig_data, dict) and ig_data.get("id"):
                    configured_ig = (settings.INSTAGRAM_ACCOUNT_ID or "").strip()
                    details["instagram"] = {
                        "id": ig_data.get("id"),
                        "username": ig_data.get("username"),
                        "name": ig_data.get("name"),
                        "configured_id": configured_ig,
                        "id_matches": str(ig_data.get("id", "")) == configured_ig
                        if configured_ig
                        else None,
                    }
            else:
                details["facebook"] = {
                    "id": page_id,
                    "name": None,
                    "error": "Could not verify Facebook Page token",
                }
        except requests.RequestException as exc:
            logger.warning(f"Facebook account lookup failed: {exc}")
            details["facebook"] = {"id": page_id, "name": None, "error": str(exc)}

    yt_client = YouTubeClient(draft_mode=False)
    if yt_client.is_configured:
        try:
            token = yt_client._refresh_access_token()
            if token:
                ch_resp = requests.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "snippet", "mine": "true"},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )
                if ch_resp.ok:
                    items = ch_resp.json().get("items", [])
                    if items:
                        channel = items[0]
                        channel_id = channel.get("id", "")
                        snippet = channel.get("snippet", {})
                        configured_id = (settings.YOUTUBE_CHANNEL_ID or "").strip()
                        details["youtube"] = {
                            "id": channel_id,
                            "name": snippet.get("title"),
                            "custom_url": snippet.get("customUrl"),
                            "configured_id": configured_id,
                            "id_matches": configured_id == channel_id if configured_id else None,
                        }
                else:
                    details["youtube"] = {"error": "Could not verify YouTube OAuth token"}
            else:
                details["youtube"] = {"error": "YouTube refresh token invalid or expired"}
        except requests.RequestException as exc:
            logger.warning(f"YouTube account lookup failed: {exc}")
            details["youtube"] = {"error": str(exc)}

    return details
