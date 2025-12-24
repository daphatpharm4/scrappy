FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pipeline-runner/pyproject.toml ./pyproject.toml
COPY README.md ./README.md
COPY src ./src

RUN pip install --no-cache-dir .

ENTRYPOINT ["africa-datalayer"]
CMD ["ingest-and-cleanse", "--config", "/configs/datasets.yaml"]
