import logging
import sys
from pathlib import Path
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from shared.config import get_ai_qa_settings  # noqa: E402
from shared.logging_utils import set_correlation_id, setup_logging  # noqa: E402
from shared.models import AIAnswer, HealthResponse  # noqa: E402

logger = logging.getLogger(__name__)
app = FastAPI(title="AI Q&A Service")
setup_logging()


class Question(BaseModel):
    question: str
    country: Optional[str] = None
    item: Optional[str] = None


INTENTS = {
    "average_rent": ["average rent", "avg rent", "rent average"],
    "average_price": ["average price", "avg price", "price average"],
    "provider_counts": ["provider count", "providers", "how many providers"],
    "item_prices": ["price for", "cost of", "item price"],
}


def parse_intent(text: str) -> str:
    lower = text.lower()
    for intent, keywords in INTENTS.items():
        for word in keywords:
            if word in lower:
                return intent
    return "item_prices"


def query_api(path: str, params: Dict[str, str | int | None]) -> Dict:
    settings = get_ai_qa_settings()
    headers = {"Authorization": f"Bearer {settings.shared_token}"}
    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
        resp = client.get(f"{settings.query_api_url}{path}", headers=headers, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_ai_qa_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.version,
        environment=settings.environment,
    )


@app.post("/ask", response_model=AIAnswer)
async def ask(question: Question) -> AIAnswer:
    set_correlation_id()
    intent = parse_intent(question.question)
    settings = get_ai_qa_settings()

    if intent == "average_rent":
        data = query_api("/analytics/average_price", {"country": question.country, "item": "rent"})
        answer = f"Average rent in {question.country or 'all countries'} is {data['value']:.2f}."
        return AIAnswer(intent=intent, params=question.model_dump(), answer=answer, data=[data])

    if intent == "average_price":
        data = query_api("/analytics/average_price", {"country": question.country, "item": question.item})
        label = question.item or "items"
        answer = f"Average price for {label} in {question.country or 'all countries'} is {data['value']:.2f}."
        return AIAnswer(intent=intent, params=question.model_dump(), answer=answer, data=[data])

    if intent == "provider_counts":
        data = query_api("/analytics/provider_counts", {"country": question.country})
        answer = f"Found {data['value']} providers in {question.country or 'all countries'}."
        return AIAnswer(intent=intent, params=question.model_dump(), answer=answer, data=[data])

    # item_prices
    params = {"country": question.country, "item": question.item, "page_size": 20}
    data = query_api("/data/prices", params)
    sample = data.get("data", [])
    answer = f"Found {len(sample)} price records for {question.item or 'items'} in {question.country or 'all countries'}."
    return AIAnswer(intent=intent, params=question.model_dump(), answer=answer, data=sample)


if __name__ == "__main__":
    setup_logging()
    import uvicorn

    settings = get_ai_qa_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
