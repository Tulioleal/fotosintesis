## 1. Dependency and Settings

- [x] 1.1 Add `Pillow` as an explicit dependency in `backend/pyproject.toml` and refresh `backend/uv.lock`.
- [x] 1.2 Add `identification_max_image_bytes`, `identification_max_image_width`, `identification_max_image_height`, `identification_max_image_pixels`, and `identification_output_quality` to `Settings` with conservative defaults and validation aliases.
- [x] 1.3 Add a `_validate` model validator (or field constraints) so pixel/dimension/quality settings fail startup on invalid values.

## 2. Image Normalization

- [x] 2.1 Create `app/identification/image_processing.py` with a `NormalizedImage` result type and a typed `ImageValidationError` carrying a stable rejection category.
- [x] 2.2 Implement `normalize_identification_image`: decode with `Image.open`, detect the actual format, verify/load, enforce dimension and pixel limits, apply `ImageOps.exif_transpose`, convert to RGB, and re-encode to JPEG at the configured quality.
- [x] 2.3 Enforce decompression-bomb safety by setting `Image.MAX_IMAGE_PIXELS` to the configured limit and treating `DecompressionBombError`/`DecompressionBombWarning` as validation failures.
- [x] 2.4 Reject empty, corrupt, truncated, unsupported, and undecodable bytes with a specific, user-facing category before any storage or provider call.
- [x] 2.5 Add `app.identification.image_processing` to the API slice-internal allowlist in `scripts/check_architecture.py`.

## 3. Endpoint Refactor

- [x] 3.1 Refactor `POST /identifications` to normalize before storage: read bytes, enforce encoded-size limit, normalize, then store the normalized bytes and derive MIME type and dimensions from the normalized output.
- [x] 3.2 Persist normalized MIME type and pixel dimensions in the `identification_images` metadata and use the normalized bytes for object storage.
- [x] 3.3 Wrap the `create_identification` insert so a failure triggers best-effort `delete_object(stored.path)`, logging failures with the object identifier and not the image content.
- [x] 3.4 Keep provider and GBIF sad paths unchanged (retained recoverable rows), sending only normalized bytes to the vision provider.

## 4. Tests

- [x] 4.1 Add a test fixture helper that generates small deterministic valid JPEG/PNG/WebP images with Pillow.
- [x] 4.2 Replace any fake image bytes used by identification upload tests with the valid fixtures.
- [x] 4.3 Add tests for: declared-MIME/byte mismatch, corrupt bytes, truncated image, unsupported format, oversized dimensions/pixels with small compressed size, and decompression-bomb rejection.
- [x] 4.4 Add tests for orientation application and EXIF/metadata stripping on the persisted normalized bytes.
- [x] 4.5 Add tests for object-storage compensation on database insert failure, including a case where cleanup itself fails and is logged without image content.
- [x] 4.6 Run the existing multilingual semantic regression coverage and confirm no behavioral change; no keyword-based semantic work is added or changed by this boundary.

## 5. Verification

- [x] 5.1 Run `ruff`, `pytest`, and `scripts/check_architecture.py` in `backend/` and fix any failures.
- [x] 5.2 Manually verify a valid JPEG/PNG/WebP upload returns normalized candidates and an invalid upload returns the specific English 4xx before any object is written.
