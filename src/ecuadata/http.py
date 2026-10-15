"""Shared HTTP client: one user agent, timeouts, throttling and retries for every provider.

Government sites block IPs that send too many requests too quickly, so every request waits
``MIN_INTERVAL`` after the previous one, and a connection that cannot be opened at all is not
retried (it usually means the server is refusing us, and retrying makes it worse).
"""

from __future__ import annotations

import time

import httpx

from ecuadata.config import config
from ecuadata.exceptions import SourceUnavailableError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36 ecuadata (+https://github.com/bernabecj/ec-public-data)"
)
RETRIES = 3
BACKOFF = 5.0  # seconds; doubles after each failed attempt
MIN_INTERVAL = 2.0  # seconds between consecutive requests

_last_request = 0.0


def make_client() -> httpx.Client:
    """Build the client used for every request. Tests replace this to inject a mock transport."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=config.timeout,
        follow_redirects=True,
    )


def _throttle() -> None:
    global _last_request
    wait = _last_request + MIN_INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def get(url: str) -> httpx.Response:
    """GET ``url``, retrying read errors and 5xx responses.

    Any other status (including 404) is returned to the caller to interpret.

    Raises:
        SourceUnavailableError: the server could not be reached, or kept failing.
    """
    delay = BACKOFF
    last_error = ""
    with make_client() as client:
        for attempt in range(RETRIES):
            _throttle()
            try:
                response = client.get(url)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise SourceUnavailableError(
                    f"Could not connect to {url} ({type(exc).__name__}: {exc}). The server may "
                    "be down or blocking your IP after too many requests; try again later or "
                    "from another network."
                ) from exc
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code < 500:
                    return response
                last_error = f"HTTP {response.status_code}"
            if attempt < RETRIES - 1:
                time.sleep(delay)
                delay *= 2
    raise SourceUnavailableError(
        f"Could not download {url} after {RETRIES} attempts ({last_error})."
    )
