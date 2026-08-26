"""Decode, validate, and normalize identification image uploads.

This is a safety boundary, not a semantic one: it proves the uploaded bytes
are a real, decodable image within configured limits and normalizes every
accepted image to a single supported output format (JPEG) before any durable
work. The vision provider always receives uniform, decodable JPEG bytes.
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass
from enum import Enum

from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning

from app.core.settings import get_settings

# Supported input formats, keyed by the format name reported by Pillow.
SUPPORTED_INPUT_FORMATS = {"JPEG", "PNG", "WEBP"}

OUTPUT_FORMAT = "JPEG"
OUTPUT_MIME_TYPE = "image/jpeg"


class ImageRejectionCategory(str, Enum):
    EMPTY = "empty"
    TOO_LARGE = "too_large"
    UNSUPPORTED_TYPE = "unsupported_type"
    NOT_AN_IMAGE = "not_an_image"
    CORRUPT = "corrupt"
    UNSUPPORTED_FORMAT = "unsupported_format"
    DIMENSIONS_EXCEEDED = "dimensions_exceeded"
    PIXELS_EXCEEDED = "pixels_exceeded"
    DECOMPRESSION_BOMB = "decompression_bomb"


class ImageValidationError(ValueError):
    """Raised when uploaded bytes cannot be validated or normalized.

    ``category`` is a stable, machine-readable rejection category used for
    observability and to produce a specific user-facing error message.
    """

    def __init__(self, category: ImageRejectionCategory, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.message = message


@dataclass(frozen=True)
class NormalizedImage:
    content: bytes
    mime_type: str
    width: int
    height: int
    size_bytes: int


def normalize_identification_image(content: bytes) -> NormalizedImage:
    """Validate and normalize raw upload bytes to a JPEG-safe output.

    Raises :class:`ImageValidationError` with a stable category on any
    rejection. Never returns until the bytes are proven decodable and within
    the configured limits.
    """
    settings = get_settings()

    if not content:
        raise ImageValidationError(
            ImageRejectionCategory.EMPTY, "The uploaded file is empty."
        )
    if len(content) > settings.identification_max_image_bytes:
        raise ImageValidationError(
            ImageRejectionCategory.TOO_LARGE,
            f"The image exceeds {settings.identification_max_image_bytes} bytes.",
        )

    Image.MAX_IMAGE_PIXELS = settings.identification_max_image_pixels

    try:
        with Image.open(io.BytesIO(content)) as image:
            _check_supported_format(image)
            _enforce_dimensions(
                image,
                max_width=settings.identification_max_image_width,
                max_height=settings.identification_max_image_height,
            )
            _enforce_pixels(image, settings.identification_max_image_pixels)
            _load_pixels(image)
            image = ImageOps.exif_transpose(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            width, height = image.size
            output = io.BytesIO()
            image.save(
                output,
                format=OUTPUT_FORMAT,
                quality=settings.identification_output_quality,
            )
    except ImageValidationError:
        raise
    except DecompressionBombError as exc:
        raise ImageValidationError(
            ImageRejectionCategory.DECOMPRESSION_BOMB,
            "The image expands beyond the safe decoding limit.",
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError(
            ImageRejectionCategory.CORRUPT,
            "The image is corrupt, truncated, or could not be decoded.",
        ) from exc

    return NormalizedImage(
        content=output.getvalue(),
        mime_type=OUTPUT_MIME_TYPE,
        width=width,
        height=height,
        size_bytes=len(output.getvalue()),
    )


def _check_supported_format(image: Image.Image) -> None:
    fmt = (image.format or "").upper()
    if fmt not in SUPPORTED_INPUT_FORMATS:
        raise ImageValidationError(
            ImageRejectionCategory.UNSUPPORTED_FORMAT,
            "Only JPEG, PNG, and WebP images are supported.",
        )


def _enforce_dimensions(image: Image.Image, *, max_width: int, max_height: int) -> None:
    width, height = image.size
    if width > max_width or height > max_height:
        raise ImageValidationError(
            ImageRejectionCategory.DIMENSIONS_EXCEEDED,
            f"The image dimensions exceed {max_width}x{max_height} pixels.",
        )


def _enforce_pixels(image: Image.Image, max_pixels: int) -> None:
    width, height = image.size
    if width * height > max_pixels:
        raise ImageValidationError(
            ImageRejectionCategory.PIXELS_EXCEEDED,
            f"The image exceeds {max_pixels} total pixels.",
        )


def _load_pixels(image: Image.Image) -> None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DecompressionBombWarning)
            image.load()
    except DecompressionBombError as exc:
        raise ImageValidationError(
            ImageRejectionCategory.DECOMPRESSION_BOMB,
            "The image expands beyond the safe decoding limit.",
        ) from exc
    except DecompressionBombWarning as exc:
        raise ImageValidationError(
            ImageRejectionCategory.DECOMPRESSION_BOMB,
            "The image expands beyond the safe decoding limit.",
        ) from exc
