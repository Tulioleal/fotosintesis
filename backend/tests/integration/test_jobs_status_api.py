"""HTTP-level tests for the job status API.

Uses ``httpx.AsyncClient`` against the FastAPI ASGI app so that the
async database engine from the test fixtures remains usable.
"""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.jobs.schemas import JobStatusResponse, JobType

pytestmark = [
    pytest.mark.skipif(
        "SKIP_PG_TESTS" in __import__("os").environ,
        reason="PostgreSQL not available (SKIP_PG_TESTS is set)",
    ),
]


@pytest.fixture
async def http_client(pg_session_factory, test_user):
    """AsyncClient bound to the per-test schema via the same async engine."""
    from app.main import app
    from app.auth.dependencies import get_current_user
    from app.db.session import get_async_session
    from app.db import session as session_module

    class _FakeAuth:
        def __init__(self, uid: UUID) -> None:
            self.id = uid

    def _override_user():
        return _FakeAuth(test_user)

    async def _override_session():
        async with pg_session_factory() as s:
            yield s

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_async_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, test_user, pg_session_factory
    app.dependency_overrides.clear()


async def _enqueue_for(pg_session_factory, *, user_id: UUID | None, key: str) -> UUID:
    from app.jobs.repository import JobRepository

    async with pg_session_factory() as s:
        repo = JobRepository(s)
        job_id = await repo.enqueue(
            job_type=JobType.ingest_validated_claims.value,
            payload_version=1,
            payload={
                "claims": [
                    {
                        "scientific_name": "Test",
                        "topic": "care",
                        "source_url": "https://example.org/x",
                        "source_domain": "example.org",
                        "source_provenance": "trusted",
                        "claim": "secret",
                        "evidence_quote": "secret",
                        "confidence": 0.9,
                        "covered_aspects": ["watering"],
                        "answerability_status": "full",
                    },
                ],
                "conversation_id": "should-not-leak",
            },
            idempotency_key=key,
            user_id=user_id,
        )
        await s.commit()
    return job_id


class TestJobStatusAPI:
    async def test_owner_reads_status(self, http_client):
        client, user, factory = http_client
        job_id = await _enqueue_for(factory, user_id=user, key="owner-1")
        response = await client.get(f"/jobs/{job_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        JobStatusResponse.model_validate(body)
        # The response must not echo any of the raw payload fields.
        forbidden_substrings = (
            "https://", "secret", "should-not-leak",
            str(user),
        )
        for token in forbidden_substrings:
            assert token not in response.text, f"leaked {token!r}"
        # And the model must not contain payload-bearing keys.
        forbidden_keys = {
            "payload", "claims", "quote", "evidence_quote", "source_body",
            "prompt", "user_notes", "tokens", "idempotency_key",
            "lease_token", "lease_owner", "conversation_id",
        }
        assert forbidden_keys.isdisjoint(body.keys()), body.keys()

    async def test_foreign_owner_returns_404(self, http_client, pg_engine):
        from app.auth.tables import users
        from sqlalchemy.ext.asyncio import AsyncSession

        client, _user, factory = http_client
        # Create a real but different user and enqueue a job owned by it.
        foreign_id = uuid4()
        async with AsyncSession(pg_engine) as s:
            await s.execute(
                users.insert().values(
                    id=foreign_id,
                    name="Foreign",
                    email=f"{foreign_id}@test.invalid",
                    email_verified=True,
                )
            )
            await s.commit()
        job_id = await _enqueue_for(factory, user_id=foreign_id, key="foreign-1")
        response = await client.get(f"/jobs/{job_id}")
        assert response.status_code == 404

    async def test_unknown_id_returns_404(self, http_client):
        client, _user, _factory = http_client
        response = await client.get(f"/jobs/{uuid4()}")
        assert response.status_code == 404

    async def test_internal_job_returns_404(self, http_client):
        client, _user, factory = http_client
        job_id = await _enqueue_for(factory, user_id=None, key="internal-1")
        response = await client.get(f"/jobs/{job_id}")
        assert response.status_code == 404

    async def test_unauthenticated_returns_401(self, pg_session_factory):
        from app.main import app
        from app.auth.dependencies import get_current_user
        from app.db.session import get_async_session

        def _unauth():
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        async def _override_session():
            async with pg_session_factory() as s:
                yield s

        app.dependency_overrides[get_current_user] = _unauth
        app.dependency_overrides[get_async_session] = _override_session
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/jobs/{uuid4()}")
                assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()
