"""Section-level profile refresh from accepted evidence.

Covers partial refresh (only affected sections change), failure fallback
(previous version preserved and marked stale), collapse of duplicate refresh
signals by fingerprint, and bounded legacy reconciliation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.auth.tables import (
    application_jobs,
    enrichment_validation_evidence,
    enrichment_validation_runs,
    knowledge_chunks,
    knowledge_document_aspect_supports,
    knowledge_documents,
    knowledge_sources,
    plant_profiles,
    profile_refresh_enrichment_jobs,
    taxonomy_provenance_snapshots,
)
from app.enrichment.policy import CURRENT_ENRICHMENT_POLICY_VERSION
from app.jobs.handlers.refresh_profile import RefreshProfileHandler
from app.jobs.schemas import RefreshProfilePayload
from app.profile_garden.reconcile import LegacyReconciliationService
from app.profile_garden.refresh import ProfileRefreshService

from ._enrichment_helpers import SPECIES_KEY, SPECIES_NAME

SPECIES_GBIF = 2878688
NOW = datetime(2026, 8, 1, tzinfo=UTC)


async def _seed_evidence(
    pg_session_factory,
    *,
    aspects: list[str],
    content: str,
    source_version: str = "v1",
    topic: str = "pests",
) -> None:
    async with pg_session_factory() as session:
        job_id = uuid4()
        await session.execute(
            application_jobs.insert().values(
                id=job_id,
                job_type="enrich_confirmed_plant",
                payload_version=1,
                payload={"run_id": str(job_id)},
                status="complete",
                idempotency_key=f"job-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        provenance_id = uuid4()
        await session.execute(
            taxonomy_provenance_snapshots.insert().values(
                id=provenance_id,
                canonical_species_key=SPECIES_KEY,
                accepted_gbif_key=SPECIES_GBIF,
                normalized_binomial=SPECIES_NAME,
                taxonomy_source="gbif",
                taxonomy_source_version=f"fixture-{uuid4().hex[:8]}",
                snapshot={"accepted": True},
                resolved_at=NOW,
            )
        )
        validation_id = uuid4()
        await session.execute(
            enrichment_validation_runs.insert().values(
                id=validation_id,
                job_id=job_id,
                taxonomy_provenance_id=provenance_id,
                policy_version=1,
                required_aspects=aspects,
                covered_aspects=aspects,
                missing_aspects=[],
                answerability_status="full",
                judge_confidence=0.9,
                validation_metadata={},
                created_at=NOW,
            )
        )
        document_id = uuid4()
        source_id = uuid4()
        chunk_id = uuid4()
        await session.execute(
            knowledge_documents.insert().values(
                id=document_id,
                scientific_name=SPECIES_NAME,
                topic=topic,
                title=f"{SPECIES_NAME} evidence",
                content=content,
                confidence=0.9,
                review_status="auto_ingested",
                canonical_species_key=SPECIES_KEY,
                accepted_gbif_key=SPECIES_GBIF,
                normalized_binomial=SPECIES_NAME,
                canonical_source_url="https://example.org/monstera-care",
                canonical_source_domain="example.org",
                source_version=source_version,
                normalized_content_hash="a" * 64,
                source_retrieved_at=NOW,
                enrichment_provenance={"kind": "confirmed_plant_enrichment", "version": 1},
                taxonomy_provenance_id=provenance_id,
            )
        )
        await session.execute(
            knowledge_sources.insert().values(
                id=source_id,
                document_id=document_id,
                title=f"{SPECIES_NAME} source",
                url="https://example.org/monstera-care",
                source_domain="example.org",
                retrieved_at=NOW,
                validation_status="trusted",
            )
        )
        await session.execute(
            knowledge_chunks.insert().values(
                id=chunk_id,
                document_id=document_id,
                source_id=source_id,
                chunk_index=0,
                content=content,
                metadata={"covered_aspects": aspects},
                scientific_name=SPECIES_NAME,
                topic=topic,
                source_domain="example.org",
                source_url="https://example.org/monstera-care",
                confidence=0.9,
                review_status="auto_ingested",
                retrieved_at=NOW,
            )
        )
        for aspect in aspects:
            await session.execute(
                knowledge_document_aspect_supports.insert().values(
                    id=uuid4(),
                    document_id=document_id,
                    aspect=aspect,
                    support_confidence=0.9,
                    review_status="auto_ingested",
                )
            )
        await session.execute(
            enrichment_validation_evidence.insert().values(
                id=uuid4(),
                validation_run_id=validation_id,
                document_id=document_id,
            )
        )
        await session.commit()


async def _seed_profile(pg_session_factory, *, sections, section_versions, **extra) -> str:
    async with pg_session_factory() as session:
        profile_id = uuid4()
        await session.execute(
            plant_profiles.insert().values(
                id=profile_id,
                scientific_name=SPECIES_NAME,
                common_name="Monstera",
                aliases=[],
                sections=sections,
                sources=[],
                confidence=0.6,
                limitations=[],
                accepted_gbif_key=SPECIES_GBIF,
                normalized_binomial=SPECIES_NAME,
                canonical_species_key=SPECIES_KEY,
                generation_policy_version=CURRENT_ENRICHMENT_POLICY_VERSION,
                section_versions=section_versions,
                **extra,
            )
        )
        await session.commit()
    return str(profile_id)


def _versions(status: str = "current", section: str = "pests") -> dict:
    return {
        "description": {
            "section_id": "description",
            "aspects": [],
            "policy_version": 1,
            "fingerprint": "old",
            "provenance": [],
            "confidence": 0.6,
            "limitations": [],
            "status": status,
            "generated_at": NOW.isoformat(),
        },
        section: {
            "section_id": section,
            "aspects": ["pest_identification"],
            "policy_version": 1,
            "fingerprint": "old",
            "provenance": [],
            "confidence": 0.6,
            "limitations": [],
            "status": status,
            "generated_at": NOW.isoformat(),
        },
    }


async def test_partial_refresh_only_replaces_affected_sections(pg_session_factory) -> None:
    await _seed_evidence(
        pg_session_factory,
        aspects=["pest_identification"],
        content="Monstera needs pest control.",
        source_version="v2",
    )
    sections = {
        "description": ["Original description."],
        "pests": ["Original pest guidance."],
    }
    profile_id = await _seed_profile(pg_session_factory, sections=sections, section_versions=_versions())

    async with pg_session_factory() as session:
        result = await ProfileRefreshService(session).refresh_sections(
            species={"canonical_species_key": SPECIES_KEY, "normalized_binomial": SPECIES_NAME},
            changed_aspects=["pest_identification"],
            generation_policy_version=CURRENT_ENRICHMENT_POLICY_VERSION,
        )
        row = (
            await session.execute(select(plant_profiles).where(plant_profiles.c.id == profile_id))
        ).first()

    assert set(result["regenerated"]) == {"pests"}
    # Affected pests section was regenerated; unaffected description preserved.
    assert row.sections["pests"] == ["Monstera needs pest control."]
    assert row.sections["description"] == ["Original description."]
    assert row.section_versions["pests"]["fingerprint"] != "old"
    assert row.section_versions["pests"]["status"] == "current"
    assert row.section_versions["description"]["fingerprint"] == "old"


async def test_refresh_failure_preserves_previous_and_marks_stale(
    pg_session_factory, monkeypatch
) -> None:
    # Force regeneration to fail so the failure-fallback path runs: the
    # previous section version must remain readable and be marked stale.
    async def _boom(*args, **kwargs):
        raise RuntimeError("regeneration failed")

    sections = {
        "description": ["Original description."],
        "pests": ["Original pest guidance."],
    }
    profile_id = await _seed_profile(pg_session_factory, sections=sections, section_versions=_versions())

    monkeypatch.setattr(
        "app.profile_garden.refresh.PlantProfileGardenRepository._profile_evidence_chunks",
        _boom,
    )
    with pytest.raises(Exception):
        async with pg_session_factory() as session:
            await ProfileRefreshService(session).refresh_sections(
                species={"canonical_species_key": SPECIES_KEY, "normalized_binomial": SPECIES_NAME},
                changed_aspects=["pest_identification"],
                generation_policy_version=CURRENT_ENRICHMENT_POLICY_VERSION,
            )

    async with pg_session_factory() as session:
        row = (
            await session.execute(select(plant_profiles).where(plant_profiles.c.id == profile_id))
        ).first()
    # Previous content preserved; affected section surfaced as stale.
    assert row.sections["pests"] == ["Original pest guidance."]
    assert row.section_versions["pests"]["status"] == "stale"
    assert row.section_versions["description"]["status"] == "current"


async def test_duplicate_refresh_signals_collapse_by_fingerprint(pg_session_factory) -> None:
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.profile_garden.signals import enqueue_profile_refresh

    identity = CanonicalSpeciesIdentity(
        accepted_gbif_key=SPECIES_GBIF,
        normalized_binomial=SPECIES_NAME,
        taxonomy_validated=True,
    )
    evidence = [
        {"source_url": "https://example.org/monstera-care", "source_version": "v2"}
    ]
    for _ in range(2):
        async with pg_session_factory() as session:
            await enqueue_profile_refresh(
                session,
                identity=identity,
                changed_aspects=["light_exposure"],
                generation_policy_version=1,
                evidence=evidence,
            )
            await session.commit()

    async with pg_session_factory() as session:
        rows = (
            await session.execute(
                select(application_jobs).where(application_jobs.c.job_type == "refresh_profile")
            )
        ).all()
    assert len(rows) == 1, "duplicate refresh signals must collapse to one job"


async def test_refresh_profile_handler_reports_complete(pg_session_factory) -> None:
    await _seed_evidence(
        pg_session_factory,
        aspects=["pest_identification"],
        content="Monstera needs pest control.",
        source_version="v2",
    )
    sections = {"description": ["Original description."], "pests": ["Original pest guidance."]}
    await _seed_profile(pg_session_factory, sections=sections, section_versions=_versions())

    handler = RefreshProfileHandler(session_factory=pg_session_factory)
    payload = RefreshProfilePayload(
        payload_version=1,
        policy_version=1,
        species={"accepted_gbif_key": SPECIES_GBIF, "normalized_binomial": SPECIES_NAME},
        changed_aspects=["pest_identification"],
        fingerprint="fp",
        run_id=uuid4(),
    )
    result = await handler.handle(payload=payload, attempt_count=1, max_attempts=3)
    assert result.status.value == "complete"
    assert result.result.regenerated_sections == ["pests"]


async def test_legacy_reconciliation_signals_insufficient_sections(pg_session_factory) -> None:
    # A legacy profile with no section_versions and insufficient fallback text.
    sections = {
        "description": ["Insufficient evidence for description of Monstera deliciosa."],
        "care": ["Sourced care content."],
    }
    await _seed_profile(pg_session_factory, sections=sections, section_versions={})

    async with pg_session_factory() as session:
        summary = await LegacyReconciliationService(session).reconcile_batch(limit=10)

    assert summary["evaluated"] >= 1
    assert summary["signalled"] >= 1
    # Historical text is preserved.
    async with pg_session_factory() as session:
        row = (
            await session.execute(select(plant_profiles))
        ).first()
    assert row.sections["description"] == [
        "Insufficient evidence for description of Monstera deliciosa."
    ]
    assert row.sections["care"] == ["Sourced care content."]


async def _associations(pg_session_factory) -> list:
    async with pg_session_factory() as session:
        return (
            await session.execute(select(profile_refresh_enrichment_jobs))
        ).all()


async def _seed_enrichment_job(pg_session_factory) -> object:
    """Insert one durable enrichment job and return its id."""
    job_id = uuid4()
    async with pg_session_factory() as session:
        await session.execute(
            application_jobs.insert().values(
                id=job_id,
                job_type="enrich_confirmed_plant",
                payload_version=1,
                payload={"run_id": str(job_id)},
                status="processing",
                idempotency_key=f"enrich-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
            )
        )
        await session.commit()
    return job_id


async def test_enrichment_causes_one_refresh_association(pg_session_factory) -> None:
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.profile_garden.signals import enqueue_profile_refresh

    identity = CanonicalSpeciesIdentity(
        accepted_gbif_key=SPECIES_GBIF,
        normalized_binomial=SPECIES_NAME,
        taxonomy_validated=True,
    )
    evidence = [
        {"source_url": "https://example.org/monstera-care", "source_version": "v2"}
    ]
    enrichment_job_id = await _seed_enrichment_job(pg_session_factory)
    async with pg_session_factory() as session:
        result = await enqueue_profile_refresh(
            session,
            identity=identity,
            changed_aspects=["light_exposure"],
            generation_policy_version=1,
            evidence=evidence,
            caused_by_enrichment_job_id=enrichment_job_id,
        )
        await session.commit()

    associations = await _associations(pg_session_factory)
    assert len(associations) == 1
    mapping = associations[0]._mapping
    assert mapping["refresh_job_id"] == result.job_id
    assert mapping["enrichment_job_id"] == enrichment_job_id


async def test_same_fingerprint_reuse_does_not_duplicate_association(
    pg_session_factory,
) -> None:
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.profile_garden.signals import enqueue_profile_refresh

    identity = CanonicalSpeciesIdentity(
        accepted_gbif_key=SPECIES_GBIF,
        normalized_binomial=SPECIES_NAME,
        taxonomy_validated=True,
    )
    evidence = [
        {"source_url": "https://example.org/monstera-care", "source_version": "v2"}
    ]
    enrichment_job_id = await _seed_enrichment_job(pg_session_factory)
    job_ids: set = set()
    for _ in range(2):
        async with pg_session_factory() as session:
            result = await enqueue_profile_refresh(
                session,
                identity=identity,
                changed_aspects=["light_exposure"],
                generation_policy_version=1,
                evidence=evidence,
                caused_by_enrichment_job_id=enrichment_job_id,
            )
            await session.commit()
            job_ids.add(result.job_id)

    # Same fingerprint collapses to one refresh job...
    async with pg_session_factory() as session:
        rows = (
            await session.execute(
                select(application_jobs).where(
                    application_jobs.c.job_type == "refresh_profile"
                )
            )
        ).all()
    assert len(rows) == 1
    assert len(job_ids) == 1
    # ...and the identical association is not duplicated.
    associations = await _associations(pg_session_factory)
    assert len(associations) == 1


async def test_two_enrichments_share_one_refresh_association(
    pg_session_factory,
) -> None:
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.profile_garden.signals import enqueue_profile_refresh

    identity = CanonicalSpeciesIdentity(
        accepted_gbif_key=SPECIES_GBIF,
        normalized_binomial=SPECIES_NAME,
        taxonomy_validated=True,
    )
    evidence = [
        {"source_url": "https://example.org/monstera-care", "source_version": "v2"}
    ]
    first_enrichment = await _seed_enrichment_job(pg_session_factory)
    second_enrichment = await _seed_enrichment_job(pg_session_factory)
    refresh_job_ids: set = set()
    for enrichment_job_id in (first_enrichment, second_enrichment):
        async with pg_session_factory() as session:
            result = await enqueue_profile_refresh(
                session,
                identity=identity,
                changed_aspects=["light_exposure"],
                generation_policy_version=1,
                evidence=evidence,
                caused_by_enrichment_job_id=enrichment_job_id,
            )
            await session.commit()
            refresh_job_ids.add(result.job_id)

    # The reused refresh job carries both causal associations.
    assert len(refresh_job_ids) == 1
    refresh_job_id = next(iter(refresh_job_ids))
    associations = await _associations(pg_session_factory)
    pairs = {
        (
            row._mapping["refresh_job_id"],
            row._mapping["enrichment_job_id"],
        )
        for row in associations
    }
    assert pairs == {
        (refresh_job_id, first_enrichment),
        (refresh_job_id, second_enrichment),
    }


async def test_legacy_reconciliation_creates_no_false_association(
    pg_session_factory,
) -> None:
    sections = {
        "description": ["Insufficient evidence for description of Monstera deliciosa."],
        "care": ["Sourced care content."],
    }
    await _seed_profile(pg_session_factory, sections=sections, section_versions={})

    async with pg_session_factory() as session:
        summary = await LegacyReconciliationService(session).reconcile_batch(limit=10)

    assert summary["signalled"] >= 1
    associations = await _associations(pg_session_factory)
    assert associations == [], (
        "legacy reconciliation must not fabricate enrichment causality"
    )


async def test_association_rolls_back_with_surrounding_transaction(
    pg_session_factory,
) -> None:
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.profile_garden.signals import enqueue_profile_refresh

    identity = CanonicalSpeciesIdentity(
        accepted_gbif_key=SPECIES_GBIF,
        normalized_binomial=SPECIES_NAME,
        taxonomy_validated=True,
    )
    evidence = [
        {"source_url": "https://example.org/monstera-care", "source_version": "v2"}
    ]
    # The causing enrichment job must exist durably; only the association is
    # rolled back together with the surrounding evidence transaction.
    enrichment_job_id = await _seed_enrichment_job(pg_session_factory)
    async with pg_session_factory() as session:
        await enqueue_profile_refresh(
            session,
            identity=identity,
            changed_aspects=["light_exposure"],
            generation_policy_version=1,
            evidence=evidence,
            caused_by_enrichment_job_id=enrichment_job_id,
        )
        await session.rollback()

    associations = await _associations(pg_session_factory)
    assert associations == [], (
        "association insertion must roll back with the evidence transaction"
    )
