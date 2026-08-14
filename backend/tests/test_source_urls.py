"""Canonical source URL identity tests."""

from __future__ import annotations

import pytest

from app.knowledge.source_urls import (
    URL_CANONICALIZATION_VERSION,
    canonical_source_domain,
    canonical_source_url,
)


def test_equivalent_urls_converge() -> None:
    equivalent = [
        "https://Example.COM/path",
        "HTTPS://example.com/path",
        "https://example.com:443/path",
        "https://example.com./path",
        "https://example.com/path#fragment",
        "https://example.com/./path",
        "https://example.com/a/../path",
        "https://example.com/%70ath",
    ]
    canonical = canonical_source_url("https://example.com/path")
    for value in equivalent:
        assert canonical_source_url(value) == canonical


def test_empty_path_normalizes_to_slash() -> None:
    assert canonical_source_url("https://example.com") == "https://example.com/"
    assert canonical_source_url("https://example.com/") == "https://example.com/"


def test_query_order_is_preserved() -> None:
    left = canonical_source_url("https://example.com/a?x=1&y=2&z=3")
    right = canonical_source_url("https://example.com/a?z=3&y=2&x=1")
    assert left == "https://example.com/a?x=1&y=2&z=3"
    assert left != right


def test_tracking_parameters_are_not_removed() -> None:
    value = "https://example.com/a?utm_source=x&ref=y&id=z"
    assert canonical_source_url(value) == value


def test_non_equivalent_urls_differ() -> None:
    assert canonical_source_url("https://example.com/a") != canonical_source_url(
        "https://example.com/b"
    )
    assert canonical_source_url("https://example.com") != canonical_source_url(
        "https://example.org"
    )
    assert canonical_source_url("https://example.com:8443/a") != canonical_source_url(
        "https://example.com/a"
    )
    assert canonical_source_url("https://example.com/a?x=1") != canonical_source_url(
        "https://example.com/a?x=2"
    )


def test_idna_hostnames_normalize() -> None:
    assert (
        canonical_source_url("https://b%C3%BCcher.example/")
        == "https://xn--bcher-kva.example/"
    )
    assert (
        canonical_source_url("https://xn--bcher-kva.example/")
        == "https://xn--bcher-kva.example/"
    )


def test_malformed_hosts_are_rejected() -> None:
    with pytest.raises(ValueError):
        canonical_source_url("https:///path")
    with pytest.raises(ValueError):
        canonical_source_url("https://exa mple.com/path")
    with pytest.raises(ValueError):
        canonical_source_url("https://example.com:notaport/")
    with pytest.raises(ValueError):
        canonical_source_url("https://:443/")


def test_userinfo_is_rejected() -> None:
    with pytest.raises(ValueError):
        canonical_source_url("https://user:pass@example.com/")
    with pytest.raises(ValueError):
        canonical_source_url("https://user@example.com/")


def test_non_https_is_rejected() -> None:
    for value in (
        "http://example.com/",
        "ftp://example.com/",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "",
        "example.com",
    ):
        with pytest.raises(ValueError):
            canonical_source_url(value)


def test_fragments_are_removed_and_ports_normalized() -> None:
    assert canonical_source_url("https://example.com/a#frag") == "https://example.com/a"
    assert canonical_source_url("https://example.com:443/a#frag") == "https://example.com/a"
    assert canonical_source_url("https://example.com:8443/a#frag") == "https://example.com:8443/a"


def test_source_domain_is_hostname_only() -> None:
    assert canonical_source_domain("https://sub.example.com:8443/a?x=1") == "sub.example.com"
    with pytest.raises(ValueError):
        canonical_source_domain("not a url")


def test_distinct_paths_preserve_source_identity_distinction() -> None:
    assert canonical_source_url("https://example.com/a") != canonical_source_url(
        "https://example.com/b"
    )
    assert canonical_source_url("https://example.com/a/b") != canonical_source_url(
        "https://example.com/a"
    )
    assert canonical_source_url("https://example.com/a%2Fb") != canonical_source_url(
        "https://example.com/a/b"
    )


def test_distinct_ordered_query_values_preserve_source_identity() -> None:
    # Ordered query values are semantically significant and must stay distinct.
    assert canonical_source_url("https://example.com/a?x=1&y=2") != canonical_source_url(
        "https://example.com/a?x=1&y=3"
    )
    assert canonical_source_url("https://example.com/a?x=1") != canonical_source_url(
        "https://example.com/a?y=1"
    )
    # Order matters: reordering yields a different source identity.
    assert canonical_source_url("https://example.com/a?x=1&y=2") != canonical_source_url(
        "https://example.com/a?y=2&x=1"
    )


def test_non_root_trailing_slash_preserves_source_identity_distinction() -> None:
    without_slash = canonical_source_url("https://example.com/care")
    with_slash = canonical_source_url("https://example.com/care/")

    assert without_slash == "https://example.com/care"
    assert with_slash == "https://example.com/care/"
    assert without_slash != with_slash


def test_root_equivalence_is_retained() -> None:
    assert canonical_source_url("https://example.com") == "https://example.com/"
    assert canonical_source_url("https://example.com/") == "https://example.com/"


def test_canonicalization_version_is_explicit() -> None:
    assert URL_CANONICALIZATION_VERSION == 2
