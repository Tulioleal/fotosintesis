"""Bounded academic trusted-fetch transport tests."""

from __future__ import annotations

import logging

import pytest

from app.knowledge.safe_http import (
    SafeFetchResult,
    SafeHttpClient,
    UnsafeDestinationError,
)


class _FakeConnection:
    def __init__(self, *, status=200, headers=None, body=b"", redirects=None) -> None:
        self._status = status
        self._headers = headers or {}
        self._body = body
        self._redirects = redirects or {}
        self.requested: list[tuple[str, str, dict]] = []
        self.response: _FakeResponse | None = None

    def request(self, method: str, url: str, headers: dict) -> None:
        self.requested.append((method, url, headers))

    def getresponse(self):
        url = self.requested[-1][1]
        response_meta = self._redirects.get(url, {})
        status = response_meta.get("status", self._status)
        headers = response_meta.get("headers", self._headers)
        body = response_meta.get("body", self._body)
        self.response = _FakeResponse(status, headers, body)
        return self.response

    def close(self) -> None:
        pass


class _FakeResponse:
    def __init__(self, status: int, headers: dict, body: bytes) -> None:
        self.status = status
        self.headers = headers
        self.body = body
        self.read_sizes: list[int | None] = []

    def read(self, size: int | None = None) -> bytes:
        self.read_sizes.append(size)
        if size is None:
            return self.body
        return self.body[:size]

    def getheaders(self):
        return list(self.headers.items())


def _client(*, factory, max_redirects: int = 3, max_response_bytes: int = 512_000) -> SafeHttpClient:
    return SafeHttpClient(
        connection_factory=factory,
        max_redirects=max_redirects,
        max_response_bytes=max_response_bytes,
    )


def test_non_https_url_is_rejected_before_fetch() -> None:
    def factory(hostname: str):
        raise AssertionError("connection must never be attempted")

    client = _client(factory=factory)
    with pytest.raises(UnsafeDestinationError, match="invalid or unsafe URL"):
        client.get("http://public.example/start")


def test_untrusted_hostname_is_rejected() -> None:
    def factory(hostname: str):
        raise AssertionError(f"connection must never be attempted for {hostname}")

    client = SafeHttpClient(
        connection_factory=factory,
        hostname_allowed=lambda hostname: hostname in {"public.example"},
    )
    with pytest.raises(UnsafeDestinationError, match="untrusted"):
        client.get("https://blog.invalid/other")


def test_https_downgrade_is_rejected() -> None:
    def factory(hostname: str):
        return _FakeConnection(
            status=302,
            headers={"Location": "http://public.example/start"},
        )

    client = _client(factory=factory)
    with pytest.raises(UnsafeDestinationError):
        client.get("https://public.example/start")


def test_untrusted_redirect_hostname_is_rejected() -> None:
    def factory(hostname: str):
        return _FakeConnection(
            status=302,
            headers={"Location": "https://blog.invalid/other"},
        )

    client = SafeHttpClient(
        connection_factory=factory,
        hostname_allowed=lambda hostname: hostname in {"public.example"},
    )
    with pytest.raises(UnsafeDestinationError, match="untrusted"):
        client.get("https://public.example/start")


def test_redirect_limit_is_enforced() -> None:
    def factory(hostname: str):
        return _FakeConnection(
            status=302,
            headers={"Location": "https://public.example/again"},
        )

    client = _client(factory=factory, max_redirects=2)
    with pytest.raises(UnsafeDestinationError, match="redirect limit"):
        client.get("https://public.example/start")


def test_unexpected_status_is_rejected() -> None:
    def factory(hostname: str):
        return _FakeConnection(status=403, headers={}, body=b"forbidden")

    client = _client(factory=factory)
    with pytest.raises(UnsafeDestinationError, match="unexpected status"):
        client.get("https://public.example/start")


def test_valid_public_https_fetch_succeeds() -> None:
    def factory(hostname: str):
        assert hostname == "public.example"
        return _FakeConnection(
            status=200,
            headers={"Content-Type": "text/html"},
            body=b"<html><body>ok</body></html>",
        )

    client = _client(factory=factory)
    result = client.get("https://public.example/care")
    assert isinstance(result, SafeFetchResult)
    assert result.final_url == "https://public.example/care"
    assert result.body == b"<html><body>ok</body></html>"


def test_fetch_reads_at_most_limit_plus_one_overflow_byte() -> None:
    connection = _FakeConnection(status=200, headers={}, body=b"x" * 5)
    captured = [connection]

    def factory(hostname: str):
        return captured[0]

    client = _client(factory=factory, max_response_bytes=5)
    result = client.get("https://public.example/care")
    assert result.body == b"x" * 5
    assert connection.response is not None
    assert connection.response.read_sizes == [6]


def test_fetch_rejects_oversized_response_without_buffering_full_body() -> None:
    connection = _FakeConnection(status=200, headers={}, body=b"x" * 100)
    captured = [connection]

    def factory(hostname: str):
        return captured[0]

    client = _client(factory=factory, max_response_bytes=5)
    with pytest.raises(UnsafeDestinationError, match="maximum size"):
        client.get("https://public.example/care")
    # The client read only limit + 1 overflow-detection bytes, never the
    # complete response body.
    assert connection.response is not None
    assert connection.response.read_sizes == [6]


def test_redirect_followed_manually_to_final_canonical_url() -> None:
    def factory(hostname: str):
        if hostname == "public.example":
            return _FakeConnection(
                status=302,
                headers={"Location": "https://cdn.example.org/final"},
            )
        return _FakeConnection(status=200, headers={}, body=b"final")

    client = SafeHttpClient(
        connection_factory=factory,
        hostname_allowed=lambda hostname: hostname in {"public.example", "cdn.example.org"},
    )
    result = client.get("https://public.example/start")
    assert result.final_url == "https://cdn.example.org/final"


def test_unsafe_failures_use_bounded_category() -> None:
    def factory(hostname: str):
        raise UnsafeDestinationError(detail="blocked")

    client = _client(factory=factory)
    with pytest.raises(UnsafeDestinationError) as exc_info:
        client.get("https://public.example/start")
    assert exc_info.value.category == "unsafe_destination"


def test_redirect_location_header_is_case_insensitive() -> None:
    calls = 0

    def factory(hostname: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _FakeConnection(
                status=302,
                headers={"location": "https://public.example/final"},
            )
        return _FakeConnection(
            status=200,
            headers={"content-type": "text/plain"},
            body=b"final",
        )

    result = _client(factory=factory).get("https://public.example/start")

    assert result.final_url == "https://public.example/final"
    assert result.body == b"final"


def test_lowercase_content_type_is_accepted() -> None:
    def factory(hostname: str):
        return _FakeConnection(
            status=200,
            headers={"content-type": "text/plain"},
            body=b"lowercase headers ok",
        )

    result = _client(factory=factory).get("https://public.example/start")
    assert result.status == 200
    assert result.body == b"lowercase headers ok"


def test_mixed_case_redirect_still_rejected_for_untrusted_hostname() -> None:
    def factory(hostname: str):
        return _FakeConnection(
            status=302,
            headers={"LoCaTiOn": "https://blog.invalid/other"},
        )

    client = SafeHttpClient(
        connection_factory=factory,
        hostname_allowed=lambda hostname: hostname in {"public.example"},
    )
    with pytest.raises(UnsafeDestinationError, match="untrusted"):
        client.get("https://public.example/start")
