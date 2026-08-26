## Why

Identification uploads are currently accepted based only on the declared MIME type and byte size. The backend never proves the bytes are a valid, decodable image, so corrupt files, misleading MIME types, and decompression-heavy images can pass the boundary and reach provider calls and object storage. Uploads are also stored before all durable steps succeed, which can leave orphaned objects.

## What Changes

- Add Pillow as an explicit, maintained server-side image decoding dependency.
- Decode uploaded bytes and detect the actual image format rather than trusting the declared MIME type.
- Reject empty, corrupt, truncated, undecodable, or unsupported images before any durable work.
- Enforce configurable width, height, total-pixel, and encoded-size limits, including decompression-bomb detection.
- Normalize every accepted image to one supported output format (JPEG): apply orientation, strip EXIF and other metadata, and flatten to RGB.
- Persist the normalized bytes and derive the stored MIME type and dimensions from the normalized output.
- Normalize before object storage so validation failures never write an object.
- Compensate for failures after storage by deleting a stored object when its database record cannot be persisted.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plant-identification-taxonomy`: Validate and normalize actual image contents before analysis and durable use.
- `project-foundation`: Require the object storage abstraction to expose best-effort deletion so ingestion can compensate for failures after a write.

## Impact

- Add Pillow to backend packaging and `pyproject.toml`.
- Add image ingestion settings for limits, output quality, and decoder safety.
- Refactor the identification upload endpoint and introduce an image normalization step.
- Persist normalized MIME type and dimensions as image metadata.
- Update unit and integration test fixtures to use deterministic, valid images.
- Add observability for rejection categories and cleanup failures.
