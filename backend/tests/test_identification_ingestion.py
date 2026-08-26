"""Hardened image ingestion: rejection, normalization, and compensation."""

from __future__ import annotations

import io
import types
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.settings import get_settings
from app.identification.image_processing import (
    ImageRejectionCategory,
    ImageValidationError,
    normalize_identification_image,
)
from app.identification.repository import IdentificationRepository
from app.main import app
from app.storage.models import StoredObject
from tests._image_helpers import (
    JPEG_BYTES,
    PNG_BYTES,
    WEBP_BYTES,
    make_image_bytes,
    make_image_with_orientation,
)


def _bmp_bytes() -> bytes:
    image = Image.new("RGB", (30, 20), "blue")
    buffer = io.BytesIO()
    image.save(buffer, format="BMP")
    return buffer.getvalue()


def _truncated_image() -> bytes:
    return PNG_BYTES[: len(PNG_BYTES) // 2]


class TestNormalizeRejections:
    def test_empty_bytes_rejected(self) -> None:
        with pytest.raises(ImageValidationError) as exc:
            normalize_identification_image(b"")
        assert exc.value.category == ImageRejectionCategory.EMPTY

    def test_corrupt_bytes_rejected(self) -> None:
        with pytest.raises(ImageValidationError) as exc:
            normalize_identification_image(b"this is definitely not an image")
        assert exc.value.category == ImageRejectionCategory.CORRUPT

    def test_truncated_image_rejected(self) -> None:
        with pytest.raises(ImageValidationError) as exc:
            normalize_identification_image(_truncated_image())
        assert exc.value.category == ImageRejectionCategory.CORRUPT

    def test_unsupported_format_rejected(self) -> None:
        with pytest.raises(ImageValidationError) as exc:
            normalize_identification_image(_bmp_bytes())
        assert exc.value.category == ImageRejectionCategory.UNSUPPORTED_FORMAT

    def test_oversized_dimensions_rejected_even_when_small_compressed(self) -> None:
        big = make_image_bytes("JPEG", size=(12000, 10))
        assert len(big) < 4096
        with pytest.raises(ImageValidationError) as exc:
            normalize_identification_image(big)
        assert exc.value.category == ImageRejectionCategory.DIMENSIONS_EXCEEDED

    def test_oversized_pixels_rejected_before_storage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IDENTIFICATION_MAX_IMAGE_PIXELS", "5000")
        get_settings.cache_clear()
        try:
            with pytest.raises(ImageValidationError) as exc:
                normalize_identification_image(make_image_bytes("PNG", size=(80, 80)))
            assert exc.value.category == ImageRejectionCategory.PIXELS_EXCEEDED
        finally:
            get_settings.cache_clear()

    def test_decompression_bomb_rejected_before_storage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("IDENTIFICATION_MAX_IMAGE_PIXELS", "5000")
        get_settings.cache_clear()
        try:
            with pytest.raises(ImageValidationError) as exc:
                normalize_identification_image(make_image_bytes("PNG", size=(200, 200)))
            assert exc.value.category == ImageRejectionCategory.DECOMPRESSION_BOMB
        finally:
            get_settings.cache_clear()


class TestNormalizeSuccess:
    def test_valid_formats_normalize_to_jpeg(self) -> None:
        for raw in (JPEG_BYTES, PNG_BYTES, WEBP_BYTES):
            result = normalize_identification_image(raw)
            assert result.mime_type == "image/jpeg"
            with Image.open(io.BytesIO(result.content)) as img:
                assert img.format == "JPEG"
                assert img.mode == "RGB"

    def test_orientation_applied_and_exif_stripped(self) -> None:
        oriented = make_image_with_orientation(size=(30, 20))
        result = normalize_identification_image(oriented)
        # orientation=6 transposes 30x20 -> 20x30
        assert (result.width, result.height) == (20, 30)
        with Image.open(io.BytesIO(result.content)) as img:
            assert img.getexif() == {}
            assert img.size == (20, 30)


def _fake_storage() -> types.SimpleNamespace:
    class FakeStorage:
        def __init__(self) -> None:
            self.puts: list[str] = []
            self.deletes: list[str] = []

        async def put_object(self, upload) -> StoredObject:
            self.puts.append(upload.path)
            return StoredObject(
                bucket="test",
                path=upload.path,
                mime_type=upload.mime_type,
                size_bytes=len(upload.content),
                created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )

        async def delete_object(self, path: str) -> None:
            self.deletes.append(path)

    return FakeStorage()


async def _authed_client() -> tuple[AsyncClient, str]:
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    payload = {"name": "Img", "email": f"img-{uuid4().hex}@example.com", "password": "password123"}
    await client.post("/auth/register", json=payload)
    verified = await client.post("/auth/credentials/verify", json=payload)
    token = verified.json()["session_token"]
    return client, token


@pytest.mark.asyncio
async def test_declared_mime_mismatch_rejected_before_object_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _fake_storage()
    monkeypatch.setattr("app.api.identifications.get_object_storage", lambda: storage)

    client, token = await _authed_client()
    try:
        # Declared JPEG, but bytes are a BMP: supported declared type, unsupported bytes.
        response = await client.post(
            "/identifications",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("plant.jpg", _bmp_bytes(), "image/jpeg")},
        )
        assert response.status_code == 422
        assert storage.puts == []
        assert storage.deletes == []
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_valid_upload_persists_normalized_jpeg_and_metadata(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _fake_storage()
    monkeypatch.setattr("app.api.identifications.get_object_storage", lambda: storage)

    class FakeVision:
        async def analyze_image(self, image: bytes, prompt: str | None = None, **kwargs):
            from app.providers.types import ConfidenceLabel, ImageAnalysisResult, PlantCandidate

            return ImageAnalysisResult(
                provider="mock",
                description="A plant.",
                candidates=[
                    PlantCandidate(
                        scientific_name="Pilea peperomioides",
                        confidence_label=ConfidenceLabel.high,
                    )
                ],
            )

    async def matched_name(self, scientific_name: str):
        from app.identification.gbif import GbifTaxonomy

        return GbifTaxonomy(
            key=1,
            accepted_key=2,
            accepted_scientific_name=scientific_name,
            binomial_name="Pilea peperomioides",
            taxonomic_status="ACCEPTED",
            genus="Pilea",
            family="Urticaceae",
            species=scientific_name,
            matched=True,
        )

    monkeypatch.setattr("app.api.identifications.get_provider_registry", lambda: types.SimpleNamespace(vision=FakeVision()))
    monkeypatch.setattr("app.identification.gbif.GbifClient.match_name", matched_name)

    client, token = await _authed_client()
    try:
        response = await client.post(
            "/identifications",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("plant.png", PNG_BYTES, "image/png")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["image"]["mime_type"] == "image/jpeg"
        assert body["image"]["metadata"]["width"] == 60
        assert body["image"]["metadata"]["height"] == 40
        # Stored content is the normalized JPEG, not the original PNG.
        assert len(storage.puts) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_insert_failure_triggers_object_compensation(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _fake_storage()
    monkeypatch.setattr("app.api.identifications.get_object_storage", lambda: storage)

    async def boom(self, **kwargs):
        raise RuntimeError("db insert failed")

    monkeypatch.setattr(IdentificationRepository, "create_identification", boom)

    client, token = await _authed_client()
    try:
        with pytest.raises(RuntimeError):
            await client.post(
                "/identifications",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("plant.jpg", JPEG_BYTES, "image/jpeg")},
            )
        assert len(storage.puts) == 1
        assert storage.puts == storage.deletes
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_insert_failure_cleanup_failure_is_logged_without_content(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
) -> None:
    class FailingCleanupStorage:
        def __init__(self) -> None:
            self.puts: list[str] = []
            self.deletes: list[str] = []

        async def put_object(self, upload) -> StoredObject:
            self.puts.append(upload.path)
            return StoredObject(
                bucket="test",
                path=upload.path,
                mime_type=upload.mime_type,
                size_bytes=len(upload.content),
                created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )

        async def delete_object(self, path: str) -> None:
            self.deletes.append(path)
            raise RuntimeError("cleanup failed")

    storage = FailingCleanupStorage()
    monkeypatch.setattr("app.api.identifications.get_object_storage", lambda: storage)

    async def boom(self, **kwargs):
        raise RuntimeError("db insert failed")

    monkeypatch.setattr(IdentificationRepository, "create_identification", boom)

    client, token = await _authed_client()
    try:
        with caplog.at_level("ERROR", logger="app.api.identifications"):
            with pytest.raises(RuntimeError):
                await client.post(
                    "/identifications",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": ("plant.jpg", JPEG_BYTES, "image/jpeg")},
                )
        assert len(storage.deletes) == 1
        cleanup_records = [
            r for r in caplog.records if r.getMessage() == "identification_object_cleanup_failed"
        ]
        assert cleanup_records
        # The object identifier is logged, never the image bytes.
        assert cleanup_records[0].__dict__.get("ctx_object_path") == storage.puts[0]
    finally:
        await client.aclose()
