## Context

`POST /identifications` currently reads the whole upload, checks the declared `content_type` against a fixed allowlist and the byte length against a fixed 8 MB ceiling, then immediately stores the original bytes and inserts an `identification_images` row. Nothing decodes the bytes, so a JPEG-declared blob of arbitrary data, a truncated image, or a small compressed image that expands to enormous pixel dimensions all pass the boundary. The object is also written before the database insert, so a failure in `create_identification` leaves an orphaned object with no referencing row.

The image is a safety boundary, not a semantic one: no botanical classification, evidence, answerability, or language behavior changes here. Deterministic byte-level validation is exactly the kind of non-semantic safety check this codebase permits.

## Goals / Non-Goals

**Goals:**

- Decode every upload and prove the bytes are a real image before any durable work.
- Detect the actual format from decoded bytes and reject mismatches, corruption, truncation, unsupported formats, and unsafe decompression.
- Enforce configurable dimension, pixel-count, and size limits with conservative defaults.
- Normalize accepted images to one supported output format with orientation applied and metadata stripped, and persist the derived MIME type and dimensions.
- Remove the orphan window: normalize before storage, and delete a just-stored object when its record cannot be persisted.

**Non-Goals:**

- No scheduled reconciliation job for orphaned temporary objects. Immediate compensation removes the realistic orphan path; a background sweeper is deferred until it is observably needed.
- No multi-format output. All accepted images are normalized to JPEG, which the vision providers already accept and which is adequate for plant identification.
- No retention of the original full-resolution upload by default.
- No semantic moderation of image subject matter and no changes to provider/GBIF/confirmation behavior.

## Decisions

### Use Pillow as the single decoder and normalizer

Pillow is the maintained, standard Python imaging library and is already present in the lockfile as a transitive dependency. It provides format detection via `Image.open`, decompression-bomb protection via `Image.MAX_IMAGE_PIXELS`, orientation via `ImageOps.exif_transpose`, and metadata-free re-encoding. It is declared as an explicit top-level dependency so the direct import is intentional and reproducible.

Alternatives considered: `imageio` and `opencv-python` pull larger native stacks for no added benefit here; hand-rolling format sniffing was rejected because it cannot actually prove decodability. A single library keeps the boundary small and reviewable.

### Normalize everything to JPEG before storage

One new module, `app/identification/image_processing.py`, exposes `normalize_identification_image(content: bytes) -> NormalizedImage` and raises a typed `ImageValidationError` with a stable category on failure. The pipeline decodes with `Image.open`, verifies the stream loads, confirms the actual `image.format` is in the supported input set (JPEG, PNG, WebP), checks dimensions and pixel count, applies `ImageOps.exif_transpose`, converts to RGB, and re-encodes to JPEG at the configured quality. `NormalizedImage` carries the normalized bytes, `image/jpeg` MIME type, and pixel dimensions.

A single output format removes the need to preserve per-upload formats and guarantees the vision provider always receives a uniform, decodable JPEG. PNG and WebP remain supported inputs; only the output is pinned.

### Validate and normalize before object storage

The endpoint order becomes: read bytes, enforce the encoded-size limit, normalize (decode/validate/normalize in memory), store the normalized bytes, then insert the metadata row. Because validation and normalization happen before `put_object`, every rejection path writes nothing, which removes most orphan risk without a cleanup job.

The declared MIME type is treated only as an input hint for a fast-fail path; the authoritative format comes from decoding. This keeps the existing early 415 for clearly-unsupported declared types while never trusting the declaration for correctness.

### Compensate only the true orphan window

After `put_object` succeeds, the only step that can leave an unreferenced object is a failure in `create_identification` (the database insert). That call is wrapped so a failure triggers a best-effort `delete_object(stored.path)`, and a deletion failure is logged with the path, never the image bytes.

Provider and GBIF failures intentionally do NOT delete the object: those paths still persist a recoverable `identification_images` row (`retry_needed` / sad path) that references the image, so the object is not orphaned and remains needed for the user's retry display. Deleting it there would leave a row pointing at a missing object. Restricting compensation to the orphan window is the minimal correct behavior and avoids introducing rollback for every downstream sad path.

### Make limits configurable with conservative defaults

New settings on `Settings` with conservative defaults and validation aliases: `identification_max_image_bytes` (8 MiB), `identification_max_image_width` and `identification_max_image_height` (4000 each), `identification_max_image_pixels` (40,000,000), and `identification_output_quality` (85). Supported input formats remain a module constant, since making the format allowlist configurable adds surface without a driving use case.

> Note: the per-side dimension default is 4000 px rather than 8000 so that the
> width × height product of a max-dimension image (16 MP) stays comfortably below
> the 40 MP total-pixel ceiling. The limits are validated independently by field
> constraints (`gt=0` for dimensions/pixels, `ge=1`/`le=100` for quality) so that
> each bound remains an independent backstop; the total-pixel cap catches images
> that are large on both axes even when each side is within its own limit.

Decompression-bomb protection sets `Image.MAX_IMAGE_PIXELS` to the configured pixel limit as a decode-time backstop; both `DecompressionBombError` and `DecompressionBombWarning` are treated as validation failures rather than merely logged.

## Risks / Trade-offs

- [Normalization adds CPU and memory cost per upload] -> Enforce encoded-size, dimension, and pixel limits before re-encoding, and only ever process the bounded normalized output.
- [Re-encoding to JPEG can alter visual detail] -> Use a quality level sufficient for identification; this endpoint feeds a vision classifier, not archival storage.
- [Existing fixtures assume arbitrary bytes pass] -> Replace them with deterministic valid images generated by Pillow in tests, and add rejection fixtures for mismatch, corruption, truncation, and limits.
- [Decoding is permissive about some malformed files] -> Combine `verify()`/`load()` with format detection and treat decoder warnings (bomb, truncated) as failures.
- [Best-effort deletion can fail] -> Log with the object identifier and leave residual objects for the deferred reconciliation; do not fail the user request on cleanup failure.

## Migration Plan

No existing stored image is rewritten. New validation applies only to new identification uploads after deployment. Limits ship with the documented conservative defaults and are tightened only after observing metrics. The change is deployed with the backend; a rollback redeploys the prior image, which restores the previous permissive behavior without data loss since no schema change is required.

## Open Questions

- Are 4000 px per side and 40 MP conservative enough for phone photos while remaining safe for decode memory? Confirm against real upload telemetry before tightening or raising the per-side limit.
- Is JPEG at quality 85 acceptable for vision-provider accuracy, or should quality be raised for near-identical detail preservation?
