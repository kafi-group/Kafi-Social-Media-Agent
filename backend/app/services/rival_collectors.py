"""
Rival data collectors (Rival Review).

Pulls free, public competitor signals:
- YouTube: public channel stats + recent video engagement via the YouTube Data
  API v3 (needs only a free API key, separate from the upload OAuth creds).
- Instagram: a competitor's public follower count + recent post engagement via
  the Meta Graph `business_discovery` edge (reuses the existing page token; the
  rival must have an IG Business/Creator account).
- Website: latest blog/news posts via RSS (feedparser), with a light HTML
  fallback to auto-discover a feed.

Every collector is defensive: any failure is captured and returned as a status
string instead of raising, so one broken source never breaks a whole refresh.
Returned shape per platform:
    {"platform", "status", "metrics", "recent_items", "message"}
status is one of: ok | not_configured | unavailable | error
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urljoin

import requests

from app.config import settings
from app.utils.logger import logger

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

_USER_AGENT = "Mozilla/5.0 (compatible; KafiRivalReview/1.0)"

# Many corporate sites reject non-browser User-Agents with a 403, so we present
# a realistic browser fingerprint when fetching public pages.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _result(
    platform: str,
    status: str,
    metrics: Optional[dict] = None,
    recent_items: Optional[list] = None,
    message: Optional[str] = None,
) -> dict:
    return {
        "platform": platform,
        "status": status,
        "metrics": metrics or {},
        "recent_items": recent_items or [],
        "message": message,
    }


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------

def youtube_auth_mode() -> str | None:
    """How rival YouTube stats are authenticated: api_key, oauth, or None."""
    if settings.YOUTUBE_DATA_API_KEY.strip():
        return "api_key"
    if (
        settings.YOUTUBE_CLIENT_ID.strip()
        and settings.YOUTUBE_CLIENT_SECRET.strip()
        and settings.YOUTUBE_REFRESH_TOKEN.strip()
    ):
        return "oauth"
    return None


def youtube_is_configured() -> bool:
    return youtube_auth_mode() is not None


def _youtube_api_auth() -> tuple[dict[str, str], dict[str, str]]:
    """
    Return (query_params, headers) for YouTube Data API v3.

    Prefers YOUTUBE_DATA_API_KEY (free public stats key). Falls back to the
    existing YouTube upload OAuth credentials when the data key is not set.
    """
    api_key = settings.YOUTUBE_DATA_API_KEY.strip()
    if api_key:
        return {"key": api_key}, {}

    from app.services.social_publisher import YouTubeClient

    client = YouTubeClient()
    if not client.is_configured:
        return {}, {}

    headers = client._get_headers()
    if headers.get("Authorization"):
        return {}, headers
    return {}, {}


def collect_youtube(rival) -> dict:
    """Public channel stats + recent video engagement (YouTube Data API v3)."""
    channel_id = (rival.youtube_channel_id or "").strip()
    handle = (rival.youtube_handle or "").strip()
    auth_params, auth_headers = _youtube_api_auth()

    if not channel_id and not handle:
        return _result(
            "youtube", "not_configured",
            message="No YouTube channel ID or handle set for this rival.",
        )
    if not auth_params.get("key") and not auth_headers.get("Authorization"):
        return _result(
            "youtube", "not_configured",
            message=(
                "Set YOUTUBE_DATA_API_KEY in backend .env, or configure YouTube OAuth "
                "(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN)."
            ),
        )

    try:
        params = {"part": "snippet,statistics,contentDetails", **auth_params}
        if channel_id:
            params["id"] = channel_id
        else:
            params["forHandle"] = handle if handle.startswith("@") else f"@{handle}"

        resp = requests.get(
            f"{YOUTUBE_API_BASE}/channels",
            params=params,
            headers=auth_headers,
            timeout=settings.SCRAPER_TIMEOUT,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return _result(
                "youtube", "unavailable",
                message="YouTube channel not found (check the handle/ID).",
            )

        channel = items[0]
        stats = channel.get("statistics", {})
        snippet = channel.get("snippet", {})
        uploads_playlist = (
            channel.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )

        metrics = {
            "channel_title": snippet.get("title"),
            "subscribers": _to_int(stats.get("subscriberCount")),
            "total_views": _to_int(stats.get("viewCount")),
            "video_count": _to_int(stats.get("videoCount")),
        }

        recent_items = (
            _youtube_recent_videos(uploads_playlist, auth_params, auth_headers)
            if uploads_playlist
            else []
        )
        if recent_items:
            metrics["recent_avg_views"] = round(
                sum(v.get("views", 0) for v in recent_items) / len(recent_items)
            )
            metrics["recent_avg_engagement"] = round(
                sum(v.get("likes", 0) + v.get("comments", 0) for v in recent_items)
                / len(recent_items)
            )

        return _result("youtube", "ok", metrics=metrics, recent_items=recent_items)

    except requests.exceptions.RequestException as exc:
        logger.error(f"YouTube rival collection failed: {exc}")
        return _result("youtube", "error", message=f"YouTube request failed: {exc}")
    except Exception as exc:  # noqa: BLE001 - never let one source break a refresh
        logger.error(f"YouTube rival collection failed: {exc}")
        return _result("youtube", "error", message=str(exc))


def _youtube_recent_videos(
    uploads_playlist: str,
    auth_params: dict[str, str],
    auth_headers: dict[str, str],
    max_results: int = 5,
) -> list:
    """Fetch the most recent uploads and their per-video engagement."""
    pl = requests.get(
        f"{YOUTUBE_API_BASE}/playlistItems",
        params={
            "part": "contentDetails",
            "playlistId": uploads_playlist,
            "maxResults": max_results,
            **auth_params,
        },
        headers=auth_headers,
        timeout=settings.SCRAPER_TIMEOUT,
    )
    pl.raise_for_status()
    video_ids = [
        it["contentDetails"]["videoId"]
        for it in pl.json().get("items", [])
        if it.get("contentDetails", {}).get("videoId")
    ]
    if not video_ids:
        return []

    vresp = requests.get(
        f"{YOUTUBE_API_BASE}/videos",
        params={
            "part": "snippet,statistics",
            "id": ",".join(video_ids),
            **auth_params,
        },
        headers=auth_headers,
        timeout=settings.SCRAPER_TIMEOUT,
    )
    vresp.raise_for_status()

    videos = []
    for v in vresp.json().get("items", []):
        s = v.get("statistics", {})
        sn = v.get("snippet", {})
        videos.append({
            "title": sn.get("title"),
            "published_at": sn.get("publishedAt"),
            "url": f"https://www.youtube.com/watch?v={v.get('id')}",
            "views": _to_int(s.get("viewCount")),
            "likes": _to_int(s.get("likeCount")),
            "comments": _to_int(s.get("commentCount")),
        })
    return videos


# ---------------------------------------------------------------------------
# Instagram (Meta Graph business_discovery)
# ---------------------------------------------------------------------------

def instagram_is_configured() -> bool:
    return bool(
        settings.INSTAGRAM_ACCOUNT_ID.strip()
        and settings.FACEBOOK_PAGE_ACCESS_TOKEN.strip()
    )


def _instagram_auth_error_message(err: dict) -> str | None:
    """
    Return a reconnect hint when Meta rejects the page token / app pairing.
    These failures affect ALL rivals until OAuth is fixed — not individual usernames.
    """
    code = err.get("code")
    msg = (err.get("message") or "").strip()
    lower = msg.lower()

    auth_signals = (
        "cannot call api for app",
        "invalid oauth",
        "error validating access token",
        "session has expired",
        "access token has expired",
        "permission denied",
        "requires facebook login",
        "pages_read_engagement",
        "instagram_basic",
        "instagram_manage_insights",
    )
    if code in (190, 102, 200, 10) or any(s in lower for s in auth_signals):
        return (
            "Meta Instagram token/app auth failed. Reconnect via /api/v1/auth/meta "
            f"(need instagram_basic + instagram_manage_insights + pages_read_engagement). "
            f"Meta said: {msg or 'OAuth/permission error'}"
        )
    return None


def probe_instagram_auth(sample_username: str = "shanfoodsglobal") -> dict:
    """
    Lightweight health check for Rival Review Instagram config.
    Uses business_discovery against a known public professional account.
    """
    ig_user_id = settings.INSTAGRAM_ACCOUNT_ID.strip()
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN.strip()
    version = settings.META_GRAPH_API_VERSION.strip() or "v18.0"

    if not ig_user_id or not token:
        return {
            "ok": False,
            "configured": False,
            "message": (
                "Set INSTAGRAM_ACCOUNT_ID and FACEBOOK_PAGE_ACCESS_TOKEN in backend .env, "
                "then reconnect Meta OAuth."
            ),
        }

    username = (sample_username or "instagram").strip().lstrip("@")
    fields = f"business_discovery.username({username}){{followers_count,media_count}}"
    try:
        resp = requests.get(
            f"https://graph.facebook.com/{version}/{ig_user_id}",
            params={"fields": fields, "access_token": token},
            timeout=min(15, settings.SCRAPER_TIMEOUT),
        )
        data = resp.json() if resp.content else {}
        if resp.ok and isinstance(data, dict) and data.get("business_discovery"):
            return {
                "ok": True,
                "configured": True,
                "message": "Ready — Instagram Business Discovery can fetch rival stats.",
            }

        err = data.get("error", {}) if isinstance(data, dict) else {}
        auth_msg = _instagram_auth_error_message(err) if isinstance(err, dict) else None
        raw = err.get("message") if isinstance(err, dict) else None
        return {
            "ok": False,
            "configured": True,
            "message": auth_msg
            or (
                f"Instagram probe failed: {raw}"
                if raw
                else "Instagram Business Discovery probe failed."
            ),
        }
    except requests.exceptions.RequestException as exc:
        return {
            "ok": False,
            "configured": True,
            "message": f"Instagram probe request failed: {exc}",
        }


def collect_instagram(rival) -> dict:
    """Public IG business/creator stats via Meta Graph business_discovery."""
    username = (rival.instagram_username or "").strip().lstrip("@")
    ig_user_id = settings.INSTAGRAM_ACCOUNT_ID.strip()
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN.strip()
    version = settings.META_GRAPH_API_VERSION.strip() or "v18.0"

    if not username:
        return _result(
            "instagram", "not_configured",
            message="No Instagram username set for this rival.",
        )
    if not ig_user_id or not token:
        return _result(
            "instagram", "not_configured",
            message=(
                "Instagram Business Discovery needs INSTAGRAM_ACCOUNT_ID and "
                "FACEBOOK_PAGE_ACCESS_TOKEN to be configured."
            ),
        )

    fields = (
        f"business_discovery.username({username})"
        "{followers_count,media_count,"
        "media.limit(6){like_count,comments_count,caption,timestamp,permalink,media_type}}"
    )
    try:
        resp = requests.get(
            f"https://graph.facebook.com/{version}/{ig_user_id}",
            params={"fields": fields, "access_token": token},
            timeout=settings.SCRAPER_TIMEOUT,
        )
        data = resp.json()
        if not resp.ok:
            err = data.get("error", {}) if isinstance(data, dict) else {}
            auth_msg = _instagram_auth_error_message(err) if isinstance(err, dict) else None
            if auth_msg:
                return _result("instagram", "error", message=auth_msg)
            msg = err.get("message", "Instagram Business Discovery request failed.")
            # Rival isn't a discoverable Business/Creator account, or username is wrong.
            return _result("instagram", "unavailable", message=msg)

        bd = data.get("business_discovery", {})
        if not bd:
            return _result(
                "instagram",
                "unavailable",
                message=(
                    f"No Instagram business_discovery data for @{username}. "
                    "Confirm the username is a public Business/Creator account."
                ),
            )

        media = bd.get("media", {}).get("data", [])
        recent_items = [{
            "caption": (m.get("caption") or "")[:200],
            "likes": _to_int(m.get("like_count")),
            "comments": _to_int(m.get("comments_count")),
            "url": m.get("permalink"),
            "timestamp": m.get("timestamp"),
            "media_type": m.get("media_type"),
        } for m in media]

        metrics = {
            "followers": _to_int(bd.get("followers_count")),
            "media_count": _to_int(bd.get("media_count")),
        }
        if recent_items:
            metrics["recent_avg_engagement"] = round(
                sum(i["likes"] + i["comments"] for i in recent_items) / len(recent_items)
            )

        return _result("instagram", "ok", metrics=metrics, recent_items=recent_items)

    except requests.exceptions.RequestException as exc:
        logger.error(f"Instagram rival collection failed: {exc}")
        return _result("instagram", "error", message=f"Instagram request failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Instagram rival collection failed: {exc}")
        return _result("instagram", "error", message=str(exc))


# ---------------------------------------------------------------------------
# Website / RSS
# ---------------------------------------------------------------------------

def collect_website(rival) -> dict:
    """Latest blog/news via RSS when available, otherwise scrape homepage highlights."""
    rss_url = (rival.rss_url or "").strip()
    website = (rival.website or "").strip()

    if not rss_url and not website:
        return _result(
            "website", "not_configured",
            message="No website or RSS feed set for this rival.",
        )

    feed_url = rss_url or _discover_feed(website)

    # 1) Preferred path: a real RSS/Atom feed.
    if feed_url:
        feed_result = _collect_feed(feed_url)
        if feed_result["status"] == "ok":
            return feed_result
        # Feed empty/unreachable -> fall through to homepage scrape if we have a site.

    # 2) Fallback: scrape the homepage for a title + latest headlines.
    if website:
        return _scrape_homepage(website)

    return _result(
        "website", "not_configured",
        message="No RSS feed found and no website to scrape.",
    )


def _collect_feed(feed_url: str) -> dict:
    """Parse an RSS/Atom feed into recent items."""
    try:
        import feedparser
        from bs4 import BeautifulSoup

        parsed = feedparser.parse(feed_url)
        entries = parsed.entries[:6]
        recent_items = []
        for e in entries:
            summary_html = e.get("summary", "")
            summary = (
                BeautifulSoup(summary_html, "html.parser").get_text()[:200]
                if summary_html
                else None
            )
            recent_items.append({
                "title": e.get("title"),
                "url": e.get("link"),
                "published": e.get("published", e.get("updated")),
                "summary": summary,
            })

        metrics = {"source": "rss", "feed_url": feed_url, "post_count": len(parsed.entries)}
        if not recent_items:
            return _result(
                "website", "unavailable", metrics=metrics,
                message="Feed reachable but returned no entries.",
            )
        return _result("website", "ok", metrics=metrics, recent_items=recent_items)

    except Exception as exc:  # noqa: BLE001
        logger.info(f"RSS parse failed for {feed_url}: {exc}")
        return _result("website", "error", message=f"RSS parse failed: {exc}")


def _scrape_homepage(website: str) -> dict:
    """Best-effort: pull the page title + latest headlines from a homepage."""
    try:
        from bs4 import BeautifulSoup

        resp = requests.get(
            website,
            timeout=settings.SCRAPER_TIMEOUT,
            headers=_BROWSER_HEADERS,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title = soup.title.get_text(strip=True) if soup.title else None
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()

        desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", attrs={"property": "og:description"}
        )
        description = (
            desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else None
        )

        # Collect candidate headlines from heading tags (news/products/sections).
        headlines = []
        seen = set()
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = " ".join(tag.get_text(" ", strip=True).split())
            key = text.lower()
            if 6 <= len(text) <= 140 and key not in seen:
                seen.add(key)
                headlines.append(text)
            if len(headlines) >= 6:
                break

        recent_items = [{"title": h} for h in headlines]
        metrics = {"source": "homepage", "title": title, "description": description}

        if not title and not recent_items:
            return _result(
                "website", "unavailable",
                message="Homepage reachable but no readable content found.",
            )
        return _result(
            "website", "ok", metrics=metrics, recent_items=recent_items,
            message="No RSS feed; showing homepage highlights.",
        )

    except requests.exceptions.RequestException as exc:
        logger.info(f"Homepage scrape failed for {website}: {exc}")
        return _result("website", "error", message=f"Website request failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.info(f"Homepage scrape failed for {website}: {exc}")
        return _result("website", "error", message=str(exc))


def _discover_feed(website: str) -> Optional[str]:
    """Best-effort: look for an RSS/Atom <link> in the site's homepage HTML."""
    if not website:
        return None
    try:
        from bs4 import BeautifulSoup

        resp = requests.get(
            website,
            timeout=settings.SCRAPER_TIMEOUT,
            headers=_BROWSER_HEADERS,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        link = soup.find(
            "link",
            attrs={"type": ["application/rss+xml", "application/atom+xml"]},
        )
        if link and link.get("href"):
            return urljoin(website, link["href"])
    except Exception as exc:  # noqa: BLE001
        logger.info(f"Feed discovery failed for {website}: {exc}")
    return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def collect_all(rival) -> list[dict]:
    """Run every collector for a rival and return per-platform results."""
    return [
        collect_youtube(rival),
        collect_instagram(rival),
        collect_website(rival),
    ]
