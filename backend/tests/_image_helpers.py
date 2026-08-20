"""Deterministic, valid image fixtures for identification upload tests.

Images are generated at import time with Pillow so that upload tests exercise
the real decode/normalize path rather than arbitrary placeholder bytes.
"""

from __future__ import annotations

import io

from PIL import Image


def make_image_bytes(fmt: str, size: tuple[int, int] = (60, 40)) -> bytes:
    """Return deterministic PNG/JPEG/WebP bytes with the given dimensions."""
    image = Image.new("RGB", size, (34, 139, 34))
    buffer = io.BytesIO()
    if fmt.upper() == "JPG":
        fmt = "JPEG"
    image.save(buffer, format=fmt.upper())
    return buffer.getvalue()


JPEG_BYTES = make_image_bytes("JPEG")
PNG_BYTES = make_image_bytes("PNG")
WEBP_BYTES = make_image_bytes("WEBP")


def make_image_with_orientation(size: tuple[int, int] = (30, 20)) -> bytes:
    """Return a PNG carrying an EXIF orientation tag (e.g. 90-degree rotation)."""
    from PIL import ImageOps

    image = Image.new("RGB", size, (10, 90, 200))
    exif = Image.Exif()
    exif[274] = 6
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", exif=exif)
    return buffer.getvalue()
