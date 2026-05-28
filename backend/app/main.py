from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.assistant import router as assistant_router
from app.api.auth import router as auth_router
from app.api.home import router as home_router
from app.api.identifications import router as identifications_router
from app.api.profile_garden import router as profile_garden_router
from app.api.reminders import router as reminders_router
from app.core.settings import get_settings
from app.observability.logging import configure_logging
from app.observability.metrics import metrics_registry
from app.observability.middleware import request_observability_middleware
from app.providers.factory import get_provider_registry


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.middleware("http")(request_observability_middleware)
    app.include_router(auth_router)
    app.include_router(home_router)
    app.include_router(identifications_router)
    app.include_router(profile_garden_router)
    app.include_router(assistant_router)
    app.include_router(reminders_router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, object]:
        providers = get_provider_registry()
        return {
            "status": "ok",
            "environment": settings.environment,
            "dependencies": {
                "database": "configured" if settings.database_url else "missing",
                "vector_store": "configured",
                "object_storage": "configured" if settings.object_storage_bucket else "missing",
                "model_provider": providers.model.__class__.__name__,
                "vision_provider": providers.vision.__class__.__name__,
                "embedding_provider": providers.embeddings.__class__.__name__,
                "search_provider": providers.search.__class__.__name__,
            },
        }

    @app.get("/metrics", tags=["system"])
    async def metrics() -> Response:
        return Response(content=metrics_registry.to_prometheus(), media_type="text/plain")

    return app


app = create_app()
