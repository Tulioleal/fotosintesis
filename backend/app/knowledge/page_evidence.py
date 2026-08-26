from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser

from app.knowledge.acquisition import TrustedSourceValidator
from app.knowledge.safe_http import SafeHttpClient
from app.knowledge.source_urls import canonical_source_domain, canonical_source_url
from app.observability.logging import get_logger
from app.observability.tracing import get_trace_id
from app.providers.types import SearchResult


logger = get_logger(__name__)


MAX_EVIDENCE_CHARS = 4_000
MAX_RESPONSE_BYTES = 512_000
FETCH_TIMEOUT_SECONDS = 4
MAX_REDIRECTS = 3
SUPPORTED_CONTENT_TYPES = {
    "application/xhtml+xml",
    "text/html",
    "text/plain",
}


@dataclass(frozen=True)
class TrustedPageEvidence:
    result: SearchResult
    content: str | None = None
    error: str | None = None
    validation_status: str = "trusted"
    fetch_status: str = "not_fetched"
    fetch_error_category: str | None = None
    fetched_content_length: int = 0
    snippet_length: int = 0
    canonical_url: str | None = None
    retrieved_at: datetime | None = None
    published_at: datetime | None = None
    source_version: str | None = None
    response_content_type: str | None = None
    response_charset: str | None = None

    @property
    def evidence_text(self) -> str:
        return self.content or self.result.snippet

    @property
    def has_fetched_content(self) -> bool:
        return bool(self.content)

    @property
    def evidence_source(self) -> str:
        return "fetched_content" if self.has_fetched_content else "snippet"


class TrustedPageEvidenceFetcher:
    def __init__(
        self,
        trusted_sources: TrustedSourceValidator,
        *,
        timeout_seconds: int = FETCH_TIMEOUT_SECONDS,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        max_evidence_chars: int = MAX_EVIDENCE_CHARS,
        max_redirects: int = MAX_REDIRECTS,
        http_client: SafeHttpClient | None = None,
    ) -> None:
        self.trusted_sources = trusted_sources
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_evidence_chars = max_evidence_chars
        self.max_redirects = max_redirects
        self.http_client = http_client or SafeHttpClient(
            timeout=timeout_seconds,
            max_redirects=max_redirects,
            max_response_bytes=max_response_bytes,
            hostname_allowed=self._hostname_allowed,
        )

    def _hostname_allowed(self, hostname: str) -> bool:
        for approved in self.trusted_sources.approved_domains:
            if hostname == approved or hostname.endswith(f".{approved}"):
                return True
        return False

    async def fetch_all(self, results: list[SearchResult], *, limit: int = 3) -> list[TrustedPageEvidence]:
        canonicalized: list[SearchResult] = []
        for result in results:
            try:
                canonical_url = canonical_source_url(result.url)
            except ValueError:
                continue
            if canonical_url != result.url:
                result = result.model_copy(
                    update={
                        "url": canonical_url,
                        "source_domain": canonical_source_domain(canonical_url),
                    }
                )
            if self.trusted_sources.is_trusted(result):
                canonicalized.append(result)
        tasks = [self.fetch(result) for result in canonicalized[:limit]]
        return list(await asyncio.gather(*tasks)) if tasks else []

    async def fetch(self, result: SearchResult) -> TrustedPageEvidence:
        start = time.monotonic()
        snippet_length = len(result.snippet or "")
        if not self.trusted_sources.is_trusted(result):
            evidence = TrustedPageEvidence(
                result=result,
                error="untrusted source",
                fetch_status="skipped",
                fetch_error_category="untrusted_source",
                snippet_length=snippet_length,
            )
            _log_page_fetch(evidence, elapsed_seconds=time.monotonic() - start)
            return evidence
        try:
            fetch = await asyncio.to_thread(self._fetch_sync, result)
        except Exception as exc:
            evidence = TrustedPageEvidence(
                result=result,
                error=str(exc),
                fetch_status="failed",
                fetch_error_category=_fetch_error_category(exc),
                snippet_length=snippet_length,
            )
            _log_page_fetch(
                evidence,
                elapsed_seconds=time.monotonic() - start,
                error_type=type(exc).__name__,
            )
            return evidence
        if not fetch.content:
            evidence = TrustedPageEvidence(
                result=result,
                error="empty extracted content",
                fetch_status="empty",
                fetch_error_category="empty_content",
                snippet_length=snippet_length,
            )
            _log_page_fetch(evidence, elapsed_seconds=time.monotonic() - start)
            return evidence
        evidence = TrustedPageEvidence(
            result=fetch.result,
            content=fetch.content,
            fetch_status="fetched",
            fetched_content_length=len(fetch.content),
            snippet_length=snippet_length,
            canonical_url=fetch.canonical_url,
            retrieved_at=fetch.retrieved_at,
            published_at=fetch.published_at,
            source_version=fetch.source_version,
            response_content_type=fetch.response_content_type,
            response_charset=fetch.response_charset,
        )
        _log_page_fetch(evidence, elapsed_seconds=time.monotonic() - start)
        return evidence

    def _fetch_sync(self, result: SearchResult) -> _FetchOutcome:
        canonical = canonical_source_url(result.url)
        http_result = self.http_client.get(canonical)

        headers = _normalized_response_headers(http_result.headers)
        content_type = headers.get("content-type") or ""
        parsed_type = content_type.split(";", 1)[0].strip().lower()
        if parsed_type not in SUPPORTED_CONTENT_TYPES:
            raise ValueError(f"unsupported content type: {parsed_type}")
        if len(http_result.body) > self.max_response_bytes:
            raise ValueError("response exceeded maximum size")
        charset = "utf-8"
        for part in content_type.split(";")[1:]:
            key, separator, value = part.partition("=")
            if separator and key.strip().lower() == "charset":
                charset = value.strip().strip('"') or "utf-8"
                break

        text = http_result.body.decode(charset, errors="replace")
        if parsed_type in {"text/html", "application/xhtml+xml"}:
            text = extract_readable_text(text)
        content = normalize_evidence_text(text, limit=self.max_evidence_chars)

        final_result = result.model_copy(
            update={
                "url": http_result.final_url,
                "source_domain": canonical_source_domain(http_result.final_url),
            }
        )
        return _FetchOutcome(
            result=final_result,
            content=content,
            canonical_url=http_result.final_url,
            retrieved_at=datetime.now(UTC),
            published_at=None,
            source_version=_source_version_from_headers(headers, content),
            response_content_type=parsed_type,
            response_charset=charset,
        )


