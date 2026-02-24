"""Simple in-memory rate limiter dependency."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

from shared.config import get_settings

_request_counters: dict[str, int] = defaultdict(int)


def rate_limit_dependency(request: Request) -> None:
    """Apply per-IP/minute limits.

    This is a lightweight limiter suitable for single-instance dev setups.
    """

    settings = get_settings()
    now = datetime.now(timezone.utc)
    bucket = now.strftime("%Y%m%d%H%M")
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}:{bucket}"

    _request_counters[key] += 1
    if _request_counters[key] > settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
        )

    expired_prefix = now.strftime("%Y%m%d%H")
    stale_keys = [k for k in _request_counters if expired_prefix not in k]
    for stale_key in stale_keys:
        _request_counters.pop(stale_key, None)
