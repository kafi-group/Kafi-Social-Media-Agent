"""
YouTube OAuth 2.0 routes — obtain a refresh token with upload permissions.

Visit http://localhost:8000/api/v1/auth/youtube while the backend is running.
"""

from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.services.social_publisher import YouTubeClient
from app.utils.logger import logger

router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

REQUIRED_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def _list_oauth_channels(access_token: str) -> list[dict]:
    """Return all YouTube channels visible to this OAuth token."""
    try:
        ch_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        if not ch_resp.ok:
            return []
        channels = []
        for item in ch_resp.json().get("items", []):
            snippet = item.get("snippet", {})
            channels.append(
                {
                    "id": item.get("id", ""),
                    "title": snippet.get("title", ""),
                    "custom_url": snippet.get("customUrl", ""),
                }
            )
        return channels
    except requests.RequestException as exc:
        logger.warning(f"YouTube channel lookup during OAuth: {exc}")
        return []


def _oauth_scopes() -> list[str]:
    return [s.strip() for s in settings.YOUTUBE_OAUTH_SCOPES.split(",") if s.strip()]


def _build_google_auth_url() -> str:
    params = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(_oauth_scopes()),
        "access_type": "offline",
        # Force account picker so user can select the Brand Account (e.g. Essence Food),
        # not just the parent Gmail address.
        "prompt": "consent select_account",
        "include_granted_scopes": "true",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


@router.get("/auth/youtube/status")
async def youtube_auth_status():
    """
    Show which YouTube channel THIS backend instance will upload to.
    Use this to confirm local vs Railway are using different tokens.
    """
    client = YouTubeClient(draft_mode=False)
    configured_id = (settings.YOUTUBE_CHANNEL_ID or "").strip()
    redirect_uri = settings.YOUTUBE_REDIRECT_URI

    if not client.is_configured:
        return {
            "configured": False,
            "redirect_uri": redirect_uri,
            "message": "YouTube OAuth credentials missing in this backend's environment.",
        }

    token = client._refresh_access_token()
    if not token:
        return {
            "configured": True,
            "redirect_uri": redirect_uri,
            "oauth_valid": False,
            "configured_channel_id": configured_id or None,
            "message": "Refresh token invalid for this backend. Re-authorize.",
        }

    channels = _list_oauth_channels(token)
    upload_target = channels[0] if channels else None
    oauth_id = (upload_target or {}).get("id", "")
    id_matches = bool(configured_id and oauth_id and configured_id == oauth_id)

    return {
        "configured": True,
        "redirect_uri": redirect_uri,
        "oauth_valid": True,
        "upload_target": upload_target,
        "all_channels_visible_to_token": channels,
        "configured_channel_id": configured_id or None,
        "channel_id_matches_token": id_matches,
        "will_block_upload_on_mismatch": bool(configured_id and oauth_id and not id_matches),
        "message": (
            f"Uploads from THIS backend go to "
            f"'{(upload_target or {}).get('title', 'unknown')}' "
            f"({oauth_id})."
            if upload_target
            else "Could not resolve upload channel for this token."
        ),
    }


@router.get("/auth/youtube")
async def youtube_auth_start():
    """
    Start YouTube OAuth — shows brand-account instructions, then Google consent.
    After approval, copy the refresh token from the callback page into .env.
    """
    if not settings.YOUTUBE_CLIENT_ID or not settings.YOUTUBE_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first.",
        )

    continue_url = "/api/v1/auth/youtube/continue"
    return HTMLResponse(
        content=f"""
        <html><body style="font-family:sans-serif;padding:2rem;max-width:720px;line-height:1.5">
          <h2>Connect YouTube for uploads</h2>
          <p>This backend will save tokens for:</p>
          <pre style="background:#f4f4f4;padding:0.75rem">{settings.YOUTUBE_REDIRECT_URI}</pre>

          <div style="background:#fef2f2;border:1px solid #fca5a5;padding:1rem;border-radius:6px;margin:1rem 0">
            <p><strong>Brand accounts (Essence Food vs Kafi Kitchen)</strong></p>
            <p>Switching channels inside YouTube is <em>not enough</em>. When Google opens,
            you must pick the <strong>channel name</strong> on the account chooser:</p>
            <ul>
              <li>Choose <strong>Essence Food</strong> — correct for main brand uploads</li>
              <li>Do <strong>not</strong> choose <code>kafi.essence@gmail.com</code> or <strong>Kafi Kitchen</strong></li>
            </ul>
            <p>If the wrong channel appears on the success page, revoke the app and try again.</p>
          </div>

          <p><a href="{continue_url}"
             style="display:inline-block;background:#dc2626;color:white;padding:0.75rem 1.25rem;
                    border-radius:6px;text-decoration:none;font-weight:600">
             Continue to Google sign-in
          </a></p>

          <p style="color:#666;font-size:0.9rem">
            Already connected? Check
            <a href="/api/v1/auth/youtube/status">/api/v1/auth/youtube/status</a>
            to see which channel this backend will upload to.
          </p>
        </body></html>
        """
    )


