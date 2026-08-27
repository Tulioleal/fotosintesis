"""Deterministic enrichment efficacy corpus.

Runs a bounded corpus of empty, sparse, complete, contradictory,
multilingual, safety-sensitive, retry, policy-change, and source-change
cases through the real production enrichment handler against PostgreSQL and
pgvector, then reports and asserts bounded efficacy outcomes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.auth.tables import (
    application_jobs,
    enrichment_telemetry_observations,
    knowledge_chunks,
    knowledge_document_aspect_supports,
    knowledge_documents,
    knowledge_embeddings,
    knowledge_sources,
)
from app.core.settings import Settings, get_settings
from app.assistant.care_contracts import RequiredAspect
from app.enrichment.policy import (
    ENRICHMENT_POLICY_V1,
    EnrichmentPolicy,
)
from app.jobs.handler import HandlerRegistry
from app.jobs.handlers.enrich_confirmed_plant import EnrichConfirmedPlantHandler
from app.jobs.schemas import (
    EnrichConfirmedPlantPayload,
    JobStatus,
    JobType,
)
from app.jobs.worker import Worker
from app.observability.metrics import MetricsRegistry

from ._enrichment_helpers import (
    LIGHT,
    PAGE_URL,
    REQUIRED,
    SAFETY_ASPECT,
    SPECIES_NAME,
    WATERING,
    DeterministicJudgeProvider,
    DeterministicSearchProvider,
    _all_vector_node_ids,
    _confirmed_payload,
    _document_content_keys,
    _effect_snapshot,
    _page,
    _production_service,
    _providers,
    _retrieve_through_production_path,
    _schedule_via_confirmation,
    provider_environment,
    vector_index_factory,
    vector_store,
)

MULTILINGUAL_QUOTES = {
    "watering_frequency_or_trigger": (
        "Riegue solo cuando el sustrato ya esté completamente seco en la superficie."
    ),
    "light_exposure": (
        "Luz brillante e indirecta; la exposición directa prolongada puede quemar las hojas."
    ),
    "humidity_preference": (
        "Une humidité ambiante modérée convient à cette espèce tropicale."
    ),
}
HUMIDITY = "humidity_preference"
POT_DRAINAGE = "pot_drainage"

# Test-only policy v2: every policy-v1 requirement plus one additional
# canonical aspect and a distinct acceptance semantics. It is deliberately
# NOT registered in ENRICHMENT_POLICIES because production telemetry labels
# support only released policy 1.
TEST_POLICY_V2 = EnrichmentPolicy(
    version=2,
    search_groups=(
        *ENRICHMENT_POLICY_V1.search_groups,
        (RequiredAspect.pot_drainage,),
    ),
    max_aspects_per_search_group=4,
    max_searches=6,
    max_durable_attempts=3,
    acceptance_semantics="registry_answerability_v2",
)


def _test_policy_resolver(version: int) -> EnrichmentPolicy:
    if version == 1:
        return ENRICHMENT_POLICY_V1
    if version == 2:
        return TEST_POLICY_V2
    raise ValueError(f"unsupported test policy version: {version}")


@contextlib.contextmanager
def _test_policy_patch():
    """Resolve the test-only policy v2 during handler model validation.

    ``EnrichmentJobResult`` imports ``get_enrichment_policy`` at validation
    time from ``app.enrichment.policy``, so the module attribute is patched
    only for the duration of the v2 handler call and always restored. The
    production policy registry is never altered.
    """
    import app.enrichment.policy as policy_module

    original = policy_module.get_enrichment_policy
    policy_module.get_enrichment_policy = _test_policy_resolver
    try:
        yield
    finally:
        policy_module.get_enrichment_policy = original


@dataclass
class CorpusCase:
    name: str
    judge: DeterministicJudgeProvider
    search: DeterministicSearchProvider
    outcome: str
    covered: set[str]
    document_deltas: tuple[int, ...]
    acquisition_avoided: bool = False
    validation_run_deltas: tuple[int, ...] = field(default_factory=tuple)
    results: list[tuple[str, set[str]]] = field(default_factory=list)
    policy_versions: list[int] = field(default_factory=list)


@dataclass
class CorpusReport:
    cases: list[CorpusCase] = field(default_factory=list)
    total_runs: int = 0
    acquisition_avoided_count: int = 0
    unsupported_persistence_count: int = 0
    duplicate_effect_count: int = 0
    effect_mismatch_count: int = 0
    search_count_max: int = 0
    lifecycle_distribution: dict[str, int] = field(default_factory=dict)
    retrieval_failures: list[str] = field(default_factory=list)
    accepted_aspect_total: int = 0
    coverage_gain_total: int = 0


async def _run_corpus(
    pg_session_factory,
    vector_index_factory,
    metrics: MetricsRegistry,
    vector_store,
) -> CorpusReport:
    cases: list[CorpusCase] = [
        CorpusCase(
            name="empty",
            judge=DeterministicJudgeProvider(pages={}),
            search=DeterministicSearchProvider(),
            outcome="failed",
            covered=set(),
            document_deltas=(0,),
        ),
        CorpusCase(
            name="sparse",
            judge=DeterministicJudgeProvider(pages={PAGE_URL: (WATERING, LIGHT)}),
            search=DeterministicSearchProvider(page=_page(source_version="s1")),
            outcome="partial",
            covered={WATERING, LIGHT},
            document_deltas=(1,),
        ),
        CorpusCase(
            name="complete",
            judge=DeterministicJudgeProvider(pages={PAGE_URL: tuple(REQUIRED)}),
            search=DeterministicSearchProvider(page=_page(source_version="s2")),
            outcome="complete",
            covered=set(REQUIRED),
            document_deltas=(1,),
        ),
        CorpusCase(
            name="contradictory",
            judge=DeterministicJudgeProvider(
                pages={PAGE_URL: (WATERING,)},
                contradiction={
                    "claim_a": "Water weekly.",
                    "claim_b": "Water monthly.",
                    "source_a_urls": [PAGE_URL],
                    "source_b_urls": [PAGE_URL],
                },
            ),
            search=DeterministicSearchProvider(page=_page(source_version="s3")),
            outcome="failed",
            covered=set(),
            document_deltas=(0,),
        ),
        CorpusCase(
            name="multilingual",
            judge=DeterministicJudgeProvider(
                pages={PAGE_URL: (WATERING, LIGHT, HUMIDITY)},
                quote_fn=lambda aspect: MULTILINGUAL_QUOTES[aspect],
            ),
            search=DeterministicSearchProvider(page=_page(source_version="s4")),
            outcome="partial",
            covered={WATERING, LIGHT, HUMIDITY},
            document_deltas=(1,),
        ),
        CorpusCase(
            name="safety-sensitive",
            judge=DeterministicJudgeProvider(
                pages={PAGE_URL: (WATERING, SAFETY_ASPECT)},
                safety_confidence=0.80,
            ),
            search=DeterministicSearchProvider(page=_page(source_version="s5")),
            outcome="partial",
            covered={WATERING},
            document_deltas=(1,),
        ),
        CorpusCase(
            name="retry",
            judge=DeterministicJudgeProvider(
                pages={PAGE_URL: (WATERING,)},
                fail_attempts=1,
            ),
            search=DeterministicSearchProvider(page=_page(source_version="s6")),
            outcome="partial",
            covered={WATERING},
            document_deltas=(0, 1),
            # The first attempt fails at the provider boundary before the
            # enrichment service executes, so it records no validation run.
            validation_run_deltas=(0, 1),
        ),
        CorpusCase(
            name="policy-change",
            judge=DeterministicJudgeProvider(pages={PAGE_URL: (WATERING, LIGHT)}),
            search=DeterministicSearchProvider(page=_page(source_version="s7")),
            outcome="partial",
            covered={WATERING, LIGHT},
            document_deltas=(1, 0),
        ),
        CorpusCase(
            name="source-change",
            judge=DeterministicJudgeProvider(
                pages={PAGE_URL: (WATERING, LIGHT)},
            ),
            search=DeterministicSearchProvider(page=_page(source_version="s8")),
            outcome="partial",
            covered={WATERING, LIGHT},
            document_deltas=(1, 1, 1),
        ),        CorpusCase(
            name="local-complete",
            judge=DeterministicJudgeProvider(
                pages={PAGE_URL: tuple(REQUIRED)},
                local_pages={PAGE_URL: tuple(REQUIRED)},
            ),
            search=DeterministicSearchProvider(page=_page(source_version="s9")),
            outcome="complete",
            covered=set(REQUIRED),
            document_deltas=(0,),
            acquisition_avoided=True,
        ),
        CorpusCase(
            name="safety-only-rejected",
            judge=DeterministicJudgeProvider(
                pages={PAGE_URL: (SAFETY_ASPECT,)},
                safety_confidence=0.80,
            ),
            search=DeterministicSearchProvider(page=_page(source_version="s10")),
            outcome="failed",
            covered=set(),
            document_deltas=(0,),
        ),
    ]

    report = CorpusReport(cases=cases)
    for case in cases:
        for run_index in range(len(case.document_deltas)):
            if case.name == "policy-change" and run_index == 1:
                # Genuine v1 -> v2 policy change: the local evidence reuses
                # the run-1 content, acquisition supplies only the newly
                # required aspect, and the persisted claim/quote content is
                # unchanged so the existing document identity is reused.
                case.judge.pages = {PAGE_URL: (POT_DRAINAGE,)}
                case.judge.local_pages = {PAGE_URL: (WATERING, LIGHT)}
                case.judge.quote_fn = (
                    lambda aspect: (
                        "Paraphrased watering_frequency_or_trigger guidance that "
                        "is not an exact substring of the supplied evidence text."
                    )
                )
                case.covered = {WATERING, LIGHT, POT_DRAINAGE}
            if case.name == "source-change" and run_index == 1:
                # Genuine source-version change: the same trusted page under a
                # different source version with unchanged claim/quote content,
                # so the content hash stays equal while the stable document
                # identity differs.
                case.search.page = _page(source_version="s8-v2")
            if case.name == "source-change" and run_index == 2:
                # Genuine content-hash change: same source version with a
                # visibly different, non-empty, accepted quote, so the content
                # hash differs while the source version stays the same.
                case.judge.quote_fn = (
                    lambda aspect: (
                        f"Visible content-hash change guidance for {aspect} that "
                        "remains semantically accepted."
                    )
                )
            if case.name == "retry" and run_index == 1:
                case.judge.fail_attempts = 0
            before = await _effect_snapshot(pg_session_factory, vector_store)
            search_calls_before = case.search.calls
            providers = _providers(judge=case.judge, search=case.search)
            if case.name == "policy-change" and run_index == 1:
                policy_version = 2
                service_kwargs = {"policy_resolver": _test_policy_resolver}
            else:
                policy_version = 1
                service_kwargs = {}
            case.policy_versions.append(policy_version)
            payload = await _confirmed_payload(
                pg_session_factory, policy_version=policy_version
            )
            handler_kwargs: dict[str, object] = {}
            if policy_version == 2:
                handler_kwargs["policy_resolver"] = _test_policy_resolver
            handler = EnrichConfirmedPlantHandler(
                _production_service(
                    pg_session_factory, providers, **service_kwargs
                ),
                **handler_kwargs,
            )
            if policy_version == 2:
                with _test_policy_patch():
                    result = await handler.handle(
                        payload=payload,
                        attempt_count=run_index + 1,
                        max_attempts=3,
                    )
            else:
                result = await handler.handle(
                    payload=payload,
                    attempt_count=run_index + 1,
                    max_attempts=3,
                )
            status = result.status.value
            covered = (
                set(result.result.covered_aspects)
                if result.result
                else set()
            )
            snapshot = result.efficacy
            acquisition_avoided = bool(
                result.result
                and result.result.acquisition_avoided
            )
            after = await _effect_snapshot(pg_session_factory, vector_store)
            case.results.append((status, covered))
            report.total_runs += 1
            report.lifecycle_distribution[status] = (
                report.lifecycle_distribution.get(status, 0) + 1
            )
            report.acquisition_avoided_count += int(
                bool(case.acquisition_avoided)
                and acquisition_avoided
            )
            if snapshot is not None:
                report.accepted_aspect_total += snapshot.accepted_aspect_count
                report.coverage_gain_total += snapshot.coverage_gain
            report.search_count_max = max(
                report.search_count_max, case.search.calls - search_calls_before
            )

            expected_delta = case.document_deltas[run_index]
            effect_delta = after.delta(before)
            before_counts = before.counts()
            after_counts = after.counts()
            for effect in (
                "documents",
                "sources",
                "chunks",
                "embeddings",
                "vector_node_ids",
            ):
                actual_delta = after_counts[effect] - before_counts[effect]
                if actual_delta != expected_delta:
                    if actual_delta > expected_delta:
                        report.duplicate_effect_count += (
                            actual_delta - expected_delta
                        )
                    else:
                        report.effect_mismatch_count += (
                            expected_delta - actual_delta
                        )
            # No run may remove or mutate existing effects: every stable
            # identity set is monotonic across the run.
            for attr in (
                "documents",
                "sources",
                "chunks",
                "embeddings",
                "supports",
                "validation_evidence",
                "vector_node_ids",
            ):
                assert getattr(before, attr) <= getattr(after, attr), (
                    case.name,
                    run_index,
                    attr,
                )
            # Relational support, relationally refreshed chunk metadata, and
            # vector metadata must fully agree after every run.
            after.assert_relational_vector_convergence()

            # Every newly persisted support aspect must have been accepted by
            # this run, even if the aspect is globally canonical.
            new_support_aspects = {
                aspect for _document_id, aspect in effect_delta.supports
            }
            report.unsupported_persistence_count += len(
                new_support_aspects - covered
            )

            # A one-source run either associates exactly one validation with
            # accepted evidence or none when nothing was accepted; acquisition
            # avoidance persists no new validation-evidence association.
            expected_validation_delta = (
                0 if acquisition_avoided else (1 if covered else 0)
            )
            actual_validation_delta = len(effect_delta.validation_evidence)
            if actual_validation_delta != expected_validation_delta:
                report.effect_mismatch_count += abs(
                    actual_validation_delta - expected_validation_delta
                )

            # Every service execution records exactly one validation run;
            # provider-pre-empted runs (retry attempt one) record none. Only
            # accepted (or acquisition-avoided) executions also associate
            # evidence documents.
            expected_validation_runs = (
                case.validation_run_deltas[run_index]
                if case.validation_run_deltas
                else 1
            )
            new_validation_runs = (
                after.validation_run_ids - before.validation_run_ids
            )
            if len(new_validation_runs) != expected_validation_runs:
                report.effect_mismatch_count += abs(
                    len(new_validation_runs) - expected_validation_runs
                )

            if covered:
                for aspect in covered:
                    status_value, chunks = await _retrieve_through_production_path(
                        pg_session_factory,
                        vector_index_factory,
                        providers,
                        aspect=aspect,
                    )
                    if status_value != "retrieved" or not any(
                        aspect in (chunk.metadata.get("covered_aspects") or [])
                        for chunk in chunks
                    ):
                        report.retrieval_failures.append(f"{case.name}:{aspect}")

    return report


async def test_deterministic_efficacy_corpus_reports_bounded_outcomes(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    metrics = MetricsRegistry()
    report = await _run_corpus(
        pg_session_factory, vector_index_factory, metrics, vector_store
    )

    assert report.total_runs == 15
    assert report.lifecycle_distribution == {
        "complete": 2,
        "partial": 9,
        "failed": 4,
    }
    assert report.acquisition_avoided_count == 1
    assert report.unsupported_persistence_count == 0
    assert report.duplicate_effect_count == 0
    assert report.effect_mismatch_count == 0
    assert report.search_count_max <= 6
    assert report.retrieval_failures == []
    assert report.accepted_aspect_total == 33
    assert report.coverage_gain_total == 31

    policy_change = next(case for case in report.cases if case.name == "policy-change")
    assert policy_change.policy_versions == [1, 2]
    assert policy_change.results[0][1] == {WATERING, LIGHT}
    assert POT_DRAINAGE in policy_change.results[1][1]
    assert {
        aspect.value for aspect in TEST_POLICY_V2.required_aspects
    } != set(REQUIRED)
    assert (
        TEST_POLICY_V2.semantics_fingerprint
        != ENRICHMENT_POLICY_V1.semantics_fingerprint
    )

    content_keys = await _document_content_keys(pg_session_factory)
    assert len(content_keys) == sum(
        sum(case.document_deltas) for case in report.cases
    )
    assert len(content_keys) == 9

    source_change = next(case for case in report.cases if case.name == "source-change")
    async with pg_session_factory() as session:
        source_change_docs = (
            await session.execute(
                select(
                    knowledge_documents.c.id,
                    knowledge_documents.c.source_version,
                    knowledge_documents.c.normalized_content_hash,
                ).where(
                    knowledge_documents.c.source_version.in_(["s8", "s8-v2"])
                )
            )
        ).mappings().all()
        source_change_chunks = (
            await session.execute(
                select(knowledge_chunks.c.id, knowledge_chunks.c.document_id)
                .join(
                    knowledge_documents,
                    knowledge_documents.c.id == knowledge_chunks.c.document_id,
                )
                .where(knowledge_documents.c.source_version.in_(["s8", "s8-v2"]))
            )
        ).mappings().all()
    assert source_change.policy_versions == [1, 1, 1]
    assert {row["source_version"] for row in source_change_docs} == {
        "s8",
        "s8-v2",
    }
    assert len(source_change_docs) == 3
    run_1_doc = next(row for row in source_change_docs if row["source_version"] == "s8")
    s8_v2_docs = [row for row in source_change_docs if row["source_version"] == "s8-v2"]
    assert len(s8_v2_docs) == 2
    # Run 2 shares the run-1 content hash under a different source version;
    # run 3 changes the content hash under the same source version.
    run_2_doc, run_3_doc = sorted(s8_v2_docs, key=lambda row: row["id"])
    if run_2_doc["normalized_content_hash"] != run_1_doc["normalized_content_hash"]:
        run_2_doc, run_3_doc = run_3_doc, run_2_doc
    assert run_2_doc["normalized_content_hash"] == run_1_doc["normalized_content_hash"]
    assert run_1_doc["id"] != run_2_doc["id"]
    assert run_2_doc["source_version"] == run_3_doc["source_version"] == "s8-v2"
    assert run_3_doc["normalized_content_hash"] != run_2_doc["normalized_content_hash"]
    assert run_3_doc["id"] != run_2_doc["id"]
    chunk_by_document = {row["document_id"]: row["id"] for row in source_change_chunks}
    assert len(chunk_by_document) == 3
    source_change_chunk_ids = {
        chunk_by_document[doc["id"]] for doc in (run_1_doc, run_2_doc, run_3_doc)
    }
    assert len(source_change_chunk_ids) == 3
    vector_ids = await _all_vector_node_ids(vector_store)
    assert all(str(chunk_id) in vector_ids for chunk_id in source_change_chunk_ids)

    async with pg_session_factory() as session:
        chunk_ids = list(
            (await session.execute(select(knowledge_chunks.c.id))).scalars().all()
        )
        support_rows = int(
            await session.scalar(
                select(func.count()).select_from(knowledge_document_aspect_supports)
            )
            or 0
        )
        policy_change_chunk_id = (
            await session.scalar(
                select(knowledge_chunks.c.id)
                .join(
                    knowledge_documents,
                    knowledge_documents.c.id == knowledge_chunks.c.document_id,
                )
                .where(
                    knowledge_documents.c.source_version == "s7"
                )
            )
        )
        policy_change_supports = set(
            (
                await session.execute(
                    select(knowledge_document_aspect_supports.c.aspect)
                    .join(
                        knowledge_documents,
                        knowledge_documents.c.id
                        == knowledge_document_aspect_supports.c.document_id,
                    )
                    .where(knowledge_documents.c.source_version == "s7")
                )
            ).scalars()
        )
    assert support_rows == 33
    assert policy_change_chunk_id is not None
    assert policy_change_supports == {WATERING, LIGHT, POT_DRAINAGE}
    relational_ids = {str(chunk_id) for chunk_id in chunk_ids}
    vector_ids = await _all_vector_node_ids(vector_store)
    assert len(relational_ids) == 9
    assert vector_ids == relational_ids
    policy_change_node = await vector_store.aget_nodes(
        node_ids=[str(policy_change_chunk_id)]
    )
    assert POT_DRAINAGE in policy_change_node[0].metadata["covered_aspects"]

    status_value, chunks = await _retrieve_through_production_path(
        pg_session_factory,
        vector_index_factory,
        _providers(
            judge=DeterministicJudgeProvider(
                pages={PAGE_URL: (POT_DRAINAGE,)}
            ),
            search=DeterministicSearchProvider(page=_page()),
        ),
        aspect=POT_DRAINAGE,
    )
    assert status_value == "retrieved"
    assert chunks[0].id == policy_change_chunk_id


async def test_efficacy_metrics_are_bounded_and_privacy_safe_in_labels_and_logs(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
    caplog,
) -> None:
    import json
    import re

    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    get_settings.cache_clear()
    settings = get_settings()

    job_id, payload = await _schedule_via_confirmation(pg_session_factory)
    async with pg_session_factory() as session:
        job_row = (
            await session.execute(
                select(
                    application_jobs.c.idempotency_key,
                    application_jobs.c.payload,
                ).where(application_jobs.c.id == job_id)
            )
        ).mappings().one()
        idempotency_key = job_row["idempotency_key"]
        serialized_payload = json.dumps(job_row["payload"], sort_keys=True)

    metrics = MetricsRegistry()
    registry = _enrichment_registry(
        pg_session_factory,
        _providers(
            judge=DeterministicJudgeProvider(pages={PAGE_URL: tuple(REQUIRED)}),
            search=DeterministicSearchProvider(page=_page()),
        ),
        settings,
    )
    caplog.set_level(logging.INFO)
    await _run_worker_to_status(
        pg_session_factory,
        registry,
        settings,
        metrics,
        job_id,
        JobStatus.complete,
    )

    rendered = metrics.to_prometheus()
    assert "fotosintesis_enrichment_efficacy_total" in rendered
    assert "fotosintesis_enrichment_efficacy_local_covered_count" in rendered
    assert "fotosintesis_enrichment_efficacy_final_covered_count" in rendered
    assert "fotosintesis_enrichment_efficacy_coverage_gain" in rendered
    assert "fotosintesis_enrichment_efficacy_accepted_aspect_count" in rendered
    assert "fotosintesis_enrichment_efficacy_search_count" in rendered
    assert "fotosintesis_enrichment_efficacy_completion_duration_seconds" in rendered

    assert metrics.enrichment_efficacy_counts == {("1", "complete", False): 1}
    final_covered = metrics.enrichment_efficacy_histograms[
        ("final_covered_count", "1", "complete")
    ]
    assert final_covered.total_count == 1
    assert final_covered.total_sum == float(len(REQUIRED))
    gain = metrics.enrichment_efficacy_histograms[("coverage_gain", "1", "complete")]
    assert gain.total_count == 1
    assert gain.total_sum == float(len(REQUIRED))

    label_keys = {
        match.group(1)
        for match in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)="', rendered)
    }
    assert {"policy_version", "lifecycle_outcome", "acquisition_avoided", "le"} <= label_keys
    efficacy_lines = [
        line
        for line in rendered.splitlines()
        if line.startswith("fotosintesis_enrichment_efficacy_")
        and "{" in line
    ]
    assert efficacy_lines
    closed_values = {
        "1", "true", "false", "complete", "partial", "failed",
        "0.0", "1.0", "2.0", "3.0", "4.0", "6.0", "8.0", "10.0", "12.0", "17.0",
        "0.1", "0.5", "2.5", "5.0", "30.0", "60.0", "300.0",
        "+Inf",
    }
    for line in efficacy_lines:
        for value in re.findall(r'"([^"]*)"', line):
            assert value in closed_values, (value, line)

    logs = " ".join(record.getMessage() for record in caplog.records)
    log_metadata = " ".join(str(record.__dict__) for record in caplog.records)
    sensitive_values = [
        SPECIES_NAME,
        "2878688",
        PAGE_URL,
        "example.org",
        "A trusted botanical source documents",
        "Paraphrased",
        "trusted botanical page content",
        "passing_score",
        idempotency_key,
        serialized_payload,
        str(payload.taxonomy_provenance_id),
    ]
    combined = f"{rendered}\n{logs}\n{log_metadata}"
    for sensitive in sensitive_values:
        assert sensitive not in combined
    # The run id equals the durable job id. It is the worker's first-class
    # bounded ctx_job_id correlation field and may appear there and nowhere
    # else: never in metric labels, never in message text, and never in any
    # other ctx_* field.
    assert str(payload.run_id) not in rendered
    assert str(payload.run_id) not in logs
    run_id_records = [
        record
        for record in caplog.records
        if getattr(record, "ctx_job_id", None) == str(payload.run_id)
    ]
    assert run_id_records, "the run id must appear only as bounded ctx_job_id"
    for record in caplog.records:
        for key, value in record.__dict__.items():
            if key.startswith("ctx_") and key != "ctx_job_id":
                assert str(payload.run_id) not in str(value), (record.name, key)
    assert "watering_frequency_or_trigger" not in rendered


def test_enrichment_efficacy_metric_contract_rejects_unbounded_labels() -> None:
    from app.observability.metrics import MetricsRegistry

    registry = MetricsRegistry()
    with pytest.raises(ValueError):
        registry.record_enrichment_efficacy(
            policy_label="2",
            lifecycle_outcome="complete",
            acquisition_avoided=False,
            local_covered_count=1,
            final_covered_count=1,
            coverage_gain=1,
            accepted_aspect_count=1,
            search_count=1,
            duration_seconds=1.0,
        )
    with pytest.raises(ValueError):
        registry.record_enrichment_efficacy(
            policy_label="999",
            lifecycle_outcome="complete",
            acquisition_avoided=False,
            local_covered_count=1,
            final_covered_count=1,
            coverage_gain=1,
            accepted_aspect_count=1,
            search_count=1,
            duration_seconds=1.0,
        )
    with pytest.raises(ValueError):
        registry.record_enrichment_efficacy(
            policy_label="https://example.org/policy/2",
            lifecycle_outcome="complete",
            acquisition_avoided=False,
            local_covered_count=1,
            final_covered_count=1,
            coverage_gain=1,
            accepted_aspect_count=1,
            search_count=1,
            duration_seconds=1.0,
        )
    with pytest.raises(ValueError):
        registry.record_enrichment_efficacy(
            policy_label="free text label",
            lifecycle_outcome="complete",
            acquisition_avoided=False,
            local_covered_count=1,
            final_covered_count=1,
            coverage_gain=1,
            accepted_aspect_count=1,
            search_count=1,
            duration_seconds=1.0,
        )
    with pytest.raises(ValueError):
        registry.record_enrichment_efficacy(
            policy_label="1",
            lifecycle_outcome="arbitrary_outcome",
            acquisition_avoided=False,
            local_covered_count=1,
            final_covered_count=1,
            coverage_gain=1,
            accepted_aspect_count=1,
            search_count=1,
            duration_seconds=1.0,
        )
    with pytest.raises(ValueError):
        registry.record_enrichment_efficacy(
            policy_label="1",
            lifecycle_outcome="lease_lost",
            acquisition_avoided=False,
            local_covered_count=1,
            final_covered_count=1,
            coverage_gain=1,
            accepted_aspect_count=1,
            search_count=1,
            duration_seconds=1.0,
        )


async def test_efficacy_corpus_accepts_no_unsupported_persistence_or_duplicates(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    metrics = MetricsRegistry()
    report = await _run_corpus(
        pg_session_factory, vector_index_factory, metrics, vector_store
    )

    assert report.unsupported_persistence_count == 0
    assert report.duplicate_effect_count == 0
    assert report.effect_mismatch_count == 0

    async with pg_session_factory() as session:
        doc_count = int(
            await session.scalar(
                select(func.count()).select_from(knowledge_documents)
            )
            or 0
        )
        chunk_count = int(
            await session.scalar(select(func.count()).select_from(knowledge_chunks))
            or 0
        )
        embedding_count = int(
            await session.scalar(
                select(func.count()).select_from(knowledge_embeddings)
            )
            or 0
        )
        source_count = int(
            await session.scalar(select(func.count()).select_from(knowledge_sources))
            or 0
        )
        support_count = int(
            await session.scalar(
                select(func.count()).select_from(knowledge_document_aspect_supports)
            )
            or 0
        )
        chunk_ids = list(
            (await session.execute(select(knowledge_chunks.c.id))).scalars().all()
        )
    expected_documents = sum(
        sum(case.document_deltas) for case in report.cases
    )
    assert doc_count == expected_documents == 9
    assert chunk_count == doc_count
    assert embedding_count == doc_count
    assert source_count == doc_count
    assert support_count == 33
    relational_ids = {str(chunk_id) for chunk_id in chunk_ids}
    vector_ids = await _all_vector_node_ids(vector_store)
    assert len(relational_ids) == 9
    assert vector_ids == relational_ids


async def _run_worker_to_status(
    pg_session_factory,
    registry,
    settings,
    metrics,
    job_id,
    status: JobStatus,
) -> None:
    worker = Worker(
        session_factory=pg_session_factory,
        handler_registry=registry,
        settings=settings,
        metrics=metrics,
    )
    task = asyncio.create_task(worker.start())
    try:
        async with asyncio.timeout(30):
            job_type = None
            while True:
                async with pg_session_factory() as session:
                    current, job_type = (
                        await session.execute(
                            select(
                                application_jobs.c.status,
                                application_jobs.c.job_type,
                            ).where(
                                application_jobs.c.id == job_id
                            )
                        )
                    ).one()
                if current == status.value:
                    break
                await asyncio.sleep(0.05)

            # The terminal status and durable observation commit together, but
            # the in-memory metrics refresh runs immediately afterward. Wait
            # for that refresh before stopping the worker to avoid racing its
            # post-commit work.
            if job_type == JobType.enrich_confirmed_plant.value:
                while not metrics.enrichment_efficacy_counts:
                    await asyncio.sleep(0.05)
    finally:
        worker.stop()
        await task


def _enrichment_registry(
    pg_session_factory,
    providers,
    settings,
) -> HandlerRegistry:
    registry = HandlerRegistry()
    registry.register(
        JobType.enrich_confirmed_plant.value,
        EnrichConfirmedPlantHandler(
            _production_service(pg_session_factory, providers, settings=settings)
        ),
        payload_models={1: EnrichConfirmedPlantPayload},
    )
    return registry


async def test_worker_emits_efficacy_only_after_durable_terminal_commits(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    get_settings.cache_clear()
    settings = get_settings()

    job_id, payload = await _schedule_via_confirmation(pg_session_factory)
    metrics = MetricsRegistry()
    await _run_worker_to_status(
        pg_session_factory,
        _enrichment_registry(
            pg_session_factory,
            _providers(
                judge=DeterministicJudgeProvider(pages={PAGE_URL: tuple(REQUIRED)}),
                search=DeterministicSearchProvider(page=_page()),
            ),
            settings,
        ),
        settings,
        metrics,
        job_id,
        JobStatus.complete,
    )
    assert metrics.enrichment_efficacy_counts == {("1", "complete", False): 1}

    job_id, _payload = await _schedule_via_confirmation(pg_session_factory)
    metrics = MetricsRegistry()
    await _run_worker_to_status(
        pg_session_factory,
        _enrichment_registry(
            pg_session_factory,
            _providers(
                judge=DeterministicJudgeProvider(pages={PAGE_URL: (WATERING,)}),
                search=DeterministicSearchProvider(page=_page()),
            ),
            settings,
        ),
        settings,
        metrics,
        job_id,
        JobStatus.partial,
    )
    # Durable observations accumulate: the registry is a database-derived
    # snapshot including the earlier complete observation.
    assert metrics.enrichment_efficacy_counts == {
        ("1", "complete", False): 1,
        ("1", "partial", False): 1,
    }

    job_id, payload = await _schedule_via_confirmation(pg_session_factory)
    metrics = MetricsRegistry()
    await _run_worker_to_status(
        pg_session_factory,
        _enrichment_registry(
            pg_session_factory,
            _providers(
                judge=DeterministicJudgeProvider(pages={}),
                search=DeterministicSearchProvider(),
            ),
            settings,
        ),
        settings,
        metrics,
        job_id,
        JobStatus.failed,
    )
    assert metrics.enrichment_efficacy_counts == {
        ("1", "complete", False): 1,
        ("1", "partial", False): 1,
        ("1", "failed", False): 1,
    }


async def _observation_rows(pg_session_factory) -> list[dict]:
    async with pg_session_factory() as session:
        rows = (
            await session.execute(select(enrichment_telemetry_observations))
        ).mappings().all()
        return [dict(row) for row in rows]


async def test_non_enrichment_jobs_produce_no_efficacy_rows_or_metrics(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    get_settings.cache_clear()
    settings = get_settings()

    from app.jobs.handler import HandlerRegistry, JobHandler, JobHandlerResult
    from app.jobs.repository import JobRepository
    from app.jobs.schemas import (
        IngestValidatedClaimsPayload,
        JobFailureCategory,
        JobLimitation,
        JobStatus,
        JobType,
        ReadJobResult,
    )
    from app.jobs.worker import Worker

    class _OutcomeHandler(JobHandler):
        async def handle(self, *, payload, attempt_count, max_attempts):
            topic = payload.claims[0].topic
            if topic == "complete":
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )
            if topic == "partial":
                return JobHandlerResult(
                    status=JobStatus.partial,
                    result=ReadJobResult(
                        succeeded=1,
                        failed=1,
                        partial=True,
                        limitations=[JobLimitation.some_claims_failed],
                    ),
                )
            return JobHandlerResult.failed(
                category=JobFailureCategory.invariant_violation,
                retryable=False,
            )

    registry = HandlerRegistry()
    registry.register(
        JobType.ingest_validated_claims.value,
        _OutcomeHandler(),
        payload_models={1: IngestValidatedClaimsPayload},
    )
    job_ids = {}
    async with pg_session_factory() as session:
        repository = JobRepository(session)
        for topic in ("complete", "partial", "failed"):
            job_ids[topic] = await repository.enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload={
                    "claims": [
                        {
                            "scientific_name": "Secretus plantus",
                            "topic": topic,
                            "source_url": "https://secret.example/private",
                            "source_domain": "secret.example",
                            "source_provenance": "trusted",
                            "claim": "CLAIM",
                            "evidence_quote": "QUOTE",
                            "confidence": 0.9,
                            "covered_aspects": ["watering_frequency_or_trigger"],
                            "answerability_status": "full",
                        }
                    ],
                    "conversation_id": "22222222-2222-2222-2222-222222222222",
                    "answerability_status": "full",
                },
                idempotency_key=f"non-enrichment-{topic}",
            )
        await session.commit()

    metrics = MetricsRegistry()
    worker = Worker(
        session_factory=pg_session_factory,
        handler_registry=registry,
        settings=settings,
        metrics=metrics,
    )
    task = asyncio.create_task(worker.start())
    try:
        async with asyncio.timeout(30):
            while True:
                async with pg_session_factory() as session:
                    statuses = set(
                        (
                            await session.execute(
                                select(application_jobs.c.status).where(
                                    application_jobs.c.id.in_(job_ids.values())
                                )
                            )
                        ).scalars()
                    )
                if {"complete", "partial", "failed"} <= statuses:
                    break
                await asyncio.sleep(0.05)
    finally:
        worker.stop()
        await task

    assert await _observation_rows(pg_session_factory) == []
    assert metrics.enrichment_efficacy_counts == {}


async def test_duplicate_observation_insert_is_idempotent_and_differing_raises(
    pg_session_factory,
) -> None:
    from sqlalchemy import text as sa_text

    from app.jobs.repository import (
        JobRepository,
        RepositoryInvariantError,
    )

    job_id, payload = await _schedule_via_confirmation(pg_session_factory)
    # The insert trigger requires a terminal job whose status matches the
    # lifecycle outcome, mirroring the worker's atomic terminal transition.
    async with pg_session_factory() as session:
        await session.execute(
            sa_text(
                """
                UPDATE application_jobs
                SET status = 'failed', completed_at = NOW()
                WHERE id = :id
                """
            ),
            {"id": job_id},
        )
        await session.commit()
    values = {
        "job_id": job_id,
        "policy_label": "1",
        "lifecycle_outcome": "failed",
        "acquisition_avoided": False,
        "local_covered_count": 0,
        "final_covered_count": 0,
        "coverage_gain": 0,
        "accepted_aspect_count": 0,
        "search_count": 0,
        "duration_seconds": 0.0,
    }
    async with pg_session_factory() as session:
        repository = JobRepository(session)
        await repository.record_terminal_enrichment_observation(**values)
        await session.commit()
        await repository.record_terminal_enrichment_observation(**values)
        await session.commit()
    assert len(await _observation_rows(pg_session_factory)) == 1

    differing = dict(values, coverage_gain=5)
    async with pg_session_factory() as session:
        repository = JobRepository(session)
        with pytest.raises(RepositoryInvariantError):
            await repository.record_terminal_enrichment_observation(**differing)
        await session.rollback()
    assert len(await _observation_rows(pg_session_factory)) == 1

    for invalid_label in ("2", "999", "https://example.org/policy/2", "free text", 1):
        async with pg_session_factory() as session:
            repository = JobRepository(session)
            with pytest.raises(ValueError):
                await repository.record_terminal_enrichment_observation(
                    **dict(values, job_id=uuid4(), policy_label=invalid_label)
                )
            await session.rollback()
    for invalid_outcome in ("lease_lost", "retry_scheduled", "arbitrary"):
        async with pg_session_factory() as session:
            repository = JobRepository(session)
            with pytest.raises(ValueError):
                await repository.record_terminal_enrichment_observation(
                    **dict(values, job_id=uuid4(), lifecycle_outcome=invalid_outcome)
                )
            await session.rollback()


def test_unsupported_policy_uses_closed_label() -> None:
    from app.enrichment.policy import enrichment_policy_label

    assert enrichment_policy_label(1) == "1"
    for value in (2, 999, True, False, "1", "2", None, -1, "unsupported"):
        assert enrichment_policy_label(value) == "unsupported", value


async def test_worker_restart_reconstructs_metrics_without_incrementing(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    get_settings.cache_clear()
    settings = get_settings()

    job_id, payload = await _schedule_via_confirmation(pg_session_factory)
    providers = _providers(
        judge=DeterministicJudgeProvider(pages={PAGE_URL: (WATERING,)}),
        search=DeterministicSearchProvider(page=_page()),
    )
    metrics = MetricsRegistry()
    await _run_worker_to_status(
        pg_session_factory,
        _enrichment_registry(pg_session_factory, providers, settings),
        settings,
        metrics,
        job_id,
        JobStatus.partial,
    )
    assert metrics.enrichment_efficacy_counts == {("1", "partial", False): 1}
    assert len(await _observation_rows(pg_session_factory)) == 1

    # Restart: a fresh worker and registry must reconstruct the same totals
    # from PostgreSQL without incrementing them.
    restarted_metrics = MetricsRegistry()
    await _run_worker_to_status(
        pg_session_factory,
        _enrichment_registry(pg_session_factory, providers, settings),
        settings,
        restarted_metrics,
        job_id,
        JobStatus.partial,
    )
    assert restarted_metrics.enrichment_efficacy_counts == {
        ("1", "partial", False): 1
    }
    assert len(await _observation_rows(pg_session_factory)) == 1

    # A second restart renders identical totals again.
    second_restart_metrics = MetricsRegistry()
    await _run_worker_to_status(
        pg_session_factory,
        _enrichment_registry(pg_session_factory, providers, settings),
        settings,
        second_restart_metrics,
        job_id,
        JobStatus.partial,
    )
    assert second_restart_metrics.enrichment_efficacy_counts == {
        ("1", "partial", False): 1
    }
    assert len(await _observation_rows(pg_session_factory)) == 1


async def test_worker_retry_schedules_zero_efficacy_then_one_complete(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    get_settings.cache_clear()
    settings = get_settings()

    job_id, payload = await _schedule_via_confirmation(pg_session_factory)
    metrics = MetricsRegistry()
    await _run_worker_to_status(
        pg_session_factory,
        _enrichment_registry(
            pg_session_factory,
            _providers(
                judge=DeterministicJudgeProvider(
                    pages={PAGE_URL: tuple(REQUIRED)},
                    fail_attempts=1,
                ),
                search=DeterministicSearchProvider(page=_page()),
            ),
            settings,
        ),
        settings,
        metrics,
        job_id,
        JobStatus.complete,
    )
    assert metrics.enrichment_efficacy_counts == {("1", "complete", False): 1}
    assert (JobType.enrich_confirmed_plant.value, "retry_scheduled") in (
        metrics.job_outcomes
    )
    observations = await _observation_rows(pg_session_factory)
    assert len(observations) == 1
    assert observations[0]["lifecycle_outcome"] == "complete"


async def test_reconciliation_exhaustion_emits_one_failed_efficacy(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
) -> None:
    from sqlalchemy import text as sa_text

    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    get_settings.cache_clear()
    settings = get_settings()

    payload = await _confirmed_payload(pg_session_factory)
    async with pg_session_factory() as session:
        from app.jobs.repository import JobRepository

        job_id = await JobRepository(session, settings).enqueue(
            job_type=JobType.enrich_confirmed_plant.value,
            payload_version=1,
            payload=payload.model_dump(mode="json"),
            idempotency_key=f"exhausted-{uuid4()}",
            max_attempts=1,
        )
        await session.execute(
            sa_text(
                "UPDATE application_jobs SET status = 'processing', "
                "attempt_count = 1, "
                "lease_owner = 'expired-worker', "
                "lease_token = 'expired-token', "
                "lease_expires_at = now() - interval '1 second' "
                "WHERE id = :job_id"
            ).bindparams(job_id=job_id)
        )
        await session.commit()

    metrics = MetricsRegistry()
    registry = _enrichment_registry(
        pg_session_factory,
        _providers(
            judge=DeterministicJudgeProvider(pages={}),
            search=DeterministicSearchProvider(),
        ),
        settings,
    )
    await _run_worker_to_status(
        pg_session_factory,
        registry,
        settings,
        metrics,
        job_id,
        JobStatus.failed,
    )
    assert metrics.enrichment_efficacy_counts == {("1", "failed", False): 1}
    observations = await _observation_rows(pg_session_factory)
    assert len(observations) == 1
    assert observations[0]["job_id"] == job_id
    assert observations[0]["lifecycle_outcome"] == "failed"
    assert observations[0]["policy_label"] == "1"


@pytest.mark.parametrize(
    "policy_value",
    [None, "not-a-number", True, 0, -1, 999],
    ids=["missing", "string", "boolean", "zero", "negative", "unknown-positive"],
)
async def test_reconciliation_malformed_exhausted_policies_emit_unsupported_failed_observation(
    pg_session_factory,
    policy_value,
) -> None:
    from sqlalchemy import text as sa_text

    from app.jobs.repository import JobRepository
    from app.jobs.worker import Worker
    from app.observability.metrics import MetricsRegistry

    payload = await _confirmed_payload(pg_session_factory)
    malformed_payload = payload.model_dump(mode="json")
    malformed_payload["policy_version"] = policy_value
    async with pg_session_factory() as session:
        job_id = await JobRepository(session).enqueue(
            job_type=JobType.enrich_confirmed_plant.value,
            payload_version=1,
            payload=malformed_payload,
            idempotency_key=f"malformed-exhausted-{uuid4()}",
            max_attempts=1,
        )
        await session.execute(
            sa_text(
                "UPDATE application_jobs SET status = 'processing', "
                "attempt_count = 1, "
                "lease_owner = 'expired-worker', "
                "lease_token = 'expired-token', "
                "lease_expires_at = now() - interval '1 second' "
                "WHERE id = :job_id"
            ).bindparams(job_id=job_id)
        )
        await session.commit()

    worker = Worker(
        session_factory=pg_session_factory,
        handler_registry=HandlerRegistry(),
        settings=Settings(
            jobs_producer_enabled=False,
            jobs_worker_enabled=True,
            jobs_poll_interval_seconds=0.05,
            jobs_lease_duration_seconds=30.0,
            jobs_lease_renewal_interval_seconds=0.05,
            jobs_backoff_base_seconds=0.05,
            jobs_metrics_port=0,
        ),
        metrics=MetricsRegistry(),
    )
    await worker._reconcile()

    observations = await _observation_rows(pg_session_factory)
    assert len(observations) == 1, policy_value
    assert observations[0]["job_id"] == job_id
    assert observations[0]["lifecycle_outcome"] == "failed"
    assert observations[0]["policy_label"] == "unsupported"


async def test_observation_completion_duration_includes_retry_backoff_and_replacement_time(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
) -> None:
    from sqlalchemy import text as sa_text

    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    get_settings.cache_clear()
    settings = get_settings()

    # Retry path: the durable observation duration must span from job
    # creation through the terminal commit, including the retry backoff and
    # the replacement-worker recovery time, not just the final attempt.
    job_id, _payload = await _schedule_via_confirmation(pg_session_factory)
    async with pg_session_factory() as session:
        await session.execute(
            sa_text(
                "UPDATE application_jobs SET created_at = now() - interval '5 seconds' "
                "WHERE id = :id"
            ),
            {"id": job_id},
        )
        await session.commit()
    providers = _providers(
        judge=DeterministicJudgeProvider(
            pages={PAGE_URL: (WATERING,)},
            fail_attempts=1,
        ),
        search=DeterministicSearchProvider(page=_page()),
    )
    metrics = MetricsRegistry()
    await _run_worker_to_status(
        pg_session_factory,
        _enrichment_registry(pg_session_factory, providers, settings),
        settings,
        metrics,
        job_id,
        JobStatus.partial,
    )
    observations = await _observation_rows(pg_session_factory)
    assert len(observations) == 1
    assert observations[0]["lifecycle_outcome"] == "partial"
    assert observations[0]["duration_seconds"] >= 5.0

    # Replacement path: an expired lease reclaimed by another worker still
    # measures the terminal duration from the original job creation.
    job_id, _payload = await _schedule_via_confirmation(pg_session_factory)
    async with pg_session_factory() as session:
        await session.execute(
            sa_text(
                "UPDATE application_jobs SET created_at = now() - interval '5 seconds', "
                "status = 'processing', lease_owner = 'expired-worker', "
                "lease_token = 'expired-token', "
                "lease_expires_at = now() - interval '1 second', attempt_count = 1 "
                "WHERE id = :id"
            ),
            {"id": job_id},
        )
        await session.commit()
    replacement_providers = _providers(
        judge=DeterministicJudgeProvider(pages={PAGE_URL: (WATERING,)}),
        search=DeterministicSearchProvider(page=_page()),
    )
    metrics = MetricsRegistry()
    await _run_worker_to_status(
        pg_session_factory,
        _enrichment_registry(pg_session_factory, replacement_providers, settings),
        settings,
        metrics,
        job_id,
        JobStatus.partial,
    )
    observations = await _observation_rows(pg_session_factory)
    for row in observations:
        if row["job_id"] == job_id:
            assert row["lifecycle_outcome"] == "partial"
            assert row["duration_seconds"] >= 5.0
            break
    else:
        pytest.fail("replacement-path observation missing")
