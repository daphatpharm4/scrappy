# scrappy

Data lakehouse scaffolding for African data ingestion, validation, and curation.

## Layout
- `src/africa_datalayer/`: Python package with ingestion, cleansing, and storage helpers.
- `configs/example_dataset.yaml`: Example config for the ingestion + cleansing CLI.
- `scripts/`: Command-line entrypoint (exposed as `africa-datalayer`).
- `tests/`: Unit tests validating ingestion, storage, and cleansing behaviors.

## Quickstart
1. Create and activate a Python 3.11+ environment and install dependencies:
   ```bash
   pip install -e .[dev]
   ```
2. Update `configs/example_dataset.yaml` with your dataset and storage settings.
3. Run the ingestion + cleansing flow locally (writes to `local_object_store/` when `local_path` is set in the config):
   ```bash
   africa-datalayer --config configs/example_dataset.yaml
   ```

## Documentation
- [African Data Layer PoC Plan](docs/african-data-layer-poc.md)
