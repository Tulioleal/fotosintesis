## 1. Storage Read Path

- [x] 1.1 Add an open/read operation to the storage adapter interface; implement for local and GCS (stream, byte size, stored MIME type).
- [x] 1.2 Missing objects surface as explicit not-found errors distinguishable from authorization failures.

## 2. Backend Media Route

- [x] 2.1 Authenticated route serves a garden plant's image by plant id after verifying caller ownership and path-to-identification association.
- [x] 2.2 Stream with stored content type, correct content length, `Cache-Control: private, no-store`.
- [x] 2.3 Return 404 (not 403) for other users' plants to avoid existence disclosure; log rejections without content.
- [x] 2.4 Tests: ownership enforcement, unknown path, deleted object, header correctness.

## 3. Save-Time Linkage

- [x] 3.1 Extend garden-save request schema with optional `image_path`; validate against caller's identification rows for that candidate.
- [x] 3.2 Persist `garden_plants.image_path` inside the existing save transaction.
- [x] 3.3 Send the current identification's storage path from the plant-profile save flow.
- [x] 3.4 Reject payloads referencing unowned paths with English validation messages.

## 4. Frontend Delivery and Display

- [x] 4.1 Next.js BFF media proxy resolving backend auth headers server-side, streaming the response.
- [x] 4.2 Point storage-relative URLs at the BFF media path; leave absolute http(s) untouched in `resolveImageUrl`.
- [x] 4.3 Shared placeholder component rendered on garden list, garden detail, home dashboard, plant profile when null (manual-search saves included).
- [x] 4.4 Verify identify-results blob preview still works and post-save display works on all four surfaces.

## 5. Verification

- [x] 5.1 Integration test full loop: upload → confirm → save with image → fetch via BFF as owner; cross-user fetch fails.
- [x] 5.2 Vitest coverage: placeholder rendering on imageless plants, save payload construction.
- [x] 5.3 Backend + frontend lint/typecheck/tests green.
