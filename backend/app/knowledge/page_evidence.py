from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.knowledge.acquisition import TrustedSourceValidator
from app.observability.logging import get_logger
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

    @property
    def evidence_text(self) -> str:
        return self.content or self.result.snippet


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
        if not self.trusted_sources.is_trusted(result):
            return TrustedPageEvidence(result=result, error="untrusted source")
        try:
            content = await asyncio.to_thread(self._fetch_sync, result)
        except Exception as exc:
            logger.debug(
                "trusted page evidence fetch failed",
                extra={
                    "ctx_source_domain": result.source_domain,
                    "ctx_error_type": type(exc).__name__,
                    "ctx_error": str(exc),
                },
            )
            return TrustedPageEvidence(result=result, error=str(exc))
        if not content:
            return TrustedPageEvidence(result=result, error="empty extracted content")
        return TrustedPageEvidence(result=result, content=content)

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
    ignored_tags = {"script", "style", "noscript", "svg", "canvas", "iframe"}

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
