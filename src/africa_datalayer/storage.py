from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import boto3

from .config import ObjectStoreConfig


class ObjectStore(Protocol):
    """Minimal interface for interacting with object storage."""

    bucket: str

    def put_object(self, key: str, data: bytes, content_type: str | None = None) -> None:
        ...

    def get_object(self, key: str) -> bytes:
        ...


@dataclass(slots=True)
class S3ObjectStore:
    bucket: str
    client: boto3.session.Session.client

    def put_object(self, key: str, data: bytes, content_type: str | None = None) -> None:
        extra_args = {"Bucket": self.bucket, "Key": key, "Body": data}
        if content_type:
            extra_args["ContentType"] = content_type
        self.client.put_object(**extra_args)

    def get_object(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response.get("Body")
        if body is None:
            raise ValueError(f"Object {key} not found in bucket {self.bucket}")
        return body.read()


@dataclass(slots=True)
class LocalObjectStore:
    bucket: str
    base_path: Path

    def _resolve(self, key: str) -> Path:
        path = self.base_path / self.bucket / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put_object(self, key: str, data: bytes, content_type: str | None = None) -> None:  # noqa: ARG002
        path = self._resolve(key)
        path.write_bytes(data)

    def get_object(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Object {key} not found at {path}")
        return path.read_bytes()


def build_object_store(config: ObjectStoreConfig) -> ObjectStore:
    """Factory that returns either an S3-compatible or local object store."""

    if config.local_path is not None:
        return LocalObjectStore(bucket=config.bucket, base_path=config.local_path)

    session = boto3.session.Session(
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        region_name=config.region_name,
    )
    client = session.client("s3", endpoint_url=config.endpoint_url)
    return S3ObjectStore(bucket=config.bucket, client=client)


def write_json(store: ObjectStore, key: str, payload: dict) -> None:
    store.put_object(key, json.dumps(payload, indent=2).encode("utf-8"), content_type="application/json")
