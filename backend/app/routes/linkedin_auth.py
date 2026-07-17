"""
LinkedIn OAuth 2.0 — personal posting and optional company-page analytics.

Live: https://kafi-social-agent.up.railway.app/api/v1/auth/linkedin
"""

from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import public_api_url, settings
from app.services.linkedin_oauth import (
    LINKEDIN_AUTH_URL,
    LINKEDIN_TOKEN_URL,
    oauth_scopes,
    probe_org_share_statistics,
    token_has_org_analytics_scope,
    token_scope_set,
)
from app.utils.logger import logger

router = APIRouter()


def _build_auth_url(purpose: str = "posting") -> str:
    params = {
        "response_type": "code",
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
        "scope": " ".join(oauth_scopes(purpose)),
        "state": purpose if purpose in ("posting", "analytics") else "posting",
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
            "auth_url": public_api_url("/api/v1/auth/linkedin"),
            "message": "Set LINKEDIN_ORGANIZATION_ID for company analytics (optional).",
        }

    if not token:
        return {
            "configured": False,
            "redirect_uri": redirect_uri,
            "organization_id": org_id,
            "auth_url": public_api_url("/api/v1/auth/linkedin?purpose=analytics"),
            "message": (
                "No LinkedIn org analytics token. Use the analytics OAuth flow after "
                "Marketing Developer Platform is approved on your LinkedIn app."
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
    """Instructions page with posting vs analytics options."""
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in Railway first.",
        )

    org_id = (settings.LINKEDIN_ORGANIZATION_ID or "").strip()
    posting_scopes = " ".join(oauth_scopes("posting"))
    analytics_scopes = " ".join(oauth_scopes("analytics"))
    return HTMLResponse(
        content=f"""
        <html><body style="font-family:sans-serif;padding:2rem;max-width:760px;line-height:1.5">
          <h2>Connect LinkedIn</h2>
          <p>Redirect URI (must match LinkedIn Developer Portal → Auth):</p>
          <pre style="background:#f4f4f4;padding:0.75rem">{settings.LINKEDIN_REDIRECT_URI}</pre>

          <div style="background:#ecfdf5;border:1px solid #6ee7b7;padding:1rem;border-radius:6px;margin:1rem 0">
            <p><strong>Option A — Personal posting (recommended)</strong></p>
            <p>Works with the default Sign In with LinkedIn + Share on LinkedIn products.
            Does <em>not</em> need Marketing Developer Platform.</p>
            <p>Scopes: <code>{posting_scopes}</code></p>
            <p><a href="/api/v1/auth/linkedin/continue?purpose=posting"
               style="display:inline-block;background:#0a66c2;color:white;padding:0.75rem 1.25rem;
                      border-radius:6px;text-decoration:none;font-weight:600">
               Continue for posting
            </a></p>
          </div>

          <div style="background:#fff7ed;border:1px solid #fdba74;padding:1rem;border-radius:6px;margin:1rem 0">
            <p><strong>Option B — Company page analytics</strong></p>
            <p>Requires <strong>Marketing Developer Platform</strong> approval for
            <code>rw_organization_admin</code>. Without that approval LinkedIn returns
            <code>unauthorized_scope_error</code>.</p>
            <ol>
              <li>Open <a href="https://developer.linkedin.com">LinkedIn Developer Portal</a></li>
              <li>Products → request / enable <strong>Marketing Developer Platform</strong></li>
              <li>Wait for approval, then use the button below</li>
              <li>Org ID: <code>{org_id or "set LINKEDIN_ORGANIZATION_ID on Railway"}</code></li>
            </ol>
            <p>Scopes: <code>{analytics_scopes}</code></p>
            <p><a href="/api/v1/auth/linkedin/continue?purpose=analytics"
               style="display:inline-block;background:#b45309;color:white;padding:0.75rem 1.25rem;
                      border-radius:6px;text-decoration:none;font-weight:600">
               Continue for company analytics
            </a></p>
          </div>

          <p style="color:#666;font-size:0.9rem">
            Dashboard LinkedIn analytics currently uses a static snapshot, so Option A is
            enough for posting. Status:
            <a href="{public_api_url('/api/v1/auth/linkedin/status')}">linkedin/status</a>
          </p>
        </body></html>
        """
    )


@router.get("/auth/linkedin/continue")
async def linkedin_auth_continue(purpose: str = Query(default="posting")):
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in Railway first.",
        )
    purpose = purpose if purpose in ("posting", "analytics") else "posting"
    return RedirectResponse(url=_build_auth_url(purpose))


