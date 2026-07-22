"""
Meta (Facebook + Instagram) OAuth 2.0 re-authorization route.

Exchanges the login code for a long-lived user token, derives a non-expiring
Page access token, and auto-saves both into runtime settings + DB + .env so
analytics keep working without manual paste/restart.

Usage (live Railway):
  1. Set FACEBOOK_APP_ID / FACEBOOK_APP_SECRET on Railway
  2. Add FACEBOOK_REDIRECT_URI (Railway callback) in Meta App → Valid OAuth Redirect URIs
  3. Visit https://kafi-social-agent.up.railway.app/api/v1/auth/meta
  4. Approve permissions — tokens are saved automatically
"""

from datetime import datetime
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import public_api_url, settings
from app.services.meta_token_service import (
    debug_token,
    exchange_long_lived_user_token,
    fetch_page_access_token,
    persist_meta_tokens,
    refresh_meta_tokens,
    resolve_instagram_account_id,
)
from app.services.token_store import credential_status
from app.utils.logger import logger

router = APIRouter()

FACEBOOK_AUTH_URL = "https://www.facebook.com/v21.0/dialog/oauth"
FACEBOOK_TOKEN_URL = "https://graph.facebook.com/oauth/access_token"

REQUIRED_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_read_user_content",
    "read_insights",
    "instagram_basic",
    "instagram_manage_insights",
    "instagram_content_publish",
    "pages_manage_posts",
    "pages_manage_engagement",
    # Required for Pages owned under Meta Business Manager; without it
    # /me/accounts often returns [] even when the user is a Page admin.
    "business_management",
]


def _list_managed_pages(long_lived_user_token: str) -> list[dict]:
    graph_url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}"
    pages: list[dict] = []
    seen: set[str] = set()

    def _extend(items: list) -> None:
        for page in items:
            page_id = str(page.get("id") or "").strip()
            if not page_id or page_id in seen:
                continue
            seen.add(page_id)
            pages.append(page)

    try:
        accounts_resp = requests.get(
            f"{graph_url}/me/accounts",
            params={
                "fields": "id,name,access_token,instagram_business_account{id,username,name}",
                "access_token": long_lived_user_token,
                "limit": 50,
            },
            timeout=30,
        )
        if accounts_resp.ok:
            _extend(accounts_resp.json().get("data", []) or [])
        else:
            logger.warning(f"me/accounts listing failed: {accounts_resp.text[:300]}")
    except requests.RequestException as exc:
        logger.warning(f"me/accounts listing failed: {exc}")

    # Business-assigned Pages often missing from /me/accounts without this path.
    try:
        assigned_resp = requests.get(
            f"{graph_url}/me/assigned_pages",
            params={
                "fields": "id,name,access_token,instagram_business_account{id,username,name}",
                "access_token": long_lived_user_token,
                "limit": 50,
            },
            timeout=30,
        )
        if assigned_resp.ok:
            _extend(assigned_resp.json().get("data", []) or [])
        else:
            logger.info(f"me/assigned_pages unavailable: {assigned_resp.text[:200]}")
    except requests.RequestException as exc:
        logger.info(f"me/assigned_pages listing failed: {exc}")

    return pages


def _format_managed_pages_html(pages: list[dict], current_page_id: str) -> str:
    configured = (current_page_id or "").strip()
    if not pages:
        return f"""
          <h3 style="color:#b45309">No Facebook Pages returned for this login</h3>
          <p>
            Meta did <strong>not</strong> return any Pages for the Facebook user you just
            authorized. The ID below is only what is <strong>already saved on the server</strong>
            (often an old Page) — it is <strong>not</strong> a newly connected Page:
          </p>
          <p><code>FACEBOOK_PAGE_ID={configured or "(not set)"}</code></p>
          <ol>
            <li>Log into Facebook as an <strong>Admin</strong> of the Kafi Essence Page</li>
            <li>During the permission screen, <strong>select the Kafi Essence Page</strong> (and its IG)</li>
            <li>Approve <strong>business_management</strong> if Meta asks (needed for Business-owned Pages)</li>
            <li>Set Railway <code>FACEBOOK_PAGE_ID</code> to the real Kafi Essence Page ID, then reconnect</li>
          </ol>
        """

    rows = []
    for page in pages:
        page_id = str(page.get("id", ""))
        is_current = page_id == configured
        ig = page.get("instagram_business_account") or {}
        ig_line = ""
        if isinstance(ig, dict) and ig.get("id"):
            ig_user = ig.get("username", "")
            ig_line = (
                f"<br>Instagram: @{ig_user} "
                f"(<code>INSTAGRAM_ACCOUNT_ID={ig.get('id')}</code>)"
            )
        marker = " <strong>← currently configured on server</strong>" if is_current else ""
        rows.append(
            f"<li><strong>{page.get('name', 'Page')}</strong>{marker}<br>"
            f"<code>FACEBOOK_PAGE_ID={page_id}</code>{ig_line}</li>"
        )
    return f"""
          <h3>Facebook Pages Meta returned for THIS login</h3>
          <p>
            Pick the <strong>Kafi Essence</strong> row. Put that ID in Railway
            <code>FACEBOOK_PAGE_ID</code>, then run <code>/api/v1/auth/meta</code> again.
            The old configured value on the server is
            <code>{configured or "(not set)"}</code> — ignore it unless it matches Kafi Essence.
          </p>
          <ul>{''.join(rows)}</ul>
    """

