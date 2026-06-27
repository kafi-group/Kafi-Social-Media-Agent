"""
Rate Limiter Configuration (slowapi)

Per-IP rate limits to prevent:
  - DoS / resource exhaustion against LLM endpoints
  - Brute-force attacks against the PIN verification endpoint

Usage in route files:
    from app.middleware.rate_limiter import limiter
    from fastapi import Request

    @router.post("/some-endpoint")
    @limiter.limit("10/minute")
    async def handler(request: Request, ...):
        ...

The limiter instance is also attached to the FastAPI app in main.py so
slowapi can inject the rate-limit exceeded handler automatically.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["300/minute"],   # global fallback per IP
)
