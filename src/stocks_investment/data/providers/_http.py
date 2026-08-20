"""Small, dependency-free HTTP boundary shared by external providers."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    """Base class for expected provider failures."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected a request because of quota/rate limiting."""


class ProviderTimeoutError(ProviderError):
    """The provider did not answer within the configured timeout."""


class ProviderSchemaError(ProviderError):
    """The provider returned a response outside its documented contract."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    body: bytes
    status: int


Transport = Callable[[str, dict[str, str], float], HttpResponse]


def request_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    retries: int,
    backoff: float,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Fetch JSON with bounded retries; never retries malformed successful data."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = (transport or _urlopen_transport)(url, headers, timeout)
            if response.status == 429:
                raise ProviderRateLimitError(f"provider rate limit for {url}")
            if response.status >= 500:
                raise ProviderError(f"provider server error {response.status} for {url}")
            if response.status >= 400:
                raise ProviderError(f"provider HTTP error {response.status} for {url}")
            try:
                value = json.loads(response.body)
            except (TypeError, ValueError) as exc:
                raise ProviderSchemaError(f"provider returned invalid JSON for {url}") from exc
            if not isinstance(value, dict):
                raise ProviderSchemaError(f"provider JSON root is not an object for {url}")
            return value
        except ProviderRateLimitError:
            last_error = ProviderRateLimitError(f"provider rate limit for {url}")
            if attempt >= retries:
                raise last_error
        except ProviderTimeoutError:
            last_error = ProviderTimeoutError(f"provider timeout for {url}")
            if attempt >= retries:
                raise last_error
        except ProviderError as exc:
            last_error = exc
            if attempt >= retries:
                raise
        except (HTTPError, HTTPException, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt >= retries:
                raise ProviderError(f"provider request failed for {url}") from exc
        if backoff:
            time.sleep(backoff * (2**attempt))
    raise ProviderError("provider request failed") from last_error


def _urlopen_transport(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as response:
            return HttpResponse(response.read(), response.status)
    except TimeoutError as exc:
        raise ProviderTimeoutError(f"provider timeout for {url}") from exc
