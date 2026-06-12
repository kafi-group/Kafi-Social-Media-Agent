"""
Email Service
Sends designer-approval-request emails via SMTP (Gmail by default).

The email contains the post's media, head caption (title), body caption, the
target platforms, and two one-click action links (Approve / Reject) that hit the
backend approval review endpoint.
"""

import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from app.config import settings
from app.services.media import MediaService
from app.utils.logger import logger
from app.utils.sanitize import escape_html

media_service = MediaService()


def is_email_configured() -> bool:
    """True when SMTP credentials and a designer recipient are set."""
    return bool(
        settings.SMTP_USERNAME
        and settings.SMTP_PASSWORD
        and settings.DESIGNER_EMAIL
    )


def public_media_url(media_path: Optional[str]) -> Optional[str]:
    """
    Build an absolute, publicly reachable URL for a stored media file.

    - Supabase storage already returns absolute https URLs.
    - Local storage returns "/uploads/..." which we prefix with BACKEND_PUBLIC_URL.
    """
    if not media_path:
        return None
    try:
        url = media_service.get_public_url(media_path)
    except Exception as e:
        logger.warning(f"Could not resolve media URL for {media_path}: {e}")
        return None

    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}{url}"


def _review_link(token: str, action: str) -> str:
    base = settings.BACKEND_PUBLIC_URL.rstrip("/")
    return f"{base}/api/v1/approvals/review/{token}?action={action}"


def _build_html(
    *,
    title: str,
    body: str,
    platforms: list[str],
    media_url: Optional[str],
    media_type: Optional[str],
    requested_by: Optional[str],
    approve_link: str,
    reject_link: str,
) -> str:
    # Escape ALL user-supplied strings before embedding in HTML to prevent
    # HTML / script injection inside the designer's email client.
    safe_title = escape_html(title)
    safe_platforms_str = escape_html(
        ", ".join(p.capitalize() for p in platforms) if platforms else "—"
    )
    safe_requester = escape_html(requested_by or "A team member")
    # Body: escape first, then convert newlines to <br/> so layout is preserved
    safe_body = escape_html(body or "").replace("\n", "<br/>")

    # Media URL is generated internally (not user-supplied), but still sanitise
    safe_media_url = escape_html(media_url or "")

    media_block = ""
    if media_url and media_type == "image":
        media_block = (
            f'<div style="margin:16px 0;">'
            f'<img src="{safe_media_url}" alt="Post media" '
            f'style="max-width:100%;border-radius:8px;border:1px solid #e2e8f0;" /></div>'
        )
    elif media_url and media_type == "video":
        media_block = (
            f'<div style="margin:16px 0;">'
            f'<a href="{safe_media_url}" style="color:#2563eb;">▶ View attached video</a></div>'
        )

    return f"""\
<!DOCTYPE html>
<html>
<body style="font-family:Arial,Helvetica,sans-serif;background:#f1f5f9;margin:0;padding:24px;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;
              overflow:hidden;border:1px solid #e2e8f0;">
    <div style="background:#0f172a;color:#ffffff;padding:20px 24px;">
      <h2 style="margin:0;font-size:18px;">Post approval requested</h2>
      <p style="margin:6px 0 0;font-size:13px;color:#cbd5e1;">
        {safe_requester} wants to publish to: {safe_platforms_str}
      </p>
    </div>
    <div style="padding:24px;">
      {media_block}
      <p style="margin:0 0 4px;font-size:12px;text-transform:uppercase;color:#64748b;
                font-weight:bold;letter-spacing:.05em;">Head caption</p>
      <p style="margin:0 0 16px;font-size:16px;font-weight:bold;color:#0f172a;">{safe_title}</p>

      <p style="margin:0 0 4px;font-size:12px;text-transform:uppercase;color:#64748b;
                font-weight:bold;letter-spacing:.05em;">Body caption</p>
      <div style="margin:0 0 24px;font-size:14px;color:#334155;line-height:1.6;">{safe_body}</div>

      <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;">
        <tr>
          <td style="padding-right:8px;width:50%;">
            <a href="{approve_link}" style="display:block;text-align:center;background:#16a34a;
               color:#ffffff;text-decoration:none;padding:12px 16px;border-radius:8px;
               font-weight:bold;font-size:14px;">✓ Approve &amp; Post</a>
          </td>
          <td style="padding-left:8px;width:50%;">
            <a href="{reject_link}" style="display:block;text-align:center;background:#dc2626;
               color:#ffffff;text-decoration:none;padding:12px 16px;border-radius:8px;
               font-weight:bold;font-size:14px;">✕ Reject</a>
          </td>
        </tr>
      </table>

      <p style="margin:20px 0 0;font-size:12px;color:#94a3b8;">
        Approving publishes the post immediately to the selected platforms.
        Rejecting blocks it. You can also review it in the QA Checker dashboard.
      </p>
    </div>
  </div>
</body>
</html>
"""


def send_approval_request(
    *,
    token: str,
    title: str,
    body: str,
    platforms: list[str],
    media_path: Optional[str],
    media_type: Optional[str],
    requested_by: Optional[str] = None,
) -> bool:
    """
    Send the approval-request email to the designer.

    Returns True on success, False otherwise (failure is non-fatal: the request
    still lives in the in-app QA queue).
    """
    if not is_email_configured():
        logger.warning(
            "Email not configured (SMTP_USERNAME/SMTP_PASSWORD/DESIGNER_EMAIL missing); "
            "skipping approval email. Request still available in the QA queue."
        )
        return False

    media_url = public_media_url(media_path)
    approve_link = _review_link(token, "approve")
    reject_link = _review_link(token, "reject")

    html = _build_html(
        title=title,
        body=body,
        platforms=platforms,
        media_url=media_url,
        media_type=media_type,
        requested_by=requested_by,
        approve_link=approve_link,
        reject_link=reject_link,
    )

    from_addr = settings.SMTP_FROM or settings.SMTP_USERNAME

    message = EmailMessage()
    message["Subject"] = f"[Approval needed] {title[:60]}"
    message["From"] = formataddr(("Kafi Social Agent", from_addr))
    message["To"] = settings.DESIGNER_EMAIL
    message.set_content(
        "A post needs your approval.\n\n"
        f"Head caption: {title}\n\n"
        f"Body caption:\n{body}\n\n"
        f"Approve: {approve_link}\n"
        f"Reject: {reject_link}\n"
    )
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        logger.info(f"Approval email sent to {settings.DESIGNER_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"Failed to send approval email: {e}")
        return False
