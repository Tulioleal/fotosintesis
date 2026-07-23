from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, insert, select, update

from app.auth.tables import (
    application_jobs,
    candidate_enrichment_jobs,
    identification_candidates,
    identification_images,
    users,
)
from app.jobs.repository import JobRepository
from app.jobs.schemas import EnrichmentJobResult, JobStatus
from app.enrichment.policy import ENRICHMENT_POLICY_V1


def _result() -> EnrichmentJobResult:
    covered = sorted(aspect.value for aspect in ENRICHMENT_POLICY_V1.required_aspects)
    return EnrichmentJobResult(
        outcome="complete",
        policy_version=1,
        covered_aspects=covered,
        missing_aspects=[],
        covered_count=len(covered),
        missing_count=0,
    )


async def test_active_enrichment_reuses_active_job_and_terminal_release_allows_new_run(
    session_factory,
) -> None:
    active_key = "enrichment-active:test"
    first_run_id = uuid4()
    second_run_id = uuid4()
    third_run_id = uuid4()
    async with session_factory() as session:
        repository = JobRepository(session)
        first = await repository.enqueue_active_enrichment(
            payload_version=1,
            payload={"run_id": str(first_run_id)},
            idempotency_key="run-one",
            active_deduplication_key=active_key,
        )
        reused = await repository.enqueue_active_enrichment(
            payload_version=1,
            payload={"run_id": str(second_run_id)},
            idempotency_key="run-two",
            active_deduplication_key=active_key,
        )
        token = str(uuid4())
        await session.execute(
            update(application_jobs)
            .where(application_jobs.c.id == first.job_id)
            .values(
                status=JobStatus.processing.value,
                lease_owner="worker",
                lease_token=token,
                lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        assert await repository.complete_job(
            job_id=first.job_id,
            owner="worker",
            lease_token=token,
            result=_result(),
        )
        second = await repository.enqueue_active_enrichment(
            payload_version=1,
            payload={"run_id": str(third_run_id)},
            idempotency_key="run-three",
            active_deduplication_key=active_key,
        )
        await session.commit()

        terminal_active_key = await session.scalar(
            select(application_jobs.c.active_deduplication_key).where(
                application_jobs.c.id == first.job_id
            )
        )

    assert first.created is True
    assert reused.job_id == first.job_id
    assert reused.created is False
    assert terminal_active_key is None
    assert second.created is True
    assert second.job_id != first.job_id


async def test_candidate_policy_replay_and_authorized_status_preserve_association(
    session_factory,
) -> None:
    user_id = uuid4()
    other_user_id = uuid4()
    image_id = uuid4()
    candidate_id = uuid4()
    first_run_id = uuid4()
    replay_run_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            insert(users),
            [
                {"id": user_id, "name": "Owner", "email": "owner@example.org"},
                {"id": other_user_id, "name": "Other", "email": "other@example.org"},
            ],
        )
        await session.execute(
            insert(identification_images).values(
                id=image_id,
                user_id=user_id,
                storage_path="plant.jpg",
                mime_type="image/jpeg",
                size_bytes=10,
                status="complete",
            )
        )
        await session.execute(
            insert(identification_candidates).values(
                id=candidate_id,
                identification_id=image_id,
                suggested_scientific_name="Monstera deliciosa",
                confidence_label="high",
                possible_match_copy="match",
                validation_status="validated",
            )
        )
        repository = JobRepository(session)
        first = await repository.associate_candidate_enrichment(
            candidate_id=candidate_id,
            user_id=user_id,
            policy_version=1,
            payload_version=1,
            payload={"payload_version": 1, "run_id": str(first_run_id)},
            idempotency_key="candidate-run-one",
            active_deduplication_key="candidate-active-one",
        )
        replay = await repository.associate_candidate_enrichment(
            candidate_id=candidate_id,
            user_id=user_id,
            policy_version=1,
            payload_version=1,
            payload={"payload_version": 1, "run_id": str(replay_run_id)},
            idempotency_key="candidate-run-two",
            active_deduplication_key="candidate-active-one",
        )
        upgraded = await repository.associate_candidate_enrichment(
            candidate_id=candidate_id,
            user_id=user_id,
            policy_version=2,
            payload_version=1,
            payload={"payload_version": 1, "run_id": str(uuid4())},
            idempotency_key="candidate-run-policy-two",
            active_deduplication_key="candidate-active-policy-two",
        )
        association_count = await session.scalar(
            select(func.count()).select_from(candidate_enrichment_jobs)
        )
        owner_status = await repository.get_candidate_enrichment_status(
            candidate_id=candidate_id,
            user_id=user_id,
            policy_version=1,
        )
        foreign_status = await repository.get_candidate_enrichment_status(
            candidate_id=candidate_id,
            user_id=other_user_id,
            policy_version=1,
        )

    assert first.association_created is True
    assert replay.job_id == first.job_id
    assert replay.association_created is False
    assert upgraded.association_created is True
    assert upgraded.job_id != first.job_id
    assert association_count == 2
    assert owner_status and owner_status.job.id == first.job_id
    assert foreign_status is None
