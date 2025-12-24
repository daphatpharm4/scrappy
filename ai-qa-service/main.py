"""FastAPI app for AI QA that proxies intentful questions to the Query API."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field

SERVICE_NAME = "ai-qa-service"
ASK_PREFIX = "/ask"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(SERVICE_NAME)

QUERY_API_URL = os.environ.get("QUERY_API_URL", "").rstrip("/")
QUERY_API_TOKEN = os.environ.get("API_AUTH_TOKEN", "")

app = FastAPI(title="AI QA", version="1.0.0")


class AskRequest(BaseModel):
    """Incoming request to the /ask endpoint."""

    intent: Literal["avg_realestate_price", "count_providers", "list_prices"]
    location: Optional[str] = Field(
        default=None,
        description="Geographic filter such as city, region, or country.",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Optional provider filter for price- or provider-scoped intents.",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of rows to request from the Query API (for list intents).",
    )


class AskResponse(BaseModel):
    """Structured response returned to the client."""

    intent: str
    request_id: str
    answer: Dict[str, Any]
    metadata: Dict[str, Any]


def service_metadata() -> Dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "environment": os.environ.get("ENVIRONMENT", "dev"),
        "query_api_url": QUERY_API_URL,
    }


def _require_query_api_config() -> None:
    if not QUERY_API_URL:
        logger.error("QUERY_API_URL is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Query API URL is not configured.",
        )
    if not QUERY_API_TOKEN:
        logger.error("API_AUTH_TOKEN is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication token is not configured.",
        )


async def _call_query_api(intent: str, payload: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    _require_query_api_config()
    url = f"{QUERY_API_URL}/api/query"
    headers = {"Authorization": f"Bearer {QUERY_API_TOKEN}", "X-Request-ID": request_id}

    logger.info(
        "Dispatching intent to Query API",
        extra={"request_id": request_id, "intent": intent, "url": url, "payload": payload},
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"intent": intent, "payload": payload}, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Query API returned error",
            extra={
                "request_id": request_id,
                "intent": intent,
                "status": exc.response.status_code,
                "response": exc.response.text,
            },
        )
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Query API error: {exc.response.text}",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Failed to reach Query API", extra={"request_id": request_id, "intent": intent})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Query API.",
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        logger.exception("Query API returned non-JSON response", extra={"request_id": request_id, "intent": intent})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Query API returned an invalid response.",
        ) from exc


def _build_payload(ask: AskRequest) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if ask.location:
        payload["location"] = ask.location
    if ask.provider:
        payload["provider"] = ask.provider

    if ask.intent == "list_prices":
        payload["limit"] = ask.limit
    return payload


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", **service_metadata()}


@app.get(f"{ASK_PREFIX}/health")
def ask_health() -> Dict[str, Any]:
    return {"status": "ok", **service_metadata()}


@app.post(ASK_PREFIX, response_model=AskResponse)
async def ask(ask_request: AskRequest, request: Request) -> AskResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    payload = _build_payload(ask_request)

    logger.info(
        "Received /ask request",
        extra={
            "request_id": request_id,
            "intent": ask_request.intent,
            "payload": payload,
            "client": request.client.host if request.client else None,
        },
    )

    query_response = await _call_query_api(ask_request.intent, payload, request_id)

    answer = {
        "intent": ask_request.intent,
        "data": query_response.get("data", query_response),
        "source": query_response.get("source", "query-api"),
    }

    return AskResponse(
        intent=ask_request.intent,
        request_id=request_id,
        answer=answer,
        metadata=service_metadata(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
