# Architecture Overview

This project ingests country datasets into a data lakehouse with a clear raw → cleansed flow and lightweight metadata.

## Components
- **CLI (`africa-datalayer`)**: Orchestrates ingestion and cleansing from a YAML config.
- **Pipelines**
  - `pipelines.ingest`: Downloads source CSV/JSON, normalizes columns, adds partition columns (`country`, `ingest_date`), and writes Parquet + a manifest to `raw/`.
  - `pipelines.cleanse`: Validates data (Pandera), standardizes columns, and writes Parquet + a manifest to `cleansed/`.
- **Storage abstraction**: `storage.ObjectStore` with S3-compatible and local filesystem implementations.
- **Schemas**: Pandera schema for economic indicators; can be extended for new datasets.

## Storage layout
```
<bucket>/
  raw/<country>/<dataset>/<ingest_date>/data.parquet
  raw/<country>/<dataset>/<ingest_date>/manifest.json
  cleansed/<country>/<dataset>/ingest_date=<ingest_date>/data.parquet
  cleansed/<country>/<dataset>/ingest_date=<ingest_date>/manifest.json
```

## Manifests
- **Raw manifest**: Checksums of source and parquet, row count, column names, dataset metadata, and prefixes used.
- **Cleansed manifest**: Row count, columns, and partition info (`country`, `ingest_date`).

## Prerequisite resources
- S3-compatible bucket (or local path) created ahead of time; the CLI will write objects beneath the bucket.
- Network reachability to source URLs defined in your YAML config.

## Extending the system
- Add new datasets by creating a config YAML, customizing schemas in `pipelines.cleanse`, and plugging in new fetchers or validators as needed.
