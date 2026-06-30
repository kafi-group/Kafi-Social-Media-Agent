"""Shared LinkedIn OAuth helpers for organization analytics."""

from __future__ import annotations

import requests

from app.config import settings

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_INTROSPECT_URL = "https://www.linkedin.com/oauth/v2/introspectToken"
LINKEDIN_REST_URL = "https://api.linkedin.com/rest"
LINKEDIN_API_VERSION = "202604"

# Microsoft docs: organizationalEntityShareStatistics requires rw_organization_admin.
ORG_ANALYTICS_SCOPES = frozenset(
    {
        "rw_organization_admin",
        "r_organization_admin",
        "w_organization_admin",
    }
)


def oauth_scopes() -> list[str]:
    raw = (settings.LINKEDIN_OAUTH_SCOPES or "").strip()
    if raw:
        return [s.strip() for s in raw.replace(",", " ").split() if s.strip()]
    return [
        "openid",
        "profile",
        "email",
        "rw_organization_admin",
    ]


def introspect_token(access_token: str) -> dict:
    if not access_token or not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        return {}
    try:
        response = requests.post(
            LINKEDIN_INTROSPECT_URL,
            data={
                "token": access_token,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20,
        )
        if response.ok:
            return response.json()
    except requests.RequestException:
        pass
    return {}


def token_scope_set(access_token: str) -> set[str]:
    intro = introspect_token(access_token)
    scope_raw = intro.get("scope") or ""
    return {part.strip() for part in str(scope_raw).replace(",", " ").split() if part.strip()}


def token_has_org_analytics_scope(access_token: str) -> bool:
    return bool(token_scope_set(access_token) & ORG_ANALYTICS_SCOPES)


def linkedin_rest_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": LINKEDIN_API_VERSION,
    }


def organization_urn(organization_id: str) -> str:
    org_id = organization_id.strip()
    if org_id.startswith("urn:li:"):
        return org_id
    return f"urn:li:organization:{org_id}"


def resolve_analytics_token() -> tuple[str, str]:
    """
    Return (token, source_label) for LinkedIn organization analytics.

    Prefers LINKEDIN_ORGANIZATION_ACCESS_TOKEN, then scans configured accounts
    for one with organization-admin scopes, then falls back to LINKEDIN_ACCESS_TOKEN.
    """
    dedicated = (settings.LINKEDIN_ORGANIZATION_ACCESS_TOKEN or "").strip()
    if dedicated:
        return dedicated, "LINKEDIN_ORGANIZATION_ACCESS_TOKEN"

    from app.services.social_publisher import load_linkedin_accounts

    for account in load_linkedin_accounts():
        if token_has_org_analytics_scope(account.access_token):
            return account.access_token, account.label

    primary = (settings.LINKEDIN_ACCESS_TOKEN or "").strip()
    if primary:
        return primary, "LINKEDIN_ACCESS_TOKEN"

    return "", ""


def probe_org_share_statistics(
    access_token: str,
    organization_id: str,
    *,
    days: int = 7,
) -> tuple[bool, str]:
    """Lightweight API probe used by OAuth callback and diagnostics."""
    if not access_token or not organization_id:
        return False, "Missing token or organization ID."

    org_urn = organization_urn(organization_id)
    end_ms = int((__import__("datetime").datetime.utcnow()).timestamp() * 1000)
    start_ms = end_ms - (days * 24 * 60 * 60 * 1000)

    response = requests.get(
        f"{LINKEDIN_REST_URL}/organizationalEntityShareStatistics",
        headers=linkedin_rest_headers(access_token),
        params={
            "q": "organizationalEntity",
            "organizationalEntity": org_urn,
            "timeIntervals.timeGranularityType": "DAY",
            "timeIntervals.timeRange.start": start_ms,
            "timeIntervals.timeRange.end": end_ms,
        },
        timeout=20,
    )
    if response.ok:
        return True, "Organization share statistics API responded successfully."

    try:
        body = response.json()
        message = body.get("message", response.text[:300])
    except Exception:
        message = response.text[:300]
    return False, f"HTTP {response.status_code}: {message}"
