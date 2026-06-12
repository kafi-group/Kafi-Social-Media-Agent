"""
Meta (Facebook + Instagram) OAuth 2.0 re-authorization route.

Generates a long-lived Page access token that never expires (as long as the
user does not revoke app access). Use this when FACEBOOK_PAGE_ACCESS_TOKEN
expires and analytics / posting stop working.

Usage:
  1. Add FACEBOOK_APP_ID and FACEBOOK_APP_SECRET to backend/.env
     (find them in your Meta App Dashboard under App Settings → Basic)
  2. Add the callback URI to your app's Valid OAuth Redirect URIs:
     http://localhost:8000/api/v1/auth/meta/callback
  3. Visit http://localhost:8000/api/v1/auth/meta while the backend is running
  4. Log in and approve permissions
  5. Copy the new token from the success page into FACEBOOK_PAGE_ACCESS_TOKEN
"""

from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.utils.logger import logger

router = APIRouter()

FACEBOOK_AUTH_URL = "https://www.facebook.com/v21.0/dialog/oauth"
FACEBOOK_TOKEN_URL = "https://graph.facebook.com/oauth/access_token"
FACEBOOK_DEBUG_TOKEN_URL = "https://graph.facebook.com/debug_token"

REQUIRED_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_read_user_content",
    "read_insights",
    "instagram_basic",
    "instagram_manage_insights",
    "pages_manage_posts",
    "pages_manage_engagement",
]


def _debug_token_info(access_token: str) -> dict:
    """Return Meta debug_token payload for the given token (expiry, type, scopes)."""
    if not access_token or not settings.FACEBOOK_APP_ID or not settings.FACEBOOK_APP_SECRET:
        return {}
    try:
        resp = requests.get(
            FACEBOOK_DEBUG_TOKEN_URL,
            params={
                "input_token": access_token,
                "access_token": f"{settings.FACEBOOK_APP_ID}|{settings.FACEBOOK_APP_SECRET}",
            },
            timeout=20,
        )
        if resp.ok:
            return resp.json().get("data", {}) or {}
    except requests.RequestException as exc:
        logger.warning(f"Meta debug_token failed: {exc}")
    return {}


def _fetch_page_access_token(long_lived_user_token: str, page_id: str) -> tuple[str, str, str]:
    """
    Resolve a Page access token from a long-lived user token.

    Returns (token, page_name, note). Page tokens derived from long-lived user
    tokens do not expire unless app access is revoked.
    """
    graph_url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}"
    page_id = page_id.strip()

    # Preferred: direct page lookup when FACEBOOK_PAGE_ID is configured.
    if page_id:
        try:
            page_resp = requests.get(
                f"{graph_url}/{page_id}",
                params={
                    "fields": "access_token,name",
                    "access_token": long_lived_user_token,
                },
                timeout=30,
            )
            if page_resp.ok:
                page_data = page_resp.json()
                token = page_data.get("access_token", "")
                if token:
                    return token, page_data.get("name", "your page"), ""
            logger.warning(f"Direct page token fetch failed: {page_resp.text[:200]}")
        except requests.RequestException as exc:
            logger.warning(f"Direct page token fetch error: {exc}")

    # Fallback: list managed pages and match by id.
    try:
        accounts_resp = requests.get(
            f"{graph_url}/me/accounts",
            params={
                "fields": "id,name,access_token",
                "access_token": long_lived_user_token,
            },
            timeout=30,
        )
        if accounts_resp.ok:
            for page in accounts_resp.json().get("data", []):
                if page_id and str(page.get("id")) != page_id:
                    continue
                token = page.get("access_token", "")
                if token:
                    return token, page.get("name", "your page"), ""
            if page_id:
                return (
                    "",
                    "",
                    f"No managed page matched FACEBOOK_PAGE_ID={page_id}. "
                    "Confirm you are an admin of that page.",
                )
    except requests.RequestException as exc:
        logger.warning(f"me/accounts page token fetch error: {exc}")

    return "", "", "Could not resolve a Page access token from your Facebook login."


