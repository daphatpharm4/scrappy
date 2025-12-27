# Codebase Reference (File-by-File)

This document gives new contributors a quick, concrete tour of the repository. It lists every major file and explains what it does, how it fits into the overall flow, and any important environment variables or behaviors to know.

## Root layout
- `README.md`: Deployment-focused overview for running everything on AKS, including the required Azure resources, sequence of helper scripts, and ingress/testing hints.
- `Makefile`: Convenience targets for infrastructure steps and image workflows (mirrors the scripts listed in the README).
- `configs/datasets.yaml`: Example dataset definitions consumed by the pipeline runner; shows fetch URLs, retry policy, schema expectations, and run modes.
- `docs/architecture/overview.md`: High-level lakehouse design (raw → cleansed), manifest format, and how to extend with new datasets.
- `k8s/` and `infra/`: Helm values and Terraform scaffolding used by the helper scripts to provision Azure resources and deploy the services.
- `scripts/00_prereqs_check.sh` … `scripts/99_destroy.sh`: Ordered shell scripts that check prerequisites, bootstrap Azure login, provision infra, build/push images, connect kubectl, install CSI/Workload Identity, deploy apps, validate, and clean up.
- `pyproject.toml`: Shared development dependencies and tools for the repository.

## Query API service (`query-api-service/`)
Purpose: Serve filtered and aggregated dataset slices from Parquet via FastAPI with bearer authentication and simple disk caching.

- `main.py`: Builds the FastAPI app, injects shared `Settings`, mounts routers under the configured API prefix, and exposes `/health` plus liveness/readiness endpoints.
- `Dockerfile`: Minimal image that installs service dependencies and runs `uvicorn`.
- `requirements.txt`: Python dependencies (FastAPI, Polars, Azure SDK, etc.).
- `app/config.py`: Pydantic `Settings` for API prefix, environment, Azure IDs, Key Vault name, blob prefixes, cache directory/TTL, and optional local data base path; values are pulled from env vars with sensible defaults.
- `app/auth.py`: `TokenProvider` that fetches and caches the bearer token (fallback from env or live from Key Vault using `DefaultAzureCredential`); raises FastAPI HTTP errors on missing/invalid tokens. `require_auth` is a dependency used on protected routes.
- `app/cache.py`: `CacheManager` that normalizes cache keys, writes/reads bytes or JSON to disk, checks TTL freshness, and invalidates expired entries.
- `app/data.py`: `DataRepository` that:
  - Resolves dataset paths (local or remote URL fallback) and caches Parquet bytes.
  - Lists Parquet files per dataset and scans them lazily with Polars.
  - Applies common filters (provider, country, region, date range, limit) and query-specific filters (price ranges, bedrooms).
  - Aggregates provider metrics (avg/total/count) and lists providers; raises `DataAccessError` for missing data or metrics.
- `app/models.py`: Pydantic request models with normalization and validation rules:
  - `BaseDataQuery` (provider/country/region/date range/limit),
  - `PriceQuery` (min/max price consistency),
  - `RealEstateQuery` (min/max bedrooms consistency),
  - `AnalyticsQuery` (metric selection).
- Routers (all use dependency-injected `DataRepository`, auth on data/analytics routes):
  - `app/routers/health.py`: `/health/live` and `/health/ready` probes with environment/storage metadata.
  - `app/routers/prices.py`: `/data/prices` returns filtered price records.
  - `app/routers/realestate.py`: `/data/realestate` returns filtered listings.
  - `app/routers/providers.py`: `/data/providers` lists distinct providers.
  - `app/routers/analytics.py`: `/analytics/provider-summary` aggregates metrics per provider with guarded error translation.
- `tests/`: Pytest suite covering token retrieval/caching, cache TTL behavior, dataset filtering/aggregation, provider listing, and router auth/health endpoints via a test client seeded with Parquet fixtures.

## AI QA service (`ai-qa-service/`)
Purpose: Expose an `/ask` endpoint that forwards intentful questions to the Query API and rewraps the response.