def _format_expiry(debug_data: dict) -> str:
    expires_at = debug_data.get("expires_at")
    if expires_at in (None, 0):
        return "does not expire (Page token)"
    try:
        return datetime.utcfromtimestamp(int(expires_at)).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OSError):
        return str(expires_at)


@router.get("/auth/meta/status")
async def meta_auth_status():
    """Show Meta token health (no secrets)."""
    page_token = (settings.FACEBOOK_PAGE_ACCESS_TOKEN or "").strip()
    user_token = (settings.FACEBOOK_USER_ACCESS_TOKEN or "").strip()
    page_debug = debug_token(page_token) if page_token else {}
    user_debug = debug_token(user_token) if user_token else {}
    return {
        "configured": bool(page_token and settings.FACEBOOK_PAGE_ID),
        "page_id": settings.FACEBOOK_PAGE_ID or None,
        "instagram_account_id": settings.INSTAGRAM_ACCOUNT_ID or None,
        "has_page_token": bool(page_token),
        "has_user_token": bool(user_token),
        "page_token_valid": page_debug.get("is_valid"),
        "page_token_expires": _format_expiry(page_debug) if page_debug else None,
        "user_token_valid": user_debug.get("is_valid"),
        "user_token_expires": _format_expiry(user_debug) if user_debug else None,
        "auto_refresh_ready": bool(user_token),
        "stored": credential_status(
            [
                "FACEBOOK_PAGE_ACCESS_TOKEN",
                "FACEBOOK_USER_ACCESS_TOKEN",
                "INSTAGRAM_ACCOUNT_ID",
            ]
        ),
        "auth_url": public_api_url("/api/v1/auth/meta"),
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
        "message": (
            "Meta tokens are ready; the scheduler will keep the user token extended."
            if page_token and user_token
            else (
                f"Page token present. Re-authorize once via {public_api_url('/api/v1/auth/meta')} "
                "to enable automatic renewal (stores FACEBOOK_USER_ACCESS_TOKEN)."
                if page_token
                else f"Visit {public_api_url('/api/v1/auth/meta')} to connect Facebook + Instagram."
            )
        ),
    }


@router.post("/auth/meta/refresh")
async def meta_auth_refresh():
    """Manually trigger Meta token refresh / Page token re-derivation."""
    return refresh_meta_tokens(force=True)


@router.get("/auth/meta")
async def meta_auth_start():
    """Start Meta OAuth — redirects to Facebook login/consent screen."""
    if not settings.FACEBOOK_APP_ID or not settings.FACEBOOK_APP_SECRET:
        raise HTTPException(
            status_code=400,
            detail=(
                "Set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in backend/.env first. "
                "Find them in your Meta App Dashboard under App Settings → Basic."
            ),
        )

    params = {
        "client_id": settings.FACEBOOK_APP_ID,
        "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
        "scope": ",".join(REQUIRED_SCOPES),
        "response_type": "code",
        "auth_type": "rerequest",
    }
    auth_url = f"{FACEBOOK_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/auth/meta/callback", response_class=HTMLResponse)
