"""Tests for the object storage factory selection."""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

from app.core.settings import Settings
from app.storage.factory import build_object_storage
from app.storage.gcs import GCSObjectStorage
from app.storage.local import LocalObjectStorage


def _settings(
    provider: str,
    bucket: str = "fotosintesis-test",
    local_root: str = "storage-data",
    gcp_project_id: str | None = None,
) -> Settings:
    # Disable the .env file loader so the test only sees the explicit values.
    return Settings(_env_file=None, _env_file_encoding="utf-8",
        object_storage_provider=provider,
        object_storage_bucket=bucket,
        object_storage_local_root=local_root,
        gcp_project_id=gcp_project_id,
    )


def test_factory_returns_local_storage_for_local_provider(tmp_path: Path) -> None:
    settings = _settings("local", local_root=str(tmp_path))
    storage = build_object_storage(settings)
    assert isinstance(storage, LocalObjectStorage)
    assert storage.bucket == "fotosintesis-test"
    assert storage.root == tmp_path


def test_factory_returns_gcs_storage_for_gcs_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_storage_module = types.ModuleType("google.cloud.storage")
    fake_client = types.SimpleNamespace()
    fake_storage_module.Client = fake_client
    fake_cloud_module = types.ModuleType("google.cloud")
    fake_cloud_module.storage = fake_storage_module
    fake_google_module = sys.modules.get("google") or types.ModuleType("google")
    fake_google_module.cloud = fake_cloud_module

    monkeypatch.setitem(sys.modules, "google", fake_google_module)
    monkeypatch.setitem(sys.modules, "google.cloud", fake_cloud_module)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", fake_storage_module)

    settings = _settings("gcs", bucket="fotosintesis-prod-storage", gcp_project_id="prod-project")
    storage = build_object_storage(settings)
    assert isinstance(storage, GCSObjectStorage)
    assert storage.bucket == "fotosintesis-prod-storage"


def test_factory_raises_for_unknown_provider() -> None:
    settings = _settings("s3")
    with pytest.raises(ValueError) as exc_info:
        build_object_storage(settings)
    assert "OBJECT_STORAGE_PROVIDER" in str(exc_info.value)


def test_factory_normalises_provider_case() -> None:
    settings = _settings("LOCAL")
    storage = build_object_storage(settings)
    assert isinstance(storage, LocalObjectStorage)


def test_local_storage_writes_under_root(tmp_path: Path) -> None:
    from app.storage.models import ObjectUpload

    settings = _settings("local", bucket="buc", local_root=str(tmp_path))
    storage = build_object_storage(settings)
    assert isinstance(storage, LocalObjectStorage)

    payload = ObjectUpload(path="identifications/test.jpg", content=b"hello", mime_type="image/jpeg")
    stored = asyncio.run(storage.put_object(payload))
    assert stored.bucket == "buc"
    assert stored.path == "identifications/test.jpg"
    assert (tmp_path / "buc" / "identifications" / "test.jpg").read_bytes() == b"hello"
