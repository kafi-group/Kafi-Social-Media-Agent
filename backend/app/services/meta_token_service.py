"""
Meta (Facebook + Instagram) long-lived token maintenance.

Page tokens derived from a long-lived user token do not expire unless revoked.
We still store the long-lived user token and periodically re-exchange it
(extends ~60 days each time) so we can always re-derive a fresh Page token
if Meta invalidates the current one.
"""

from __future__ import annotations

import threading
from typing import Any

import requests

from app.config import settings
from app.services.token_store import save_credentials
from app.utils.logger import logger

FACEBOOK_TOKEN_URL = "https://graph.facebook.com/oauth/access_token"
FACEBOOK_DEBUG_TOKEN_URL = "https://graph.facebook.com/debug_token"

_refresh_lock = threading.Lock()


def _graph_base() -> str:
    return f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}"


def exchange_long_lived_user_token(token: str) -> tuple[str, dict[str, Any]]:
    """
    Exchange a short- or long-lived user token for a fresh long-lived user token.
    Returns (new_token, raw_response_json).
    """
    resp = requests.get(
        FACEBOOK_TOKEN_URL,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "fb_exchange_token": token,
        },
        timeout=30,
    )
    data = resp.json() if resp.content else {}
    if not resp.ok:
        raise RuntimeError(
            f"Meta long-lived exchange failed ({resp.status_code}): "
            f"{str(data)[:300]}"
        )
    new_token = (data.get("access_token") or "").strip()
    if not new_token:
        raise RuntimeError("Meta long-lived exchange returned no access_token")
    return new_token, data


def fetch_page_access_token(
    long_lived_user_token: str,
    page_id: str = "",
) -> tuple[str, str, str]:
    """
    Resolve a Page access token from a long-lived user token.
    Returns (token, page_name, note).
    """
    page_id = (page_id or settings.FACEBOOK_PAGE_ID or "").strip()
    graph_url = _graph_base()

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
                token = (page_data.get("access_token") or "").strip()
                if token:
                    return token, page_data.get("name", "your page"), ""
            logger.warning(f"Direct page token fetch failed: {page_resp.text[:200]}")
        except requests.RequestException as exc:
            logger.warning(f"Direct page token fetch error: {exc}")

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
                token = (page.get("access_token") or "").strip()
                if token:
                    return token, page.get("name", "your page"), ""
            pages = accounts_resp.json().get("data", []) or []
            if page_id:
                # Configured ID missing from me/accounts — fall back to first
                # managed page so reconnect still yields a usable Page token.
                for page in pages:
                    token = (page.get("access_token") or "").strip()
                    if token:
                        return (
                            token,
                            page.get("name", "your page"),
                            (
                                f"No managed page matched FACEBOOK_PAGE_ID={page_id}. "
                                f"Using '{page.get('name')}' ({page.get('id')}) instead — "
                                "update FACEBOOK_PAGE_ID on Railway to this ID."
                            ),
                        )
                return (
                    "",
                    "",
                    f"No managed page matched FACEBOOK_PAGE_ID={page_id}.",
                )
            for page in pages:
                token = (page.get("access_token") or "").strip()
                if token:
                    return token, page.get("name", "your page"), ""
    except requests.RequestException as exc:
        logger.warning(f"me/accounts page token fetch error: {exc}")

    return "", "", "Could not resolve a Page access token from the user token."


def resolve_instagram_account_id(page_token: str, page_id: str = "") -> str:
    page_id = (page_id or settings.FACEBOOK_PAGE_ID or "").strip()
    if not page_id or not page_token:
        return ""
    try:
        resp = requests.get(
            f"{_graph_base()}/{page_id}",
            params={
                "fields": "instagram_business_account{id}",
                "access_token": page_token,
            },
            timeout=20,
        )
        if resp.ok:
            ig = resp.json().get("instagram_business_account") or {}
            if isinstance(ig, dict):
                return str(ig.get("id") or "").strip()
    except requests.RequestException as exc:
        logger.warning(f"Instagram account lookup failed: {exc}")
    return ""


def debug_token(access_token: str) -> dict[str, Any]:
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


