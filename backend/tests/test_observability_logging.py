"""Structured logging never serializes source identity or exception content.

The page-fetch event must retain bounded operational fields (status, error
category, lengths, duration) without any raw URL, domain, URL hash, snippet,
or fetched body. The JSON formatter must never serialize an exception message
or traceback, only the closed exception type name. Provider configuration
failures log the exception type and role, never the exception string.
"""

from __future__ import annotations

import logging
import sys

import pytest

from app.knowledge.acquisition import TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidenceFetcher
from app.observability.logging import JsonFormatter
from app.providers.types import SearchResult

URL_SENTINEL = "https://example.org/secret-care-guide-SECRETURL"
DOMAIN_SENTINEL = "example.org"
SNIPPET_SENTINEL = "SECRET_SNIPPET"
BODY_SENTINEL = "SECRET_FETCHED_BODY"
EXCEPTION_SENTINELS = (
    "https://secret.example/SECRET_URL_PATH",
    "SECRET_PROMPT",
    "SECRET_PAYLOAD",
    "SECRET_EVIDENCE_BODY",
    "Secretus plantus",
)


def _format_record(record: logging.LogRecord) -> str:
    return JsonFormatter().format(record)


@pytest.mark.asyncio
async def test_page_fetch_success_log_omits_source_identity(caplog) -> None:
    result = SearchResult(
        title="t",
        url=URL_SENTINEL,
        snippet=SNIPPET_SENTINEL,
        source_domain=DOMAIN_SENTINEL,
    )
    fetcher = TrustedPageEvidenceFetcher(TrustedSourceValidator(["example.org"]))
    fetcher._fetch_sync = lambda _result: BODY_SENTINEL  # type: ignore[method-assign]
    caplog.set_level(logging.INFO)

    evidence = await fetcher.fetch(result)

    assert evidence.fetch_status == "fetched"
    record = next(
        record
        for record in caplog.records
        if record.name == "app.knowledge.page_evidence"
    )
    formatted = _format_record(record)
    for forbidden in (URL_SENTINEL, DOMAIN_SENTINEL, SNIPPET_SENTINEL, BODY_SENTINEL):
        assert forbidden not in formatted
    assert '"fetch_status": "fetched"' in formatted
    assert '"fetched_content_length": 19' in formatted
    assert '"snippet_length": 14' in formatted
    assert '"elapsed_seconds":' in formatted
    assert '"error_type": null' in formatted


@pytest.mark.asyncio
async def test_page_fetch_error_log_omits_exception_content(caplog) -> None:
    result = SearchResult(
        title="t",
        url="https://example.org/care",
        snippet="snippet",
        source_domain="example.org",
    )

    def failing_fetch(_result: SearchResult) -> str:
        raise ValueError(" | ".join(EXCEPTION_SENTINELS))

    fetcher = TrustedPageEvidenceFetcher(TrustedSourceValidator(["example.org"]))
    fetcher._fetch_sync = failing_fetch  # type: ignore[method-assign]
    caplog.set_level(logging.INFO)

    evidence = await fetcher.fetch(result)

    assert evidence.fetch_status == "failed"
    record = next(
        record
        for record in caplog.records
        if record.name == "app.knowledge.page_evidence"
    )
    formatted = _format_record(record)
    for forbidden in (*EXCEPTION_SENTINELS, "Traceback", "File \"", "line "):
        assert forbidden not in formatted
    assert '"fetch_status": "failed"' in formatted
    assert '"fetch_error_category": "fetch_error"' in formatted
    assert '"error_type": "ValueError"' in formatted
    assert '"elapsed_seconds":' in formatted


def test_json_formatter_never_serializes_exception_message_or_traceback() -> None:
    sentinel = "SECRET https://secret.example SECRET_PAYLOAD Secretus plantus"

    try:
        raise RuntimeError(sentinel)
    except RuntimeError:
        record = logging.LogRecord(
            name="app.jobs.worker",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="worker handler exception",
            args=(),
            exc_info=sys.exc_info(),
        )

    formatted = _format_record(record)
    assert sentinel not in formatted
    assert "Traceback" not in formatted
    assert "formatException" not in formatted
    assert '"message": "worker handler exception"' in formatted
    assert '"error_type": "RuntimeError"' in formatted
    assert '"error": ' not in formatted


def test_json_formatter_serializes_bounded_error_type_field() -> None:
    record = logging.LogRecord(
        name="app.providers.factory",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="provider_configuration_failure",
        args=(),
        exc_info=None,
    )
    record.ctx_role = "model"
    record.ctx_provider = "invalid-provider"
    record.ctx_error_type = "ValueError"

    formatted = _format_record(record)
    assert '"message": "provider_configuration_failure"' in formatted
    assert '"role": "model"' in formatted
    assert '"provider": "invalid-provider"' in formatted
    assert '"error_type": "ValueError"' in formatted
    assert '"error": ' not in formatted


@pytest.mark.parametrize(
    ("builder_name", "role"),
    [
        ("_build_model_chain", "model"),
        ("_build_vision_chain", "vision"),
        ("_build_judge_chain", "judge"),
        ("_build_search_chain", "search"),
    ],
)
def test_provider_configuration_failure_logs_type_not_exception(
    monkeypatch, caplog, builder_name: str, role: str
) -> None:
    import app.providers.factory as factory_module
    from app.core.settings import get_settings

    sentinel_message = " | ".join(EXCEPTION_SENTINELS)

    def _raise_sentinel(_provider, _settings) -> object:
        raise ValueError(sentinel_message)

    single_builder = {
        "_build_model_chain": "_build_single_model_provider",
        "_build_vision_chain": "_build_single_vision_provider",
        "_build_judge_chain": "_build_single_judge_provider",
        "_build_search_chain": "_build_single_search_provider",
    }[builder_name]
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    original_single = getattr(factory_module, single_builder)

    def _raise_sentinel(provider, settings) -> object:
        if provider == "mock":
            return original_single(provider, settings)
        raise ValueError(sentinel_message)

    monkeypatch.setattr(factory_module, single_builder, _raise_sentinel)
    caplog.set_level(logging.WARNING, logger="app.providers.factory")

    builder = getattr(factory_module, builder_name)
    chain = builder(["invalid-provider", "mock"], get_settings())

    assert chain is not None
    failure_records = [
        record
        for record in caplog.records
        if record.getMessage() == "provider_configuration_failure"
    ]
    assert failure_records, (builder_name, caplog.records)
    record = failure_records[0]
    assert record.__dict__["ctx_role"] == role
    assert record.__dict__["ctx_provider"] == "invalid-provider"
    assert record.__dict__["ctx_error_type"] == "ValueError"
    assert "ctx_error" not in record.__dict__

    formatted = _format_record(record)
    for forbidden in EXCEPTION_SENTINELS:
        assert forbidden not in formatted
    assert '"role": "' + role + '"' in formatted
    assert '"provider": "invalid-provider"' in formatted
    assert '"error_type": "ValueError"' in formatted
    assert '"error": ' not in formatted