def _format_expiry(debug_data: dict) -> str:
    expires_at = debug_data.get("expires_at")
    if expires_at in (None, 0):
        return "does not expire (Page token)"
    try:
        from datetime import datetime

        return datetime.utcfromtimestamp(int(expires_at)).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OSError):
        return str(expires_at)


@router.get("/auth/meta")
async def meta_auth_start():
    """
    Start Meta OAuth — redirects to Facebook login/consent screen.
    Requires FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in .env.
    """
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
    """
    Exchange Facebook OAuth code for a long-lived Page access token.
    Displays the new token so you can paste it into .env.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Facebook OAuth error: {error} — {error_description}",
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    # Step 1: Exchange code for a short-lived user access token
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

    # Step 2: Exchange for a long-lived user token (valid ~60 days)
    try:
        ll_resp = requests.get(
            FACEBOOK_TOKEN_URL,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.FACEBOOK_APP_ID,
                "client_secret": settings.FACEBOOK_APP_SECRET,
                "fb_exchange_token": short_lived_token,
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error(f"Meta long-lived token exchange failed: {exc}")
        raise HTTPException(status_code=502, detail="Failed to get long-lived token.") from exc

    if not ll_resp.ok:
        raise HTTPException(
            status_code=400,
            detail=f"Long-lived token exchange error: {ll_resp.text[:300]}",
        )
    long_lived_user_token = ll_resp.json().get("access_token", "")

    # Step 3: Get a never-expiring Page access token (required for FB + IG analytics/posting).
    page_token, page_name, page_token_note = _fetch_page_access_token(
        long_lived_user_token,
        settings.FACEBOOK_PAGE_ID,
    )

    if page_token:
        token_to_use = page_token
        token_label = "Page access token (non-expiring — use this)"
        token_note = (
            f"Page: <strong>{page_name}</strong>"
            if page_name
            else "Page access token resolved successfully."
        )
        if page_token_note:
            token_note += f"<br><span style='color:#b45309'>{page_token_note}</span>"
    else:
        token_to_use = long_lived_user_token
        token_label = "Long-lived USER token (~60 days — not ideal)"
        token_note = (
            (page_token_note or "Could not fetch a Page token.")
            + "<br><strong>Set FACEBOOK_PAGE_ID in .env before re-authorizing</strong> "
            "to receive a non-expiring Page token for Facebook and Instagram."
        )

    debug_data = _debug_token_info(token_to_use)
    expiry_text = _format_expiry(debug_data)
    token_type = debug_data.get("type", "unknown")
    is_valid = debug_data.get("is_valid", "unknown")
    scopes = ", ".join(debug_data.get("scopes", []) or [])

    return HTMLResponse(
        content=f"""
        <html><body style="font-family:sans-serif;padding:2rem;max-width:720px">
          <h2>Meta (Facebook + Instagram) authorization successful</h2>
          <p>{token_note}</p>
          <p><strong>{token_label}</strong></p>
          <ul>
            <li>Valid: <strong>{is_valid}</strong></li>
            <li>Token type: <strong>{token_type}</strong></li>
            <li>Expires: <strong>{expiry_text}</strong></li>
          </ul>
          {f"<p>Scopes: {scopes}</p>" if scopes else ""}
          <p>Copy this value into <code>backend/.env</code> as
          <code>FACEBOOK_PAGE_ACCESS_TOKEN</code>, then restart the backend:</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto;word-break:break-all">{token_to_use}</pre>
          <h3>Next steps</h3>
          <ol>
            <li>Open <code>backend/.env</code></li>
            <li>Replace <code>FACEBOOK_PAGE_ACCESS_TOKEN=...</code> with the token above</li>
            <li>Restart the backend server</li>
            <li>Facebook and Instagram analytics should work again</li>
          </ol>
          <p style="color:#666;font-size:0.9rem">
            Do <strong>not</strong> use tokens from Graph API Explorer for production — they
            expire in about 1–2 hours. Always use this <code>/api/v1/auth/meta</code> flow and
            copy the <strong>Page access token</strong> shown above.
          </p>
        </body></html>
        """
    )
