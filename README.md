# scrappy

Data lakehouse scaffolding for African data ingestion, validation, and curation.

## Layout
- `src/africa_datalayer/`: Python package with ingestion, cleansing, and storage helpers.
- `configs/example_dataset.yaml`: Example config for the ingestion + cleansing CLI.
- `scripts/`: Command-line entrypoint (exposed as `africa-datalayer`).
- `tests/`: Unit tests validating ingestion, storage, and cleansing behaviors.

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

## Architecture
- A high-level overview of the ingestion and cleansing components, storage layout, and manifests lives in `docs/architecture/overview.md`.

## Documentation
- [African Data Layer PoC Plan](docs/african-data-layer-poc.md)
