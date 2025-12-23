FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY african-data-layer-poc/shared /app/shared
COPY african-data-layer-poc/ai-qa-service /app/ai-qa-service
RUN pip install --no-cache-dir fastapi uvicorn[standard] typer boto3 duckdb pandas pyarrow pyyaml requests httpx beautifulsoup4 pydantic
EXPOSE 8001
CMD ["uvicorn", "ai_qa_service:app", "--host", "0.0.0.0", "--port", "8001"]
