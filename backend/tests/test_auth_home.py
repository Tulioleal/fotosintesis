import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_registration_validation_and_duplicate_email() -> None:
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


@pytest.mark.asyncio
async def test_password_recovery_returns_neutral_confirmation() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/recovery/request", json={"email": "missing@example.com"})
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "Si existe una cuenta" in response.json()["message"]


@pytest.mark.asyncio
async def test_protected_home_summary_requires_and_accepts_session() -> None:
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

        summary = await client.get("/home/summary", headers={"Authorization": f"Bearer {token}"})
        assert summary.status_code == 200
        assert summary.json()["empty_state"] is True
