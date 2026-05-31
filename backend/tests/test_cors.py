import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, create_app


ORIGIN = "http://localhost:3000"


@pytest.mark.asyncio
async def test_auth_register_preflight_allows_frontend_origin() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/auth/register",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]


@pytest.mark.asyncio
async def test_unhandled_error_response_keeps_cors_headers() -> None:
    test_app = create_app()

    @test_app.get("/cors-error")
    async def cors_error() -> None:
        raise RuntimeError("forced failure")

    async with AsyncClient(
        transport=ASGITransport(app=test_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/cors-error", headers={"Origin": ORIGIN})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
