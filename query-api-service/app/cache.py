from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable


class CacheManager:
    def __init__(self, base_dir: str, ttl_seconds: int = 300) -> None:
        self.base_path = Path(base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _key_path(self, key: str) -> Path:
        safe_key = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
        return self.base_path / safe_key

    def path_for_key(self, key: str) -> Path:
        return self._key_path(key)

    def is_fresh(self, key: str) -> bool:
        path = self._key_path(key)
        if not path.exists():
            return False
        age_seconds = time.time() - path.stat().st_mtime
        return age_seconds <= self.ttl_seconds

    def write_bytes(self, key: str, data: bytes) -> Path:
        path = self._key_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def read_bytes(self, key: str) -> bytes:
        return self._key_path(key).read_bytes()

    def write_json(self, key: str, data: Any) -> Path:
        return self.write_bytes(key, json.dumps(data, default=str).encode("utf-8"))

    def read_json(self, key: str) -> Any:
        return json.loads(self.read_bytes(key))

    def get_or_set_json(self, key: str, loader: Callable[[], Any]) -> Any:
        if self.is_fresh(key):
            return self.read_json(key)
        data = loader()
        self.write_json(key, data)
        return data

    def invalidate_if_expired(self, keys: Iterable[str]) -> None:
        for key in keys:
            path = self._key_path(key)
            if path.exists() and not self.is_fresh(key):
                path.unlink(missing_ok=True)