def persist_meta_tokens(
    *,
    page_token: str = "",
    user_token: str = "",
    page_id: str = "",
    instagram_account_id: str = "",
) -> list[str]:
    updates: dict[str, str] = {}
    if page_token:
        updates["FACEBOOK_PAGE_ACCESS_TOKEN"] = page_token
    if user_token:
        updates["FACEBOOK_USER_ACCESS_TOKEN"] = user_token
    if page_id:
        updates["FACEBOOK_PAGE_ID"] = page_id
    if instagram_account_id:
        updates["INSTAGRAM_ACCOUNT_ID"] = instagram_account_id
    return save_credentials(updates)


def refresh_meta_tokens(*, force: bool = False) -> dict[str, Any]:
    """
    Extend the long-lived user token and re-derive the Page token.
    Safe to run on a schedule. Returns a status dict (no secrets).
    """
    with _refresh_lock:
        return _refresh_meta_tokens_unlocked(force=force)


def _refresh_meta_tokens_unlocked(*, force: bool = False) -> dict[str, Any]:
    if not settings.FACEBOOK_APP_ID or not settings.FACEBOOK_APP_SECRET:
        return {
            "status": "skipped",
            "reason": "FACEBOOK_APP_ID / FACEBOOK_APP_SECRET not configured",
        }

    user_token = (settings.FACEBOOK_USER_ACCESS_TOKEN or "").strip()
    page_token = (settings.FACEBOOK_PAGE_ACCESS_TOKEN or "").strip()

    if not user_token:
        # Without a stored user token we cannot auto-renew. Page tokens from a
        # proper Meta OAuth flow are non-expiring; only warn if debug says invalid.
        if not page_token:
            return {"status": "skipped", "reason": "no Meta tokens stored"}
        info = debug_token(page_token)
        if info and info.get("is_valid") is False:
            return {
                "status": "needs_reauth",
                "reason": (
                    "Page token is invalid and no FACEBOOK_USER_ACCESS_TOKEN is "
                    "stored. Visit /api/v1/auth/meta once — tokens will auto-save."
                ),
            }
        if not force:
            return {
                "status": "ok",
                "reason": (
                    "Using non-expiring Page token. Re-run /api/v1/auth/meta once "
                    "to store a user token for automatic renewal."
                ),
                "page_token_valid": info.get("is_valid", True),
            }
        return {
            "status": "needs_reauth",
            "reason": "force refresh requested but FACEBOOK_USER_ACCESS_TOKEN is missing",
        }

    try:
        new_user_token, exchange_data = exchange_long_lived_user_token(user_token)
        page_token_new, page_name, note = fetch_page_access_token(
            new_user_token,
            settings.FACEBOOK_PAGE_ID,
        )
        if not page_token_new:
            # Keep the refreshed user token even if page resolve failed.
            persist_meta_tokens(user_token=new_user_token)
            return {
                "status": "partial",
                "reason": note or "User token refreshed but Page token missing",
                "expires_in": exchange_data.get("expires_in"),
            }

        ig_id = resolve_instagram_account_id(
            page_token_new,
            settings.FACEBOOK_PAGE_ID,
        )
        saved = persist_meta_tokens(
            page_token=page_token_new,
            user_token=new_user_token,
            instagram_account_id=ig_id,
        )
        logger.info(
            f"Meta tokens auto-refreshed for page '{page_name or settings.FACEBOOK_PAGE_ID}'"
        )
        return {
            "status": "refreshed",
            "page_name": page_name,
            "saved_keys": saved,
            "expires_in": exchange_data.get("expires_in"),
        }
    except Exception as exc:
        logger.error(f"Meta token auto-refresh failed: {exc}")
        return {"status": "error", "reason": str(exc)[:300]}


def ensure_valid_page_token() -> bool:
    """
    Best-effort repair used by analytics when Meta returns token_expired.
    Returns True when a refreshed Page token was persisted.
    """
    result = refresh_meta_tokens(force=True)
    return result.get("status") == "refreshed" and bool(
        (settings.FACEBOOK_PAGE_ACCESS_TOKEN or "").strip()
    )