@router.get("/auth/youtube/continue")
async def youtube_auth_continue():
    """Redirect to Google OAuth with account picker enabled."""
    if not settings.YOUTUBE_CLIENT_ID or not settings.YOUTUBE_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first.",
        )
    return RedirectResponse(url=_build_google_auth_url())


@router.get("/auth/youtube/callback", response_class=HTMLResponse)
async def youtube_auth_callback(code: str = Query(default="")):
    """Exchange OAuth code for refresh token and display it for .env."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error(f"YouTube OAuth token exchange failed: {exc}")
        raise HTTPException(status_code=502, detail="Failed to contact Google OAuth.") from exc

    if not response.ok:
        logger.error(f"YouTube OAuth token exchange error: {response.text[:500]}")
        raise HTTPException(
            status_code=400,
            detail=f"Google OAuth error: {response.text[:300]}",
        )

    data = response.json()
    refresh_token = data.get("refresh_token", "")
    granted_scopes = data.get("scope", "")

    if not refresh_token:
        return HTMLResponse(
            status_code=400,
            content="""
            <html><body style="font-family:sans-serif;padding:2rem;max-width:640px">
              <h2>No refresh token returned</h2>
              <p>Google did not return a refresh token. This usually means the app was
              already authorized without forcing consent.</p>
              <ol>
                <li>Revoke access at
                  <a href="https://myaccount.google.com/permissions">Google Account permissions</a>
                </li>
                <li>Visit <a href="/api/v1/auth/youtube">/api/v1/auth/youtube</a> again</li>
              </ol>
            </body></html>
            """,
        )

    upload_ok = REQUIRED_UPLOAD_SCOPE in granted_scopes.split()
    scope_status = (
        "Upload scope granted — you can post videos."
        if upload_ok
        else "WARNING: youtube.upload scope missing. Re-authorize after revoking app access."
    )

    channel_block = ""
    wrong_channel_warning = ""
    access_token = data.get("access_token", "")
    if access_token:
        channels = _list_oauth_channels(access_token)
        if channels:
            upload_target = channels[0]
            channel_id = upload_target.get("id", "")
            title = upload_target.get("title", "")
            custom_url = upload_target.get("custom_url", "")
            title_lower = title.lower()
            if "kafi kitchen" in title_lower or custom_url == "@kafikitchen":
                wrong_channel_warning = """
          <div style="background:#fef2f2;border:2px solid #dc2626;padding:1rem;margin:1rem 0;border-radius:6px">
            <p><strong>Wrong channel — do not save this token!</strong></p>
            <p>This token uploads to <strong>Kafi Kitchen</strong>. Revoke access, then authorize
            again and select <strong>Essence Food</strong> on Google's account chooser
            (not the Gmail address).</p>
            <p><a href="/api/v1/auth/youtube">Try again</a></p>
          </div>
                """
            channel_block = f"""
          <h3>Upload target for this token</h3>
          <p><strong>{title}</strong>{f' ({custom_url})' if custom_url else ''}</p>
          <p>Videos will upload to this channel — verify it is correct before saving the token.</p>
          <p>Add to <code>backend/.env</code> <strong>and Railway</strong>:</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto">YOUTUBE_CHANNEL_ID={channel_id}</pre>
            """
            if len(channels) > 1:
                others = "".join(
                    f"<li><strong>{ch.get('title', '')}</strong>"
                    f"{f' ({ch.get('custom_url', '')})' if ch.get('custom_url') else ''}"
                    f" — <code>{ch.get('id', '')}</code></li>"
                    for ch in channels
                )
                channel_block += f"""
          <div style="background:#fff7ed;border:1px solid #fdba74;padding:1rem;margin-top:1rem;border-radius:6px">
            <p><strong>All channels visible to this token</strong></p>
            <ul>{others}</ul>
          </div>
                """

    return HTMLResponse(
        content=f"""
        <html><body style="font-family:sans-serif;padding:2rem;max-width:720px">
          <h2>YouTube authorization successful</h2>
          {wrong_channel_warning}
          <p><strong>{scope_status}</strong></p>
          <p>Callback / redirect URI for this token:</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto">{settings.YOUTUBE_REDIRECT_URI}</pre>
          <p>Granted scopes:</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto">{granted_scopes}</pre>
          <p>Add this to the <strong>same backend</strong> that handles your posts
          (<code>backend/.env</code> for local, Railway Variables for production):</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto;word-break:break-all">YOUTUBE_REFRESH_TOKEN="{refresh_token}"</pre>
          {channel_block}
          <h3>Next steps</h3>
          <ol>
            <li>Paste the refresh token and channel ID into the environment that serves your dashboard posts</li>
            <li>If you post from <a href="https://kafi-social-agent.vercel.app">Vercel</a>,
                update <strong>Railway</strong> — local <code>.env</code> alone is not enough</li>
            <li>Restart / redeploy the backend</li>
            <li>Confirm at <code>/api/v1/auth/youtube/status</code> and Dashboard → Settings</li>
          </ol>
          <p style="color:#666;font-size:0.9rem">
            Keep this token secret. Do not commit it to git.
          </p>
        </body></html>
        """
    )