@dataclass(frozen=True)
class _FetchOutcome:
    result: SearchResult
    content: str
    canonical_url: str
    retrieved_at: datetime
    published_at: datetime | None
    source_version: str | None
    response_content_type: str | None
    response_charset: str | None


def _normalized_response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {str(key).casefold(): value for key, value in headers.items()}


def _source_version_from_headers(headers: dict[str, str], content: str) -> str:
    """Derive a deterministic source version from fetch metadata.

    Precedence: strong normalized ETag, valid normalized Last-Modified,
    then a SHA-256 of the normalized fetched content. The version is never
    derived from a search snippet.
    """
    normalized = _normalized_response_headers(headers)
    etag = (normalized.get("etag") or "").strip().strip('"')
    if etag:
        return f"etag:{etag}"
    last_modified = (normalized.get("last-modified") or "").strip()
    if last_modified:
        return f"last-modified:{last_modified}"
    import hashlib
    import re as _re

    normalized = _re.sub(r"\s+", " ", content).strip()
    return f"sha256:{hashlib.sha256(normalized.encode()).hexdigest()}"


class _ReadableTextParser(HTMLParser):
    ignored_tags = {
        "script", "style", "noscript", "svg", "canvas", "iframe",
        "nav", "header", "footer", "form", "button", "select", "option",
    }

    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.ignored_tags:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        value = data.strip()
        if value:
            self.parts.append(value)


def extract_readable_text(html: str) -> str:
    parser = _ReadableTextParser()
    parser.feed(html)
    return " ".join(parser.parts)


def normalize_evidence_text(text: str, *, limit: int = MAX_EVIDENCE_CHARS) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rsplit(" ", 1)[0].strip()


def _fetch_error_category(exc: Exception) -> str:
    message = str(exc).casefold()
    if "timed out" in message or isinstance(exc, TimeoutError):
        return "timeout"
    if "unsupported content type" in message:
        return "unsupported_content_type"
    if "redirect" in message:
        return "redirect"
    if "unsafe destination" in message or "untrusted" in message:
        return "unsafe_destination"
    if "maximum size" in message:
        return "too_large"
    if "http error 403" in message or "forbidden" in message:
        return "blocked"
    if "http error 404" in message or "not found" in message:
        return "not_found"
    return "fetch_error"


def _log_page_fetch(
    evidence: TrustedPageEvidence,
    *,
    elapsed_seconds: float,
    error_type: str | None = None,
) -> None:
    logger.info(
        "trusted page evidence fetch completed",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_fetch_status": evidence.fetch_status,
            "ctx_fetch_error_category": evidence.fetch_error_category,
            "ctx_error_type": error_type,
            "ctx_fetched_content_length": evidence.fetched_content_length,
            "ctx_snippet_length": evidence.snippet_length,
            "ctx_elapsed_seconds": round(elapsed_seconds, 6),
        },
    )
