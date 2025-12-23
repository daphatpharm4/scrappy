# scrappy

Data lakehouse scaffolding for African data ingestion, validation, and curation.

## Layout
- `src/africa_datalayer/`: Python package with ingestion, cleansing, and storage helpers.
- `configs/example_dataset.yaml`: Example config for the ingestion + cleansing CLI.
- `scripts/`: Command-line entrypoint (exposed as `africa-datalayer`).
- `tests/`: Unit tests validating ingestion, storage, and cleansing behaviors.
- `african-data-layer-poc/`: Dockerized PoC with MinIO, ingestion, cleaning, query, and AI Q&A services.

## Prerequisites
- Python 3.11+ with `pip` and a virtual environment tool (e.g., `venv` or `conda`).
- Network access to download source datasets from the URLs you configure.
- Either:
  - Access to an S3-compatible object store (AWS S3, MinIO, or Supabase object storage) plus a pre-created bucket (default: `africa-datalayer`) and credentials with write permissions, or
  - A local filesystem path where parquet objects and manifests can be written (e.g., `./local_object_store`).

## Create the required resources
1. **Prepare a config file**: Copy `configs/example_dataset.yaml` to a new path (e.g., `configs/my_dataset.yaml`) and set:
   - `dataset`: `country_code`, `dataset`, `ingest_date`, `source_url`, and `source_format` (`csv` or `json`).
   - `object_store`: Either provide S3 connection details (`endpoint_url`, `access_key`, `secret_key`, `region_name`) or uncomment `local_path` to use the filesystem.
2. **Create storage targets**:
   - If using S3/MinIO/Supabase, create the bucket named in your config (`bucket`) before running the pipeline.
   - If using the local filesystem, ensure the directory you reference in `local_path` exists; the CLI will create the bucket prefix beneath it.
3. **Install dependencies** inside an activated virtual environment:
   ```bash
   pip install -e .[dev]
   ```
4. **(Optional) Validate permissions** by running a small test write (e.g., `aws s3 ls s3://<bucket>` for S3 or creating a file under your `local_path`).

## Quickstart
1. Create and activate a Python 3.11+ environment and install dependencies (see **Prerequisites**).
2. Ensure your bucket or local storage path exists (see **Create the required resources**).
3. Update your YAML config with dataset and storage settings.
4. Run the ingestion + cleansing flow locally (writes to your configured object store or `local_object_store/` when `local_path` is set in the config):
   ```bash
   africa-datalayer --config configs/example_dataset.yaml
   ```

## African Data Layer PoC (docker-compose)

```
                             +------------------+
                             |    AI Q&A (8001) |
                             +---------+--------+
                                       |
                                       v
+---------+    ingest raw    +---------+--------+    curated reads    +-----------------+
| sample  | ---------------> | Ingestion Service | ------------------> |   Query API     |
| inputs  |                  +---------+--------+                     |   (DuckDB)      |
| (HTML & |                            |                              +-----------------+
| JSON)   |                            v                                       ^
+---------+                  +---------+--------+                              |
                               Cleaning Service                                 |
                             +---------+--------+                               |
                                       |                                        |
                                       v                                        |
                              +-------------------+                             |
                              |    MinIO          | <---------------------------+
                              | (raw/clean/curated)
                              +-------------------+
```

### Steps
1. Copy the example environment: `cp african-data-layer-poc/.env.example african-data-layer-poc/.env` and adjust secrets/ports.
2. Start everything: `docker compose -f african-data-layer-poc/docker-compose.yml up -d --build`.
3. Bootstrap the bucket/prefixes: `docker compose -f african-data-layer-poc/docker-compose.yml run --rm ingestion-service python /app/scripts/bootstrap_minio.py`.
4. Load sample data: `docker compose -f african-data-layer-poc/docker-compose.yml run --rm ingestion-service python /app/ingestion-service/ingestion_service.py run`.
5. Clean and publish curated Parquet: `docker compose -f african-data-layer-poc/docker-compose.yml run --rm cleaning-service python /app/cleaning-service/cleaning_service.py run`.
6. Query analytics (Bearer token from `.env`):
   ```bash
   curl -H "Authorization: Bearer $SHARED_BEARER_TOKEN" "http://localhost:8000/analytics/average_price?country=kenya"
   ```
7. Ask an NL question:
   ```bash
   curl -X POST -H "Content-Type: application/json" \\
     -d '{"question":"What is the average price of maize in Kenya?","country":"kenya","item":"maize"}' \\
     http://localhost:8001/ask
   ```

### Data flow
- **Ingestion** (FastAPI + CLI): parses bundled HTML/JSON samples for prices, real estate, and providers across Kenya and Cameroon, adds metadata + correlation IDs, and writes raw JSON to `s3://datalake/raw/<domain>/<country>/<timestamp>.json` (via MinIO).
- **Cleaning** (FastAPI + CLI): lists new raw objects, validates to canonical schemas, records manifest state in `curated/manifests/processed_raw_files.json`, and writes JSON + Parquet to `clean/<domain>/<country>/<date>.*`.
- **Query API**: serves authenticated REST endpoints for data retrieval and simple analytics backed by DuckDB reading Parquet from MinIO with an in-memory TTL cache.
- **AI Q&A**: parses intents (avg rent/price, provider counts, item prices), calls the Query API with a shared bearer token, and returns structured JSON answers.

### Demo script
Run the full story (compose up, bootstrap, ingest, clean, curl examples):
```bash
bash african-data-layer-poc/scripts/run_demo.sh
```

## Architecture
- A high-level overview of the ingestion and cleansing components, storage layout, and manifests lives in `docs/architecture/overview.md`.

## Documentation
- [African Data Layer PoC Plan](docs/african-data-layer-poc.md)
