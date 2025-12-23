"""Bootstrap MinIO bucket and prefixes for the PoC."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from shared.logging_utils import setup_logging
from shared.minio_client import get_minio_client


PREFIXES = [
    "raw/prices/",
    "raw/realestate/",
    "raw/providers/",
    "clean/prices/",
    "clean/realestate/",
    "clean/providers/",
    "curated/manifests/",
]


def main() -> None:
    setup_logging()
    client = get_minio_client()
    client.ensure_bucket()
    for prefix in PREFIXES:
        key = f"{prefix}.keep"
        client.upload_bytes(key, b"bootstrap")


if __name__ == "__main__":
    main()