async def meta_auth_callback(
    code: str = Query(default=""),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
):
    """Exchange Facebook OAuth code and auto-save long-lived tokens."""
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Facebook OAuth error: {error} — {error_description}",
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    try:
        token_resp = requests.get(
            FACEBOOK_TOKEN_URL,
            params={
                "client_id": settings.FACEBOOK_APP_ID,
                "client_secret": settings.FACEBOOK_APP_SECRET,
                "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
                "code": code,
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error(f"Meta OAuth token exchange failed: {exc}")
        raise HTTPException(status_code=502, detail="Failed to contact Facebook OAuth.") from exc

    if not token_resp.ok:
        raise HTTPException(
            status_code=400,
            detail=f"Facebook token exchange error: {token_resp.text[:300]}",
        )

    short_lived_token = token_resp.json().get("access_token", "")
    if not short_lived_token:
        raise HTTPException(status_code=400, detail="Facebook did not return an access token.")

    try:
        long_lived_user_token, _ = exchange_long_lived_user_token(short_lived_token)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    managed_pages = _list_managed_pages(long_lived_user_token)
    pages_html = _format_managed_pages_html(
        managed_pages, settings.FACEBOOK_PAGE_ID or ""
    )

    page_token, page_name, page_token_note = fetch_page_access_token(
        long_lived_user_token,
        settings.FACEBOOK_PAGE_ID,
    )

    if page_token:
        token_to_use = page_token
        token_label = "Page access token (non-expiring — saved automatically)"
        token_note = (
            f"Page: <strong>{page_name}</strong>"
            if page_name
            else "Page access token resolved successfully."
        )
        if page_token_note:
            token_note += f"<br><span style='color:#b45309'>{page_token_note}</span>"
    else:
        token_to_use = long_lived_user_token
        token_label = "Long-lived USER token (~60 days — Page token missing)"
        token_note = (
            (page_token_note or "Could not fetch a Page token.")
            + "<br><strong>This does not mean Meta connected the old Page.</strong> "
            "It means the server still has an old <code>FACEBOOK_PAGE_ID</code>, and "
            "this Facebook login did not return a usable Page token for Kafi Essence. "
            "See the Pages section below, update Railway, then reconnect."
        )

    # If we fell back to a different managed page, adopt its ID for IG lookup + persist.
    resolved_page_id = (settings.FACEBOOK_PAGE_ID or "").strip()
    if page_token and managed_pages:
        configured = resolved_page_id
        matched = next(
            (
                str(p.get("id") or "").strip()
                for p in managed_pages
                if (p.get("access_token") or "").strip() == page_token
                or (configured and str(p.get("id")) == configured)
            ),
            "",
        )
        if not matched:
            # Token came from fallback page — prefer that page's id from the note/name match
            for p in managed_pages:
                if (p.get("access_token") or "").strip() and str(p.get("name")) == page_name:
                    matched = str(p.get("id") or "").strip()
                    break
            if not matched:
                for p in managed_pages:
                    if (p.get("access_token") or "").strip():
                        matched = str(p.get("id") or "").strip()
                        break
        if matched:
            resolved_page_id = matched
            settings.FACEBOOK_PAGE_ID = matched

    ig_id = ""
    if page_token:
        ig_id = resolve_instagram_account_id(page_token, resolved_page_id)

    saved_keys = persist_meta_tokens(
        page_token=page_token or "",
        user_token=long_lived_user_token,
        page_id=resolved_page_id if page_token else "",
        instagram_account_id=ig_id,
    )
    # If only the user token could be obtained, still persist it for later refresh.
    if not page_token and long_lived_user_token:
        saved_keys = persist_meta_tokens(user_token=long_lived_user_token)

    debug_data = debug_token(token_to_use)
    expiry_text = _format_expiry(debug_data)
    token_type = debug_data.get("type", "unknown")
    is_valid = debug_data.get("is_valid", "unknown")
    scopes = ", ".join(debug_data.get("scopes", []) or [])

    ig_block = ""
    if ig_id:
        ig_block = f"""
          <h3>Instagram Business Account</h3>
          <p>Linked account ID <code>{ig_id}</code> was saved automatically.</p>
        """

    saved_note = (
        f"<p style='background:#ecfdf5;border:1px solid #6ee7b7;padding:1rem;border-radius:6px'>"
        f"<strong>Saved automatically:</strong> {', '.join(saved_keys) or 'none'}. "
        f"No .env paste or backend restart needed. The daily scheduler will keep "
        f"the user token extended so Facebook &amp; Instagram analytics stay online."
        f"</p>"
        if saved_keys
        else "<p style='color:#b45309'>Tokens were obtained but could not be persisted. "
        "Check backend logs and database connectivity.</p>"
    )

    return HTMLResponse(
        content=f"""
        <html><body style="font-family:sans-serif;padding:2rem;max-width:720px">
          <h2>Meta (Facebook + Instagram) authorization successful</h2>
          {saved_note}
          <p>{token_note}</p>
          <p><strong>{token_label}</strong></p>
          <ul>
            <li>Valid: <strong>{is_valid}</strong></li>
            <li>Token type: <strong>{token_type}</strong></li>
            <li>Expires: <strong>{expiry_text}</strong></li>
          </ul>
          {f"<p>Scopes: {scopes}</p>" if scopes else ""}
          {ig_block}
          {pages_html}
          <h3>What happens next</h3>
          <ol>
            <li>Open Dashboard → Analytics — Facebook and Instagram should show Connected</li>
            <li>Check status anytime at <code>/api/v1/auth/meta/status</code></li>
            <li>The backend refreshes Meta tokens daily in the background</li>
          </ol>
          <p style="color:#666;font-size:0.9rem">
            Do <strong>not</strong> paste Graph API Explorer tokens — they expire in 1–2 hours.
            Always use this <code>/api/v1/auth/meta</code> flow.
          </p>
        </body></html>
        """
    )
