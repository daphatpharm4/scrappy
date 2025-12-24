from __future__ import annotations

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.dependencies import get_settings as settings_dependency
from app.routers import analytics, health, prices, providers, realestate

SERVICE_NAME = "query-api-service"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Query API", version="1.0.0")

    # Allow tests to override the shared settings dependency.
    app.dependency_overrides[settings_dependency] = lambda: settings

    app.include_router(health.router)
    app.include_router(prices.router, prefix=settings.api_prefix)
    app.include_router(realestate.router, prefix=settings.api_prefix)
    app.include_router(providers.router, prefix=settings.api_prefix)
    app.include_router(analytics.router, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    def root_health() -> dict:
        return {"status": "ok", "service": SERVICE_NAME, "environment": settings.environment}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
