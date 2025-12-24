from __future__ import annotations

import os
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="Liveness probe")
def live() -> dict:
    return {"status": "live"}


@router.get("/health/ready", summary="Readiness probe")
def ready() -> dict:
    return {
        "status": "ready",
        "environment": os.environ.get("ENVIRONMENT", "dev"),
        "storage_account": os.environ.get("AZURE_STORAGE_ACCOUNT", ""),
        "blob_container": os.environ.get("BLOB_CONTAINER", ""),
    }
