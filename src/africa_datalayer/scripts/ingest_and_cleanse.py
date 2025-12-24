"""Placeholder ingest-and-cleanse pipeline entrypoint.

This keeps the CronJob runnable by providing a lightweight, no-op pipeline that
logs the datasets it would process.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import typer
import yaml

app = typer.Typer(help="Africa Data Layer pipeline runner (placeholder)")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _load_datasets(config_path: Path) -> List[Dict[str, Any]]:
    if not config_path.exists():
        logger.warning("Config file not found at %s; nothing to ingest", config_path)
        return []

    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    datasets = raw.get("datasets", [])
    if not isinstance(datasets, list):
        logger.warning("Config file at %s missing 'datasets' list", config_path)
        return []

    return [d for d in datasets if isinstance(d, dict)]


@app.command("ingest-and-cleanse")
def ingest_and_cleanse(
    config: Path = typer.Option(
        Path("configs/datasets.yaml"),
        "--config",
        "-c",
        help="Path to datasets config file.",
    ),
) -> None:
    """Run a no-op ingest-and-cleanse pipeline."""
    datasets = _load_datasets(config)
    logger.info("Starting placeholder ingest-and-cleanse run")
    logger.info("Datasets config path: %s", config.resolve())

    if not datasets:
        logger.info("No datasets defined; exiting early")
        return

    for dataset in datasets:
        name = dataset.get("name", "<unnamed>")
        source = dataset.get("source", "unknown")
        logger.info(
            "Would process dataset '%s' from source '%s': %s",
            name,
            source,
            json.dumps(dataset),
        )

    logger.info("Placeholder pipeline run completed successfully")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
