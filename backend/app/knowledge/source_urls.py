"""Canonical source URL identity for trusted botanical evidence.

Equivalent source URLs converge on one canonical URL used for trust
validation, search-result deduplication, judge source packages, judge support
lookup, the persisted source URL, and content identity hashes. Query order is
preserved; queries are never sorted and tracking parameters are never removed.
"""

from __future__ import annotations

import posixpath
import re
from urllib.parse import unquote, urlsplit, urlunsplit

URL_CANONICALIZATION_VERSION = 2

_UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
_HEX = frozenset("0123456789abcdefABCDEF")
_HOSTNAME_CHARS = re.compile(r"^[A-Za-z0-9.-]+$")


def _normalize_unreserved_percent(value: str) -> str:
    out: list[str] = []
    index = 0
    length = len(value)
    while index < length:
        char = value[index]
        if char == "%" and index + 2 < length and value[index + 1] in _HEX and value[index + 2] in _HEX:
            decoded = chr(int(value[index + 1 : index + 3], 16))
            if decoded in _UNRESERVED:
                out.append(decoded)
                index += 3
                continue
        out.append(char)
        index += 1
    return "".join(out)


def _remove_dot_segments(path: str) -> str:
    """Dot-segment normalization (RFC 3986 semantics via posixpath)."""
    if not path:
        return "/"

    had_trailing_slash = path.endswith("/")
    trailing_dot_segment = path.endswith(("/.", "/.."))

    normalized = posixpath.normpath(path)
    if normalized == ".":
        normalized = ""
    if not normalized.startswith("/"):
        normalized = "/" + normalized

    if (
        (had_trailing_slash or trailing_dot_segment)
        and normalized != "/"
        and not normalized.endswith("/")
    ):
        normalized += "/"

    return normalized


def _idna_hostname(hostname: str) -> str:
    if ":" in hostname:
        return hostname
    decoded = unquote(hostname)
    if any(ch.isspace() or ch in "/@%#" for ch in decoded):
        raise ValueError(f"invalid IDNA hostname: {hostname!r}")
    try:
        return decoded.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError(f"invalid IDNA hostname: {hostname!r}") from exc


def canonical_source_url(value: object) -> str:
    """Canonicalize an absolute HTTPS URL into its stable source identity.

    Rejects non-absolute-HTTPS URLs, userinfo, missing hostnames, and invalid
    ports. Lowercases the scheme and hostname, applies IDNA normalization,
    removes trailing DNS dots and the default 443 port, normalizes empty paths
    and dot segments, removes fragments, and normalizes unreserved
    percent-encoding while preserving query order.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("canonical source URL must be a non-empty string")
    parts = urlsplit(value.strip())
    scheme = parts.scheme.lower()
    if scheme != "https":
        raise ValueError("canonical source URLs must be absolute HTTPS")
    if "@" in parts.netloc or parts.username is not None:
        raise ValueError("canonical source URLs must not contain userinfo")
    hostname = parts.hostname
    if not hostname:
        raise ValueError("canonical source URL requires a hostname")
    hostname = _idna_hostname(hostname.rstrip("."))
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("canonical source URL has an invalid port") from exc
    netloc = hostname
    if port is not None and port != 443:
        netloc = f"{hostname}:{port}"
    path = parts.path
    if not path:
        path = "/"
    normalized_path = _remove_dot_segments(path)
    normalized_path = _normalize_unreserved_percent(normalized_path)
    query = _normalize_unreserved_percent(parts.query)
    return urlunsplit((scheme, netloc, normalized_path, query, ""))


def canonical_source_domain(canonical_url: str) -> str:
    """Hostname-only source domain derived from a canonical URL."""
    hostname = urlsplit(canonical_url).hostname
    if not hostname:
        raise ValueError("canonical source URL requires a hostname")
    return hostname.rstrip(".")


__all__ = [
    "URL_CANONICALIZATION_VERSION",
    "canonical_source_domain",
    "canonical_source_url",
]
