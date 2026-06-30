"""
LinkedIn OAuth 2.0 — obtain an access token with organization analytics scopes.

Visit http://localhost:8000/api/v1/auth/linkedin while the backend is running.
"""

from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.services.linkedin_oauth import (
    LINKEDIN_AUTH_URL,
    LINKEDIN_TOKEN_URL,
    introspect_token,
    oauth_scopes,
    probe_org_share_statistics,
    token_has_org_analytics_scope,
    token_scope_set,
)
from app.utils.logger import logger

router = APIRouter()


def _build_auth_url() -> str:
    params = {
        "response_type": "code",
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
        "scope": " ".join(oauth_scopes()),
    }
    return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"


@router.get("/auth/linkedin/status")
async def linkedin_auth_status():
    """Show whether the configured token can access organization analytics."""
    from app.services.linkedin_oauth import resolve_analytics_token

    org_id = (settings.LINKEDIN_ORGANIZATION_ID or "").strip()
    token, source = resolve_analytics_token()
    redirect_uri = settings.LINKEDIN_REDIRECT_URI

    if not org_id:
        return {
            "configured": False,
            "redirect_uri": redirect_uri,
            "message": "Set LINKEDIN_ORGANIZATION_ID in backend/.env first.",
        }

    if not token:
        return {
            "configured": False,
            "redirect_uri": redirect_uri,
            "organization_id": org_id,
            "message": (
                "No LinkedIn token configured. Visit /api/v1/auth/linkedin to authorize."
            ),
        }

    scopes = sorted(token_scope_set(token))
    has_org_scope = token_has_org_analytics_scope(token)
    probe_ok, probe_message = probe_org_share_statistics(token, org_id)

    return {
        "configured": True,
        "redirect_uri": redirect_uri,
        "organization_id": org_id,
        "token_source": source,
        "scopes": scopes,
        "has_org_analytics_scope": has_org_scope,
        "analytics_api_ok": probe_ok,
        "message": probe_message if not probe_ok else (
            f"LinkedIn organization analytics is ready (token from {source})."
        ),
    }


@router.get("/auth/linkedin")
async def linkedin_auth_start():
    """Instructions page before redirecting to LinkedIn."""
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first.",
        )

    org_id = (settings.LINKEDIN_ORGANIZATION_ID or "").strip()
    scopes = " ".join(oauth_scopes())
    return HTMLResponse(
        content=f"""
        <html><body style="font-family:sans-serif;padding:2rem;max-width:760px;line-height:1.5">
          <h2>Connect LinkedIn company page analytics</h2>
          <p>This flow requests organization analytics scopes for your LinkedIn app.</p>

          <div style="background:#eff6ff;border:1px solid #93c5fd;padding:1rem;border-radius:6px;margin:1rem 0">
            <p><strong>Before you continue</strong></p>
            <ol>
              <li>In <a href="https://developer.linkedin.com">LinkedIn Developer Portal</a>,
                  open your app and add the <strong>Marketing Developer Platform</strong> product.</li>
              <li>Add this redirect URI under Auth → OAuth 2.0 settings:
                <pre style="background:#f4f4f4;padding:0.5rem">{settings.LINKEDIN_REDIRECT_URI}</pre>
              </li>
              <li>Sign in with a LinkedIn member who is an <strong>Administrator</strong>
                  of your company page (org ID: <code>{org_id or "set LINKEDIN_ORGANIZATION_ID"}</code>).</li>
            </ol>
          </div>

          <p>Scopes requested:</p>
          <pre style="background:#f4f4f4;padding:0.75rem;overflow:auto">{scopes}</pre>

          <p><a href="/api/v1/auth/linkedin/continue"
             style="display:inline-block;background:#2563eb;color:white;padding:0.75rem 1.25rem;
                    border-radius:6px;text-decoration:none;font-weight:600">
             Continue to LinkedIn
          </a></p>

          <p style="color:#666;font-size:0.9rem">
            Check status anytime:
            <a href="/api/v1/auth/linkedin/status">/api/v1/auth/linkedin/status</a>
          </p>
        </body></html>
        """
    )


