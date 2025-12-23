# African Data Layer PoC → Implementation Tasks & Code Samples

This plan operationalizes the architecture for a pan-African data lakehouse starting with Kenya and Cameroon, using cost-efficient object storage (Supabase Analytics Buckets or MinIO), Apache Iceberg tables, and a query layer (Trino or DuckDB). It emphasizes raw → cleansed → curated zones and an NL-to-SQL interface for public and private clients.

## Scope & Assumptions
- Initial geos: Kenya, Cameroon. Datasets: open government data, mobile/utility CSVs, geospatial (GeoJSON/Parquet), and streaming telemetry (optional).
- Storage: S3-compatible (Supabase Analytics Buckets or MinIO). Catalog: Hive/REST for Iceberg.
- Processing: Python + DuckDB for lightweight ELT; Trino for federated/serving; optional dbt for transforms.
- Security: Per-tenant buckets/prefixes, row/column-level masking in curated zone.

## Phase Breakdown (first 6 months)
- **Month 0–1: Foundations**
  - Stand up object storage (MinIO or Supabase Analytics Buckets) with three prefixes: `raw/`, `cleansed/`, `curated/`.
  - Deploy catalog (Hive/Glue-compatible) and Trino; enable Iceberg connector.
  - Set up CI for data contracts/schema checks (Great Expectations or Pandera) and basic dbt project skeleton.
- **Month 1–2: Ingestion & Staging**
  - Build ingestion jobs for Kenya Open Data + Cameroon datasets (CSV/JSON/GeoJSON to Parquet in `raw/`).
  - Add checksum & source metadata manifests per batch.
  - Automate partitioning by `ingest_date` and `country`.
- **Month 2–3: Cleaning & Standardization**
  - Add cleansing jobs to standardize column names, types, currencies, and geos (ISO-3166, ISO-4217).
  - Validate with expectations; write to Iceberg tables in `cleansed/`.
- **Month 3–4: Curation & Serving**
  - Publish curated, denormalized tables (e.g., `country_stats_daily`) with SCD Type 2 for slowly changing dims.
  - Expose via Trino and materialized DuckDB artifacts for lightweight dashboards.
- **Month 4–6: NL-to-SQL & Monetization**
  - Ship NL interface (LLM + SQL guardrails) against curated schema.
  - Package monetization surfaces: REST/GraphQL APIs, dashboards, and dataset downloads with usage metering.

## Zone Layout
```
s3://africa-datalayer/
  raw/<country>/<dataset>/<ingest_date>/...         # Source dumps (CSV/JSON/GeoJSON/Parquet)
  cleansed/<country>/<dataset>/ingest_date=<date>/   # Typed/validated Parquet
  curated/<subject>/<table>/dt=<date>/               # Iceberg-managed tables for serving
```

## Implementation Backlog (actionable)
1) **Storage & Catalog**
   - Provision MinIO/Supabase bucket and create service accounts with scoped access.
   - Deploy Iceberg catalog (e.g., Hive Metastore + MySQL/Postgres) reachable by Trino and Python jobs.
2) **Ingestion Pipelines**
   - Author Python jobs to fetch CSV/JSON/GeoJSON, convert to Parquet, and upload to `raw/`.
   - Add metadata manifests (checksum, source URL, schema, row counts).
3) **Validation & Cleansing**
   - Apply expectations (Great Expectations or Pandera) to standardize schema and drop/flag bad rows.
   - Write cleansed outputs as Iceberg tables partitioned by `ingest_date`, `country`.
4) **Curation**
   - Build dbt/SQL models for curated facts and dims (population, economic indicators, geospatial grids).
   - Implement SCD2 for reference data; enforce PII redaction/masking where needed.
5) **Query Layer**
   - Configure Trino catalogs for Iceberg and object storage; enable columnar cache.
   - Publish DuckDB artifacts for embedded analytics or offline notebooks.
6) **NL-to-SQL Interface**
   - Build a schema registry (JSON) and prompts/tooling to translate NL → SQL with guardrails (schema-constrained decoding + EXPLAIN validation).
7) **Monetization & Delivery**
   - REST/GraphQL APIs for curated tables (pagination, filtering).
   - Dashboard templates (e.g., Superset/Metabase) and signed URL downloads with quotas.

