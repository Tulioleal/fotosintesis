from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select

from app.auth.tables import (
    application_jobs,
    candidate_enrichment_jobs,
    identification_candidates,
    identification_images,
    taxonomy_provenance_snapshots,
    users,
)
from app.core.settings import Settings
from app.identification.confirmation import CandidateConfirmationService


@pytest.mark.asyncio
async def test_postgres_confirmation_atomically_persists_and_replays_current_policy(
    pg_session_factory,
) -> None:
    user_id = uuid4()
    identification_id = uuid4()
    candidate_id = uuid4()
    async with pg_session_factory() as session:
        await session.execute(
            insert(users).values(
                id=user_id,
                name="Owner",
                email=f"{user_id}@example.org",
            )
        )
        await session.execute(
            insert(identification_images).values(
                id=identification_id,
                user_id=user_id,
                storage_path="plant.jpg",
                mime_type="image/jpeg",
                size_bytes=10,
                metadata={},
                status="needs_confirmation",
                message="Confirm.",
            )
        )
        await session.execute(
            insert(identification_candidates).values(
                id=candidate_id,
                identification_id=identification_id,
                suggested_scientific_name="Monstera deliciosa",
                confidence_label="high",
                visible_traits=[],
                possible_match_copy="Possible match.",
                gbif_key=2878688,
                gbif_accepted_key=2878688,
                accepted_scientific_name="Monstera deliciosa",
                binomial_name="Monstera deliciosa",
                taxonomic_status="ACCEPTED",
                synonyms=[],
                genus="Monstera",
                family="Araceae",
                species="Monstera deliciosa",
                validation_status="validated",
            )
        )
        await session.commit()

        service = CandidateConfirmationService(
            session,
            Settings(jobs_producer_enabled=True),
        )
        first = await service.confirm(
            identification_id=identification_id,
            candidate_id=candidate_id,
            user_id=user_id,
        )
        replay = await service.confirm(
            identification_id=identification_id,
            candidate_id=candidate_id,
            user_id=user_id,
        )

        assert replay.enrichment.job.id == first.enrichment.job.id
        assert await session.scalar(select(func.count()).select_from(application_jobs)) == 1
        assert await session.scalar(
            select(func.count()).select_from(candidate_enrichment_jobs)
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(taxonomy_provenance_snapshots)
        ) == 1
