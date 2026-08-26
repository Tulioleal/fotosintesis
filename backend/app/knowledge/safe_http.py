"""Bounded HTTPS transport for trusted page evidence.

The academic contract requires HTTPS, an approved source hostname before and
after redirects, bounded redirects, a request timeout, supported text content
types, and a bounded response body. Redirects are followed manually so every
hop is re-validated. Credentials and cookies are never forwarded, and failures
use the bounded ``unsafe_destination`` category. Production-grade DNS pinning
and peer-IP verification are deliberately out of scope for this academic
project; standard hostname TLS verification remains.
"""

from __future__ import annotations

import http.client
import logging
import ssl
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from app.knowledge.source_urls import canonical_source_url

logger = logging.getLogger(__name__)

UNSAFE_DESTINATION_CATEGORY = "unsafe_destination"
MAX_REDIRECTS_DEFAULT = 3
MAX_RESPONSE_BYTES_DEFAULT = 512_000


class UnsafeDestinationError(RuntimeError):
    def __init__(self, *, detail: str = "") -> None:
        self.category = UNSAFE_DESTINATION_CATEGORY
        super().__init__(detail or "unsafe destination")


@dataclass(frozen=True)
class SafeFetchResult:
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes


class SafeHttpClient:
    def __init__(
        self,
        *,
        timeout: float = 4.0,
        max_redirects: int = MAX_REDIRECTS_DEFAULT,
        max_response_bytes: int = MAX_RESPONSE_BYTES_DEFAULT,
        hostname_allowed: Callable[[str], bool] | None = None,
        connection_factory: Callable[[str], http.client.HTTPSConnection] | None = None,
        context: ssl.SSLContext | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.max_response_bytes = max_response_bytes
        self.hostname_allowed = hostname_allowed
        self.connection_factory = connection_factory
        self.context = context or ssl.create_default_context()

    def get(self, url: str) -> SafeFetchResult:
        current = url
        for hop in range(self.max_redirects + 1):
            try:
                canonical = canonical_source_url(current)
            except ValueError as exc:
                raise UnsafeDestinationError(detail="invalid or unsafe URL") from exc
            parsed = urlsplit(canonical)
            hostname = parsed.hostname
            if not hostname:
                raise UnsafeDestinationError(detail="missing hostname")
            if self.hostname_allowed is not None and not self.hostname_allowed(hostname):
                raise UnsafeDestinationError(detail="untrusted redirect hostname")
            port = parsed.port or 443
            path = canonical[len(f"{parsed.scheme}://{parsed.netloc}") :] or "/"
            connection = self._connection(hostname, port)
            try:
                connection.request(
                    "GET",
                    path,
                    headers={
                        "User-Agent": "FotosintesisBot/1.0 (+trusted botanical evidence fetch)",
                        "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.1",
                        "Host": hostname,
                    },
                )
                response = connection.getresponse()
                # Read at most the configured byte limit plus one
                # overflow-detection byte, then reject an oversized body
                # without ever buffering the complete response.
                body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise UnsafeDestinationError(detail="response exceeded maximum size")
                headers = {
                    str(key).casefold(): value
                    for key, value in response.getheaders()
                }
            finally:
                connection.close()

            location = headers.get("location")
            if response.status in (301, 302, 303, 307, 308) and location:
                if hop >= self.max_redirects:
                    raise UnsafeDestinationError(detail="redirect limit exceeded")
                current = self._resolve_redirect(canonical, location)
                continue
            if response.status not in (200, 206):
                raise UnsafeDestinationError(detail=f"unexpected status {response.status}")
            return SafeFetchResult(
                final_url=canonical,
                status=response.status,
                headers=headers,
                body=body,
            )
        raise UnsafeDestinationError(detail="redirect limit exceeded")

    def _connection(self, hostname: str, port: int) -> http.client.HTTPSConnection:
        if self.connection_factory is not None:
            return self.connection_factory(hostname)
        return http.client.HTTPSConnection(
            hostname,
            port,
            timeout=self.timeout,
            context=self.context,
        )

    @staticmethod
    def _resolve_redirect(base_url: str, location: str) -> str:
        from urllib.parse import urljoin

        if location.startswith(("http://", "https://")):
            return location
        if location.startswith("//"):
            parsed = urlsplit(base_url)
            return f"{parsed.scheme}:{location}"
        return urljoin(base_url, location)


__all__ = [
    "MAX_REDIRECTS_DEFAULT",
    "MAX_RESPONSE_BYTES_DEFAULT",
    "UNSAFE_DESTINATION_CATEGORY",
    "SafeFetchResult",
    "SafeHttpClient",
    "UnsafeDestinationError",
]
