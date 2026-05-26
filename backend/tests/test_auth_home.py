from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import recovery_tokens, sessions, users
from app.main import app


@pytest.mark.asyncio
async def test_registration_validation_and_duplicate_email(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        invalid = await client.post(
            "/auth/register", json={"name": "", "email": "bad", "password": "short"}
        )
        assert invalid.status_code == 422

        payload = {"name": "Tuli", "email": "tuli@example.com", "password": "password123"}
        created = await client.post("/auth/register", json=payload)
        assert created.status_code == 201
        assert created.json()["user"]["email_verified"] is False

        duplicate = await client.post("/auth/register", json=payload)
        assert duplicate.status_code == 409

    async with session_factory() as session:
        row = (
            await session.execute(select(users).where(users.c.email == "tuli@example.com"))
        ).first()
        assert row is not None
        assert row.email_verified is False
        assert row.password_hash.startswith("$argon2id$")


@pytest.mark.asyncio
async def test_registered_user_can_be_verified_from_fresh_repository_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        created = await repository.create_user("Ada", "ADA@example.com", "password123")

    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        verified = await repository.verify_credentials("ada@example.com", "password123")

    assert verified.id == created.id
    assert verified.email == "ada@example.com"


@pytest.mark.asyncio
async def test_password_recovery_returns_neutral_confirmation() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/recovery/request", json={"email": "missing@example.com"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "Si existe una cuenta" in response.json()["message"]


@pytest.mark.asyncio
async def test_password_recovery_persists_token_for_existing_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            json={"name": "Lin", "email": "lin@example.com", "password": "password123"},
        )
        existing = await client.post(
            "/auth/recovery/request", json={"email": "lin@example.com"}
        )
        missing = await client.post(
            "/auth/recovery/request", json={"email": "missing@example.com"}
        )

    assert existing.status_code == 200
    assert missing.status_code == 200
    assert existing.json() == missing.json()

    async with session_factory() as session:
        rows = (await session.execute(select(recovery_tokens))).all()
        assert len(rows) == 2
        assert sum(row.user_id is not None for row in rows) == 1
        assert all(row.expires_at is not None for row in rows)


@pytest.mark.asyncio
async def test_protected_home_summary_requires_and_accepts_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthorized = await client.get("/home/summary")
        assert unauthorized.status_code == 401

        payload = {"name": "Ada", "email": "ada@example.com", "password": "password123"}
        await client.post("/auth/register", json=payload)
        verified = await client.post(
            "/auth/credentials/verify",
            json={"email": payload["email"], "password": payload["password"]},
        )
        assert verified.status_code == 200
        token = verified.json()["session_token"]

        async with session_factory() as session:
            row = (
                await session.execute(select(sessions).where(sessions.c.session_token == token))
            ).first()
            assert row is not None
            initial_expiration = row.expires

        summary = await client.get("/home/summary", headers={"Authorization": f"Bearer {token}"})
        assert summary.status_code == 200
        assert summary.json()["empty_state"] is True

        session_validation = await client.get(
            "/auth/session", headers={"Authorization": f"Bearer {token}"}
        )
        assert session_validation.status_code == 200
        assert session_validation.json() == {"status": "ok"}

        async with session_factory() as session:
            refreshed = (
                await session.execute(select(sessions).where(sessions.c.session_token == token))
            ).first()
            assert refreshed.expires >= initial_expiration

        logged_out = await client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        assert logged_out.status_code == 200

        invalidated = await client.get(
            "/home/summary", headers={"Authorization": f"Bearer {token}"}
        )
        assert invalidated.status_code == 401

        invalidated_session = await client.get(
            "/auth/session", headers={"Authorization": f"Bearer {token}"}
        )
        assert invalidated_session.status_code == 401

        async with session_factory() as session:
            row = (
                await session.execute(select(sessions).where(sessions.c.session_token == token))
            ).first()
            assert row.invalidated_at is not None


@pytest.mark.asyncio
async def test_expired_persisted_session_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        user = await repository.create_user("Grace", "grace@example.com", "password123")
        session_record = await repository.create_session(
            user.id,
            idle_ttl=timedelta(seconds=-1),
            absolute_ttl=timedelta(days=1),
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/home/summary", headers={"Authorization": f"Bearer {session_record.token}"}
        )

    assert response.status_code == 401
