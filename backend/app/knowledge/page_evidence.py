from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.knowledge.acquisition import TrustedSourceValidator
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
    ) -> None:
        self.trusted_sources = trusted_sources
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_evidence_chars = max_evidence_chars
        self.max_redirects = max_redirects

    async def fetch_all(self, results: list[SearchResult], *, limit: int = 3) -> list[TrustedPageEvidence]:
        trusted = [result for result in results if self.trusted_sources.is_trusted(result)]
        tasks = [self.fetch(result) for result in trusted[:limit]]
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
            content = await asyncio.to_thread(self._fetch_sync, result)
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
        if not content:
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
            result=result,
            content=content,
            fetch_status="fetched",
            fetched_content_length=len(content),
            snippet_length=snippet_length,
        )
        _log_page_fetch(evidence, elapsed_seconds=time.monotonic() - start)
        return evidence

    def _fetch_sync(self, result: SearchResult) -> str:
        parsed = urlparse(result.url)
        if parsed.scheme != "https":
            raise ValueError("only HTTPS URLs are allowed")

        request = Request(
            result.url,
            headers={
                "User-Agent": "FotosintesisBot/1.0 (+trusted botanical evidence fetch)",
                "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.1",
            },
        )
        opener = build_opener(_BoundedRedirectHandler(self.max_redirects))
        try:
            with opener.open(request, timeout=self.timeout_seconds) as response:
                final_url = response.geturl()
                final_domain = urlparse(final_url).netloc
                final_result = SearchResult(
                    title=result.title,
                    url=final_url,
                    snippet=result.snippet,
                    source_domain=final_domain,
                )
                if not self.trusted_sources.is_trusted(final_result):
                    raise ValueError("redirected outside trusted HTTPS source")

                content_type = response.headers.get_content_type()
                if content_type not in SUPPORTED_CONTENT_TYPES:
                    raise ValueError(f"unsupported content type: {content_type}")

                body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise ValueError("response exceeded maximum size")
                charset = response.headers.get_content_charset() or "utf-8"
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ValueError(f"page fetch failed: {exc}") from exc

        text = body.decode(charset, errors="replace")
        if content_type in {"text/html", "application/xhtml+xml"}:
            text = extract_readable_text(text)
        return normalize_evidence_text(text, limit=self.max_evidence_chars)


class _BoundedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, max_redirects: int) -> None:
        self.max_redirects = max_redirects
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirect_count = int(req.headers.get("X-Fotosintesis-Redirect-Count", "0")) + 1
        if redirect_count > self.max_redirects:
            raise HTTPError(newurl, code, "too many redirects", headers, fp)
        new_request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_request is not None:
            new_request.add_header("X-Fotosintesis-Redirect-Count", str(redirect_count))
        return new_request


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
    result = evidence.result
    logger.info(
        "trusted page evidence fetch completed",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_source_domain": result.source_domain,
            "ctx_url_hash": hashlib.sha256(result.url.encode("utf-8")).hexdigest()[:16],
            "ctx_fetch_status": evidence.fetch_status,
            "ctx_fetch_error_category": evidence.fetch_error_category,
            "ctx_error_type": error_type,
            "ctx_fetched_content_length": evidence.fetched_content_length,
            "ctx_snippet_length": evidence.snippet_length,
            "ctx_elapsed_seconds": round(elapsed_seconds, 6),
        },
    )
