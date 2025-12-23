import json
import logging
from datetime import datetime
from typing import Iterable, List, Optional

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from .config import get_minio_settings
from .logging_utils import log_with_extra

logger = logging.getLogger(__name__)


class MinioClient:
    def __init__(self) -> None:
        settings = get_minio_settings()
        self.bucket = settings.bucket
        self.client: BaseClient = boto3.client(
            "s3",
            endpoint_url=str(settings.endpoint_url),
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            region_name=settings.region,
            use_ssl=settings.secure,
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)
            log_with_extra(logger, logging.INFO, "Created bucket", bucket=self.bucket)

    def upload_json(self, key: str, body: dict, metadata: Optional[dict] = None) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.client.put_object(Bucket=self.bucket, Key=key, Body=payload, Metadata=metadata or {})
        log_with_extra(logger, logging.INFO, "Uploaded object", bucket=self.bucket, key=key)

    def upload_bytes(self, key: str, payload: bytes, metadata: Optional[dict] = None) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=payload, Metadata=metadata or {})
        log_with_extra(logger, logging.INFO, "Uploaded bytes", bucket=self.bucket, key=key)

    def list_prefix(self, prefix: str) -> List[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        keys: List[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        log_with_extra(logger, logging.DEBUG, "Listed prefix", prefix=prefix, count=len(keys))
        return keys

    def download_json(self, key: str) -> dict:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        data = resp["Body"].read()
        return json.loads(data.decode("utf-8"))

    def download_bytes(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def object_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def write_manifest_entry(self, manifest_key: str, processed_key: str) -> None:
        manifest: dict = {"processed": []}
        if self.object_exists(manifest_key):
            manifest = self.download_json(manifest_key)
        manifest.setdefault("processed", []).append({
            "raw_key": processed_key,
            "processed_at": datetime.utcnow().isoformat() + "Z",
        })
        self.upload_json(manifest_key, manifest)

    def list_unprocessed(self, raw_prefix: str, manifest_key: str) -> List[str]:
        keys = self.list_prefix(raw_prefix)
        processed: Iterable[str] = []
        if self.object_exists(manifest_key):
            manifest = self.download_json(manifest_key)
            processed = [entry["raw_key"] for entry in manifest.get("processed", [])]
        pending = [key for key in keys if key not in processed]
        log_with_extra(
            logger,
            logging.INFO,
            "Found unprocessed raw files",
            raw_prefix=raw_prefix,
            pending=len(pending),
        )
        return pending


def get_minio_client() -> MinioClient:
    return MinioClient()
