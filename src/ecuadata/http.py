"""Shared HTTP client: one user agent, timeouts and retries for every provider."""

from __future__ import annotations

import time

import httpx

from ecuadata.config import config
from ecuadata.exceptions import SourceUnavailableError

USER_AGENT = "ecuadata (+https://github.com/bernabecj/ec-public-data)"
RETRIES = 3
BACKOFF = 1.0  # seconds; doubles after each failed attempt


def make_client() -> httpx.Client:
    """Build the client used for every request. Tests replace this to inject a mock transport."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=config.timeout,
        follow_redirects=True,
    )


def get(url: str) -> httpx.Response:
    """GET ``url``, retrying connection errors and 5xx responses.

    Any other status (including 404) is returned to the caller to interpret.

    Raises:
        SourceUnavailableError: the server could not be reached, or kept answering 5xx.
    """
    delay = BACKOFF
    last_error = ""
    with make_client() as client:
        for attempt in range(RETRIES):
            try:
                response = client.get(url)
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
