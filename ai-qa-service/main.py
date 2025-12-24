"""Minimal FastAPI app placeholder for the AI QA service."""

from __future__ import annotations

import os
from fastapi import FastAPI

SERVICE_NAME = "ai-qa-service"
ASK_PREFIX = "/ask"

app = FastAPI(title="AI QA (Placeholder)", version="0.1.0")


def service_metadata() -> dict:
    return {
        "service": SERVICE_NAME,
        "environment": os.environ.get("ENVIRONMENT", "dev"),
        "query_api_url": os.environ.get("QUERY_API_URL", ""),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", **service_metadata()}


@app.get(f"{ASK_PREFIX}/health")
def ask_health() -> dict:
    return {"status": "ok", **service_metadata()}


@app.get(f"{ASK_PREFIX}/info")
def info() -> dict:
    return {"message": "AI QA placeholder running", **service_metadata()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