@router.get("/auth/linkedin/callback", response_class=HTMLResponse)
async def linkedin_auth_callback(
    code: str = Query(default=""),
    state: str = Query(default="posting"),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
):
    if error:
        purpose = state if state in ("posting", "analytics") else "analytics"
        detail = f"LinkedIn OAuth error: {error}"
        if error_description:
            detail += f" — {error_description}"
        if "unauthorized_scope" in error or "scope" in (error_description or "").lower():
            detail += (
                " Your LinkedIn app is not approved for one of the requested scopes. "
                "Use Option A (posting) at /api/v1/auth/linkedin, or enable Marketing "
                "Developer Platform before Option B (company analytics)."
            )
        # Return a readable HTML page instead of raw JSON for browser users.
        return HTMLResponse(
            status_code=400,
            content=f"""
            <html><body style="font-family:sans-serif;padding:2rem;max-width:720px;line-height:1.5">
              <h2>LinkedIn authorization failed</h2>
              <p>{detail}</p>
              <p><a href="/api/v1/auth/linkedin">Back to LinkedIn connect options</a></p>
              <p>If you only need posting, use <strong>Option A</strong> (no
              <code>rw_organization_admin</code>).</p>
            </body></html>
            """,
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    purpose = state if state in ("posting", "analytics") else "posting"

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

    scopes = sorted(token_scope_set(access_token))
    scope_text = ", ".join(scopes) if scopes else "(none reported)"
    org_scope_ok = token_has_org_analytics_scope(access_token)

    org_id = (settings.LINKEDIN_ORGANIZATION_ID or "").strip()
    probe_ok = False
    probe_message = "Set LINKEDIN_ORGANIZATION_ID for company analytics probes."
    if org_id and org_scope_ok:
        probe_ok, probe_message = probe_org_share_statistics(access_token, org_id)

    saved_keys: list[str] = []
    # Persist into runtime/.env when possible. LinkedIn org token is not in MANAGED_KEYS
    # yet — keep personal token path via settings setattr for analytics purpose.
    if purpose == "analytics" and org_scope_ok:
        settings.LINKEDIN_ORGANIZATION_ACCESS_TOKEN = access_token
        try:
            from pathlib import Path
            import re

            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_path.exists():
                text = env_path.read_text(encoding="utf-8")
                line = f'LINKEDIN_ORGANIZATION_ACCESS_TOKEN="{access_token}"'
                if re.search(r"^LINKEDIN_ORGANIZATION_ACCESS_TOKEN=.*$", text, flags=re.M):
                    text = re.sub(
                        r"^LINKEDIN_ORGANIZATION_ACCESS_TOKEN=.*$",
                        line,
                        text,
                        flags=re.M,
                    )
                else:
                    text += f"\n{line}\n"
                env_path.write_text(text, encoding="utf-8")
                saved_keys.append("LINKEDIN_ORGANIZATION_ACCESS_TOKEN")
        except OSError as exc:
            logger.warning(f"Could not persist LinkedIn org token to .env: {exc}")
    elif purpose == "posting":
        settings.LINKEDIN_ACCESS_TOKEN = access_token
        try:
            from pathlib import Path
            import re

            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_path.exists():
                text = env_path.read_text(encoding="utf-8")
                line = f'LINKEDIN_ACCESS_TOKEN="{access_token}"'
                if re.search(r"^LINKEDIN_ACCESS_TOKEN=.*$", text, flags=re.M):
                    text = re.sub(
                        r"^LINKEDIN_ACCESS_TOKEN=.*$",
                        line,
                        text,
                        flags=re.M,
                    )
                else:
                    text += f"\n{line}\n"
                env_path.write_text(text, encoding="utf-8")
                saved_keys.append("LINKEDIN_ACCESS_TOKEN")
        except OSError as exc:
            logger.warning(f"Could not persist LinkedIn posting token to .env: {exc}")

    warning = ""
    if purpose == "analytics" and not org_scope_ok:
        warning = """
          <div style="background:#fef2f2;border:2px solid #dc2626;padding:1rem;margin:1rem 0;border-radius:6px">
            <p><strong>Missing organization analytics scope</strong></p>
            <p>Enable <strong>Marketing Developer Platform</strong> on your LinkedIn app,
            wait for approval, then try Option B again. For posting only, use Option A.</p>
          </div>
        """
    elif purpose == "analytics" and org_id and not probe_ok:
        warning = f"""
          <div style="background:#fff7ed;border:1px solid #fdba74;padding:1rem;margin:1rem 0;border-radius:6px">
            <p><strong>Token scopes look OK, but analytics API probe failed</strong></p>
            <p>{probe_message}</p>
          </div>
        """

    saved_note = (
        f"<p style='background:#ecfdf5;border:1px solid #6ee7b7;padding:1rem;border-radius:6px'>"
        f"<strong>Saved:</strong> {', '.join(saved_keys)}. Also set the same variable on "
        f"<strong>Railway</strong> for production.</p>"
        if saved_keys
        else "<p>Copy the token below into Railway Variables for production.</p>"
    )

    token_var = (
        "LINKEDIN_ORGANIZATION_ACCESS_TOKEN"
        if purpose == "analytics"
        else "LINKEDIN_ACCESS_TOKEN"
    )

    return HTMLResponse(
        content=f"""
        <html><body style="font-family:sans-serif;padding:2rem;max-width:760px;line-height:1.5">
          <h2>LinkedIn authorization successful ({purpose})</h2>
          {warning}
          {saved_note}
          <p>Granted scopes:</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto">{scope_text}</pre>
          <p>Expires in: {expires_in or "unknown"} seconds</p>
          <p>Railway / .env value:</p>
          <pre style="background:#f4f4f4;padding:1rem;overflow:auto;word-break:break-all">{token_var}="{access_token}"</pre>
          <h3>Next steps</h3>
          <ol>
            <li>Confirm the token is set on <strong>Railway Variables</strong></li>
            <li>Redeploy / restart the backend if you only changed Railway</li>
            <li>Verify at <a href="{public_api_url('/api/v1/auth/linkedin/status')}">linkedin/status</a></li>
          </ol>
        </body></html>
        """
    )
