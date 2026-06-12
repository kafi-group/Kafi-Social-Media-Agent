"""
Input Sanitization Utilities

Guards against:
  - HTML/script injection in email templates (XSS via email)
  - Path traversal attacks in file path parameters
  - Excessively long string payloads
  - Null-byte injection

These helpers are intentionally thin wrappers so they can be used across
routes, services, and schemas without pulling in heavy dependencies.
"""

import html
import re


def escape_html(value: str) -> str:
    """
    HTML-escape a string so it is safe to embed in an HTML email or page.

    Converts < > & " ' into their HTML entity equivalents.
    Returns an empty string for falsy input.
    """
    if not value:
        return ""
    return html.escape(str(value), quote=True)


def sanitize_string(value: str, max_length: int = 10_000) -> str:
    """
    Strip leading/trailing whitespace, remove null bytes, and cap length.

    Use on any user-supplied text before storing or logging it.
    """
    if not value:
        return value
    cleaned = str(value).replace("\x00", "").strip()
    return cleaned[:max_length]


def validate_media_path(path: str) -> str:
    """
    Validate a stored media path to prevent path traversal.

    Accepts only paths of the form ``<subdir>/<filename>`` where both
    components consist of alphanumeric characters, hyphens, underscores,
    dots, or (for the subdir separator) a single forward slash.

    Raises ValueError on invalid input.
    """
    if not path:
        raise ValueError("Media path must not be empty")

    # Reject traversal sequences and absolute paths
    if ".." in path:
        raise ValueError("Path traversal detected in media path")
    if path.startswith("/") or path.startswith("\\"):
        raise ValueError("Absolute paths are not allowed for media paths")
    if "\\" in path:
        raise ValueError("Backslashes are not allowed in media paths")
    if "\x00" in path:
        raise ValueError("Null bytes detected in media path")

    # Allow only safe characters
    if not re.match(r"^[a-zA-Z0-9._/\-]+$", path):
        raise ValueError("Media path contains invalid characters")

    return path


def safe_error_detail(exc: Exception, fallback: str = "An unexpected error occurred") -> str:
    """
    Return a safe error message for HTTP responses.

    In production the raw exception message is never exposed to clients
    (it is only logged server-side).  In development the detail is surfaced
    so engineers can debug quickly.
    """
    from app.config import settings

    if settings.ENVIRONMENT == "production":
        return fallback
    return str(exc)
