"""Verify LinkedIn and YouTube credentials (no live posts)."""

import sys
from datetime import datetime
from pathlib import Path

import requests

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings  # noqa: E402
from app.services.social_publisher import (  # noqa: E402
    LinkedInClient,
    YouTubeClient,
    load_linkedin_accounts,
)


def _env_issues(value: str) -> list[str]:
    issues: list[str] = []
    if value.startswith(" ") or value.startswith('"'):
        issues.append("leading space or quote")
    if value.endswith('"'):
        issues.append("trailing quote")
    return issues


def _linkedin_introspect(token: str) -> dict:
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        return {"skip": "Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET for introspection"}
    response = requests.post(
        "https://www.linkedin.com/oauth/v2/introspectToken",
        data={
            "token": token,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    if response.ok:
        return response.json()
    return {"error": response.status_code, "body": response.text[:200]}


def _linkedin_userinfo(token: str) -> dict:
    response = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if response.ok:
        data = response.json()
        return {"ok": True, "name": data.get("name"), "sub": data.get("sub")}
    return {"ok": False, "status": response.status_code, "body": response.text[:200]}


def verify_linkedin() -> None:
    print("=" * 60)
    print("LINKEDIN (no live posts)")
    print("=" * 60)
    accounts = load_linkedin_accounts()
    print(f"Accounts loaded: {len(accounts)}\n")

    for acct in accounts:
        print(f"--- {acct.label} ---")
        token_issues = _env_issues(acct.access_token)
        label_issues = _env_issues(acct.label)
        if token_issues or label_issues:
            print(f"  .env formatting issues: token={token_issues or 'ok'}, label={label_issues or 'ok'}")

        intro = _linkedin_introspect(acct.access_token)
        if intro.get("active") is True:
            print("  Token: ACTIVE")
            print(f"  Scopes: {intro.get('scope', '(none)')}")
            expires_at = intro.get("expires_at")
            if expires_at:
                print(
                    "  Expires:",
                    datetime.utcfromtimestamp(int(expires_at)).strftime("%Y-%m-%d %H:%M UTC"),
                )
        elif intro.get("active") is False:
            print("  Token: INACTIVE / EXPIRED")
        else:
            print(f"  Introspection: {intro}")

        userinfo = _linkedin_userinfo(acct.access_token)
        if userinfo.get("ok"):
            print(f"  Profile: {userinfo.get('name')} (id={userinfo.get('sub')})")
        else:
            print(f"  Userinfo failed: HTTP {userinfo.get('status')}")

        client = LinkedInClient(
            acct.access_token, acct.person_id, acct.label, draft_mode=False
        )
        try:
            urn = client._author_urn()
            print(f"  Author URN: {urn}")
        except Exception as exc:
            print(f"  Author URN failed: {exc}")
            urn = None

        if urn:
            response = requests.post(
                client.MEDIA_API_URL,
                headers=client._headers(),
                json={"initializeUploadRequest": {"owner": urn}},
                timeout=20,
            )
            if response.status_code in (200, 201):
                print("  Image upload init: OK")
            else:
                print(f"  Image upload init: HTTP {response.status_code} {response.text[:150]}")
        print()


def verify_youtube() -> None:
    print("=" * 60)
    print("YOUTUBE")
    print("=" * 60)
    client = YouTubeClient(draft_mode=False)
    print(f"Credentials present: {client.is_configured}")
    print(f"YOUTUBE_CHANNEL_ID set: {bool((settings.YOUTUBE_CHANNEL_ID or '').strip())}")

    if not client.is_configured:
        print("YouTube: NOT configured (missing client id/secret or refresh token)\n")
        return

    token = client._refresh_access_token()
    if not token:
        print("Refresh token: FAILED (expired or revoked — visit /api/v1/auth/youtube)\n")
        return

    print("Refresh token: OK")
    response = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "snippet,statistics", "mine": "true"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if not response.ok:
        print(f"Channels API failed: HTTP {response.status_code} {response.text[:200]}\n")
        return

    items = response.json().get("items", [])
    if not items:
        print("No YouTube channel returned for this Google account\n")
        return

    snippet = items[0]["snippet"]
    stats = items[0].get("statistics", {})
    channel_id = items[0]["id"]
    print(f"OAuth channel ID: {channel_id}")
    print(f"Channel title: {snippet.get('title')}")
    print(f"Custom URL: {snippet.get('customUrl')}")
    print(f"Subscribers: {stats.get('subscriberCount', 'hidden')}")

    configured_id = (settings.YOUTUBE_CHANNEL_ID or "").strip()
    if configured_id:
        if configured_id == channel_id:
            print("YOUTUBE_CHANNEL_ID: matches OAuth channel")
        else:
            print("YOUTUBE_CHANNEL_ID: MISMATCH with OAuth channel")
    else:
        print(f"Tip: set YOUTUBE_CHANNEL_ID={channel_id}")
    print()


def verify_meta() -> None:
    print("=" * 60)
    print("FACEBOOK + INSTAGRAM (no live posts)")
    print("=" * 60)
    from app.services.social_publisher import fetch_connected_account_details

    details = fetch_connected_account_details()
    fb = details.get("facebook") or {}
    ig = details.get("instagram") or {}

    if fb.get("name"):
        match = "matches" if fb.get("id_matches") else "MISMATCH"
        print(f"Facebook Page: {fb.get('name')} (id={fb.get('id')}) — .env {match}")
    elif settings.FACEBOOK_PAGE_ID:
        print(f"Facebook Page: could not verify ({fb.get('error', 'unknown error')})")
    else:
        print("Facebook: NOT configured")

    if ig and ig.get("id"):
        label = f"@{ig.get('username')}" if ig.get("username") else ig.get("name")
        match = "matches" if ig.get("id_matches") else "MISMATCH"
        print(f"Instagram: {label} (id={ig.get('id')}) — .env {match}")
    elif settings.INSTAGRAM_ACCOUNT_ID:
        print("Instagram: configured in .env but could not resolve linked Business account")
    else:
        print("Instagram: NOT configured")
    print()


def main() -> None:
    print(f"DRAFT_MODE: {settings.DRAFT_MODE}\n")
    verify_linkedin()
    verify_meta()
    verify_youtube()


if __name__ == "__main__":
    main()
