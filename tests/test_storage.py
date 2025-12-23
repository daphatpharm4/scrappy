from __future__ import annotations

from africa_datalayer.storage import LocalObjectStore


def test_local_object_store_roundtrip(tmp_path):
    store = LocalObjectStore(bucket="test-bucket", base_path=tmp_path)
    store.put_object("raw/sample/data.txt", b"hello")

    payload = store.get_object("raw/sample/data.txt")
    assert payload == b"hello"
