from __future__ import annotations

import hashlib
from typing import Iterable


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_many(parts: Iterable[bytes]) -> str:
    digest = hashlib.sha256()
    for chunk in parts:
        digest.update(chunk)
    return digest.hexdigest()