## Code Samples

### 1) Python ingestion → Parquet → MinIO/Supabase
```python
import io
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
import boto3

SOURCE_URL = "https://data.go.ke/api/.../export?format=csv"
BUCKET = "africa-datalayer"
RAW_PREFIX = "raw/kenya/economic_indicators/2024-09-30/"

s3 = boto3.client(
    "s3",
    endpoint_url="https://minio.example.com",  # or Supabase object API endpoint
    aws_access_key_id="MINIO_KEY",
    aws_secret_access_key="MINIO_SECRET",
)

resp = requests.get(SOURCE_URL, timeout=30)
resp.raise_for_status()

df = pd.read_csv(io.BytesIO(resp.content))
df["country"] = "KEN"
df["ingest_date"] = "2024-09-30"

table = pa.Table.from_pandas(df)
buf = io.BytesIO()
pq.write_table(table, buf, compression="zstd")

s3.put_object(Bucket=BUCKET, Key=f"{RAW_PREFIX}data.parquet", Body=buf.getvalue())
```

### 2) Validation & Cleansing (Pandera + DuckDB)
```python
import duckdb
import pandera as pa
from pandera.typing import DataFrame, Series

class EconSchema(pa.SchemaModel):
    country: Series[str] = pa.Field(isin=["KEN", "CMR"])
    indicator: Series[str]
    value: Series[float] = pa.Field(ge=0)
    year: Series[int] = pa.Field(ge=1960)
    ingest_date: Series[str]

conn = duckdb.connect()
df = conn.read_parquet("s3://africa-datalayer/raw/kenya/economic_indicators/2024-09-30/data.parquet").df()
validated: DataFrame[EconSchema] = EconSchema.validate(df)

conn.execute("""
    COPY (SELECT * FROM validated) TO
      's3://africa-datalayer/cleansed/kenya/economic_indicators/ingest_date=2024-09-30/data.parquet'
      (FORMAT PARQUET, COMPRESSION ZSTD);
""")
```

### 3) Iceberg table creation (Trino)
```sql
CREATE TABLE lake.cleansed.economic_indicators (
  country VARCHAR,
  indicator VARCHAR,
  value DOUBLE,
  year INTEGER,
  ingest_date DATE
)
WITH (
  format = 'PARQUET',
  partitioning = ARRAY['country', 'years(ingest_date)']
);
```

### 4) Curated view for serving (Trino)
```sql
CREATE TABLE lake.curated.country_stats_daily AS
SELECT
  country,
  indicator,
  date_parse(date_str, '%Y-%m-%d') AS dt,
  avg(value) AS avg_value
FROM lake.cleansed.economic_indicators
GROUP BY 1,2,3;
```

### 5) NL-to-SQL service skeleton (Python, FastAPI + Trino)
```python
from fastapi import FastAPI
import trino

app = FastAPI()
conn = trino.dbapi.connect(
    host="trino.service",
    port=8080,
    user="nl_service",
    catalog="lake",
    schema="curated",
)

# Assume generate_sql(question, schema_json) produces a vetted SQL string.
@app.get("/ask")
def ask(question: str):
    sql = generate_sql(question, schema_json=load_schema())
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    return {"sql": sql, "rows": rows}
```

## Data Quality & Governance Guardrails
- Mandatory metadata: source URL, checksum, ingest timestamp, country, schema version.
- Expectations on cleansed tables; fail/alert on drift or nullability changes.
- Row-level filters by tenant; column masking for sensitive fields before curated exposure.
- Audit logs: object access + query logs (Trino) shipped to centralized logging.

## Observability & Ops
- Metrics: ingestion latency, row counts, validation failures, cost per TB scanned.
- Alerting on: schema drift, missing partitions, NL-to-SQL rejection rates, Trino CPU/queue depth.
- Backups: versioned buckets + periodic catalog backups; disaster recovery via cross-region replication.

## Monetization Paths
- APIs: rate-limited endpoints with API keys; tiered quotas.
- Dashboards: templated Superset/Metabase pointing at curated tables.
- Downloads: signed URLs with per-tenant prefixes and billing hooks.