@router.get("/auth/linkedin/continue")
async def linkedin_auth_continue():
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first.",
        )
    return RedirectResponse(url=_build_auth_url())


@router.get("/auth/linkedin/callback", response_class=HTMLResponse)
async def linkedin_auth_callback(
    code: str = Query(default=""),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
):
    if error:
        detail = f"LinkedIn OAuth error: {error}"
        if error_description:
            detail += f" — {error_description}"
        if "unauthorized_scope" in error or "scope" in error.lower():
            detail += (
                " Your LinkedIn app has not been approved for one of the requested scopes. "
                "Enable Marketing Developer Platform at https://developer.linkedin.com and "
                "request rw_organization_admin. This flow only requests: openid profile email "
                "rw_organization_admin (not w_organization_social)."
            )
        raise HTTPException(status_code=400, detail=detail)
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    try:
        response = requests.post(
            LINKEDIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error(f"LinkedIn OAuth token exchange failed: {exc}")
        raise HTTPException(status_code=502, detail="Failed to contact LinkedIn OAuth.") from exc

    if not response.ok:
        logger.error(f"LinkedIn OAuth token exchange error: {response.text[:500]}")
        raise HTTPException(
            status_code=400,
            detail=f"LinkedIn OAuth error: {response.text[:300]}",
        )

    data = response.json()
    access_token = data.get("access_token", "")
    expires_in = data.get("expires_in", "")
    if not access_token:
        raise HTTPException(status_code=400, detail="LinkedIn did not return an access token.")

    intro = introspect_token(access_token)
    scopes = sorted(token_scope_set(access_token))
    scope_text = ", ".join(scopes) if scopes else "(none reported)"
    org_scope_ok = token_has_org_analytics_scope(access_token)

    org_id = (settings.LINKEDIN_ORGANIZATION_ID or "").strip()
    probe_ok = False
    probe_message = "Set LINKEDIN_ORGANIZATION_ID, then re-run this flow."
    if org_id:
        probe_ok, probe_message = probe_org_share_statistics(access_token, org_id)

    warning = ""
    if not org_scope_ok:
        warning = """
          <div style="background:#fef2f2;border:2px solid #dc2626;padding:1rem;margin:1rem 0;border-radius:6px">
            <p><strong>Missing organization analytics scope</strong></p>
            <p>Token does not include <code>rw_organization_admin</code>. Enable
            <strong>Marketing Developer Platform</strong> on your LinkedIn app, then try again.</p>
          </div>
        """
    elif org_id and not probe_ok:
        warning = f"""
          <div style="background:#fff7ed;border:1px solid #fdba74;padding:1rem;margin:1rem 0;border-radius:6px">
            <p><strong>Token scopes look OK, but analytics API probe failed</strong></p>
            <p>{probe_message}</p>
            <p>Confirm the signed-in member is a company page <strong>Administrator</strong>
            for organization ID <code>{org_id}</code>.</p>
          </div>
        """

    return HTMLResponse(
        content=f"""
        <html><body style="font-family:sans-serif;padding:2rem;max-width:760px;line-height:1.5">
          <h2>LinkedIn authorization successful</h2>
          {warning}
          <p>Granted scopes:</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto">{scope_text}</pre>
          <p>Expires in: {expires_in or "unknown"} seconds</p>
          <p>Add this to <code>backend/.env</code> (keeps personal posting tokens unchanged):</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto;word-break:break-all">LINKEDIN_ORGANIZATION_ACCESS_TOKEN="{access_token}"</pre>
          <p>Organization ID (analytics target):</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto">LINKEDIN_ORGANIZATION_ID={org_id or "YOUR_ORG_ID"}</pre>
          <h3>Next steps</h3>
          <ol>
            <li>Paste the token into <code>backend/.env</code></li>
            <li>Restart the backend</li>
            <li>Open Dashboard → Analytics → LinkedIn</li>
            <li>Or verify at <a href="/api/v1/auth/linkedin/status">/api/v1/auth/linkedin/status</a></li>
          </ol>
          <p style="color:#666;font-size:0.9rem">
            LinkedIn access tokens expire (~60 days). Re-run this flow when analytics stops working.
          </p>
        </body></html>
        """
    )