- `main.py`: FastAPI app defining:
  - Configuration from `QUERY_API_URL` and `API_AUTH_TOKEN` env vars (returns 503 if missing).
  - `AskRequest` with allowed intents (`avg_realestate_price`, `count_providers`, `list_prices`), optional location/provider, and a capped limit for list intents.
  - `_build_payload` to forward only relevant fields.
  - `_call_query_api` that POSTs to `QUERY_API_URL/api/query` with bearer auth, logs dispatch, and surfaces HTTP/JSON errors as FastAPI exceptions.
  - `/health` and `/ask/health` endpoints returning service metadata.
  - `/ask` endpoint that assigns/propagates `X-Request-ID`, logs the request, calls the Query API, and returns `AskResponse` with intent, data, source, and metadata.
- `Dockerfile` / `requirements.txt`: Image and dependency pins for the service.

## Scraper service (`scraper-service/`)
Purpose: Periodically scrape target URLs, extract lead details via an LLM provider, and write results as JSON/CSV/Markdown.

- `app/main.py`:
  - Target loading: Reads `SCRAPER_CONFIG` (file path or inline content) and supports YAML/JSON lists or newline/comma-separated values.
  - Proxy rotation: Builds a proxy pool from `HTTP_PROXY`/`HTTPS_PROXY` env vars and selects a proxy per URL.
  - API keys: Reads provider keys for OpenAI/DeepSeek/xAI; `SCRAPER_MODEL_PROVIDER` chooses the provider.
  - Prompting and model calls: Builds a structured prompt, posts to the provider-specific chat-completions endpoint, logs failures, and parses JSON-like responses into `name/email/phone/personalization`.
  - HTML fetching: Uses Playwright (Chromium) with optional proxy to render pages and return HTML.
  - Orchestration: `process_url` handles scrape + model call with structured logging; `run` loads targets, checks key availability, runs concurrent tasks with `aiohttp`, collects non-null leads, and writes outputs to `/data/out` (`leads.json`, `leads.md`, `leads.csv`).
- `Dockerfile` / `requirements.txt`: Image and dependency pins, including Playwright runtime.

## Pipeline runner CLI (`src/africa_datalayer/`)
Purpose: CLI for ingesting datasets from YAML config, applying schema hints, and writing raw/clean/curated artifacts to Azure Blob Storage with manifests.

- `scripts/ingest_and_cleanse.py`:
  - CLI: Typer command `ingest-and-cleanse` with options for config path, run mode (`batch/backfill/dev/any`), and log level.
  - Config parsing: Typed dataclasses for retry policy, fetch method/format/headers/params, schema fields, and dataset metadata (domain/country/source/run_mode).
  - Azure setup: Builds `BlobServiceClient` with `DefaultAzureCredential`; uploads blobs with content types.
  - Fetching: `_fetch_bytes` performs HTTP requests with exponential backoff and raises on repeated failure.
  - Processing: Reads CSV/JSON into pandas, applies schema casts/defaults, adds metadata columns, derives deterministic `record_id`, and writes compressed Parquet.
  - Manifests: Writes raw, clean, and curated manifests/quality reports with checksums, row counts, and partition info; organizes under prefixes (`BLOB_PREFIX_RAW/CLEAN/CURATED`).
- `__init__.py`: Package marker for the CLI module.

## Scripts and infrastructure helpers
- `scripts/*.sh`: Shell entrypoints used by the README/Makefile to provision, deploy, validate, and tear down Azure resources.
- `k8s/env/values-dev.yaml`: Helm values for images, ingress host/TLS, Key Vault secret names, workload identity client IDs, and scraper settings.
- `infra/terraform/env/dev.tfvars`: Terraform variables for resource naming, sizing, and region; aligns with the Helm values.
- `pipeline-runner/pyproject.toml`: Build metadata for the pipeline runner package and its console script entrypoint (`africa-datalayer`).

## How the parts connect
1) Pipeline runner ingests sources → writes raw/clean/curated Parquet + manifests to Azure Blob.  
2) Query API reads cleaned Parquet (local path or remote URL cached locally) → serves filtered records, provider lists, and provider aggregates behind bearer auth.  
3) AI QA service accepts `/ask` requests → forwards intent + filters to Query API → returns structured answers with request IDs.  
4) Scraper service can run on a schedule → fetches HTML, calls an LLM provider for lead extraction → writes leads artifacts usable by downstream analytics or ingestion.
