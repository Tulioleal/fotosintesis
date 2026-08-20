"""Manual plant search candidate creation and confirmation.

Covers the manual-search path: creating a user-owned, unconfirmed manual
candidate from a GBIF identity (no image, no synthetic confidence), rejecting
unvalidated identities, confirmation reuse through the enrichment scheduler,
ownership checks, and blocking unvalidated/unowned candidates.
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import identification_candidates
from app.core.settings import get_settings
from app.identification.confirmation import (
    CandidateConfirmationService,
    ConfirmationRejectedError,
)
from app.identification.gbif import GbifTaxonomy
from app.identification.repository import IdentificationRepository


def _accepted_taxonomy() -> GbifTaxonomy:
    return GbifTaxonomy(
        key=2878688,
        accepted_key=2878688,
        accepted_scientific_name="Monstera deliciosa Liebm.",
        binomial_name="Monstera deliciosa",
        taxonomic_status="ACCEPTED",
        rank="SPECIES",
        synonyms=[],
        genus="Monstera",
        family="Araceae",
        species="Monstera deliciosa",
        matched=True,
    )


def _enable_producer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBS_PRODUCER_ENABLED", "true")
    get_settings.cache_clear()


async def _user(session_factory, email: str) -> tuple[object, str]:
    async with session_factory() as session:
        auth = DatabaseAuthRepository(session)
        user = await auth.create_user("Owner", email, "password123")
        auth_session = await auth.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )
    return user, auth_session.token


@pytest.mark.asyncio
async def test_create_manual_candidate_has_no_image_and_no_synthetic_confidence(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user, _ = await _user(session_factory, "manual-create@example.com")

    async with session_factory() as session:
        candidate = await IdentificationRepository(session).create_manual_candidate(
            user_id=user.id,
            query="Monstera deliciosa",
            taxonomy=_accepted_taxonomy(),
        )

    assert candidate.validation_status.value == "validated"
    assert candidate.confidence_label == "manual"
    assert candidate.confirmed_at is None
    assert candidate.accepted_scientific_name == "Monstera deliciosa Liebm."
    assert candidate.binomial_name == "Monstera deliciosa"
    assert candidate.genus == "Monstera"
    assert candidate.family == "Araceae"

    async with session_factory() as session:
        row = (
            await session.execute(
                select(identification_candidates).where(
                    identification_candidates.c.id == candidate.id
                )
            )
        ).first()
    assert row.identification_id is None
    assert row.origin == "manual_search"
    assert row.user_id == user.id
    assert row.confidence_label == "manual"


@pytest.mark.asyncio
async def test_create_manual_candidate_rejects_unvalidated_identity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user, _ = await _user(session_factory, "manual-invalid@example.com")

    async with session_factory() as session:
        with pytest.raises(ValueError):
            await IdentificationRepository(session).create_manual_candidate(
                user_id=user.id,
                query="Monstera",
                taxonomy=GbifTaxonomy(
                    key=1,
                    accepted_key=1,
                    accepted_scientific_name="Monstera",
                    binomial_name=None,
                    taxonomic_status="ACCEPTED",
                    matched=True,
                ),
            )

    async with session_factory() as session:
        count = len(
            (
                await session.execute(
                    select(identification_candidates).where(
                        identification_candidates.c.user_id == user.id
                    )
                )
            ).all()
        )
    assert count == 0


@pytest.mark.asyncio
async def test_confirm_manual_candidate_reuses_enrichment_scheduling(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_producer(monkeypatch)
    user, _ = await _user(session_factory, "manual-confirm@example.com")

    async with session_factory() as session:
        candidate = await IdentificationRepository(session).create_manual_candidate(
            user_id=user.id,
            query="Monstera deliciosa",
            taxonomy=_accepted_taxonomy(),
        )
        response = await CandidateConfirmationService(session).confirm_manual(
            candidate_id=candidate.id, user_id=user.id
        )

    assert response.status == "confirmed"
    assert response.candidate.id == candidate.id
    assert response.enrichment.job.status.value == "pending"

    async with session_factory() as session:
        confirmed = (
            await session.execute(
                select(identification_candidates).where(
                    identification_candidates.c.id == candidate.id
                )
            )
        ).first()
    assert confirmed.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirm_manual_candidate_blocks_unowned(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_producer(monkeypatch)
    owner, _ = await _user(session_factory, "manual-owner@example.com")
    other, _ = await _user(session_factory, "manual-other@example.com")

    async with session_factory() as session:
        candidate = await IdentificationRepository(session).create_manual_candidate(
            user_id=owner.id,
            query="Monstera deliciosa",
            taxonomy=_accepted_taxonomy(),
        )
        with pytest.raises(ConfirmationRejectedError):
            await CandidateConfirmationService(session).confirm_manual(
                candidate_id=candidate.id, user_id=other.id
            )

    async with session_factory() as session:
        row = (
            await session.execute(
                select(identification_candidates).where(
                    identification_candidates.c.id == candidate.id
                )
            )
        ).first()
    assert row.confirmed_at is None


@pytest.mark.asyncio
async def test_confirm_manual_candidate_blocks_unvalidated(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_producer(monkeypatch)
    user, _ = await _user(session_factory, "manual-unvalidated@example.com")

    async with session_factory() as session:
        candidate = await IdentificationRepository(session).create_manual_candidate(
            user_id=user.id,
            query="Monstera deliciosa",
            taxonomy=_accepted_taxonomy(),
        )
        # Downgrade the candidate so it is no longer taxonomically validated.
        from sqlalchemy import update

        await session.execute(
            update(identification_candidates)
            .where(identification_candidates.c.id == candidate.id)
            .values(validation_status="no_gbif_match")
        )
        await session.commit()

        with pytest.raises(ConfirmationRejectedError):
            await CandidateConfirmationService(session).confirm_manual(
                candidate_id=candidate.id, user_id=user.id
            )
