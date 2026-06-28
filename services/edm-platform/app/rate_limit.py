"""A small in-process sliding-window rate limiter for the auth endpoints.

No Redis is available (ADR-0003/0004), so this is a module-level dict, not a shared
store -- it only limits attempts within a single server process. A deployment running
multiple instances behind a load balancer would need a shared backend (Redis, or the
database itself) for this to hold across instances; that's a real limitation of this
approach, not an oversight, and is the honest tradeoff for a $0, infra-light stack.

Login is checked against both the caller's IP and the target email, since either alone
has a gap: IP-only lets an attacker spread one account's guesses across many source
IPs (credential stuffing); email-only lets one IP brute-force many different accounts
unchecked.
"""

import time
from collections import defaultdict

from fastapi import Request

from app.config import settings
from app.modules.core.exceptions import TooManyRequestsError

_attempts: dict[str, list[float]] = defaultdict(list)


def _check(key: str) -> None:
    now = time.monotonic()
    window_start = now - settings.auth_rate_limit_window_seconds
    timestamps = [t for t in _attempts[key] if t > window_start]
    if len(timestamps) >= settings.auth_rate_limit_max_attempts:
        raise TooManyRequestsError(
            f"too many attempts; try again in {settings.auth_rate_limit_window_seconds} seconds"
        )
    timestamps.append(now)
    _attempts[key] = timestamps


def enforce_auth_rate_limit(request: Request, email: str) -> None:
    client_host = request.client.host if request.client else "unknown"
    _check(f"ip:{client_host}")
    _check(f"email:{email.lower()}")


def reset() -> None:
    """Test-only: clears all tracked attempts. The dict above is a module-level
    singleton (the whole point -- it must be shared across requests within one
    process), so without this, attempts recorded by one test would carry over into
    the next test's assertions about the same client IP."""
    _attempts.clear()
