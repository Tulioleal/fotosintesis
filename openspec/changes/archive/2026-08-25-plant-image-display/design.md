## Context

Uploads already persist normalized JPEG bytes and metadata (`backend/app/api/identifications.py`, `identification_images` table). `garden_plants.image_path` exists (`backend/app/auth/tables.py`) and the API returns it; frontend surfaces already render it through `resolveImageUrl` (`HomeDashboard.tsx:188`, `GardenList.tsx:100`, `GardenDetail.tsx:134`, `RemindersManager.tsx:826`). Nothing populates the column: the save flow sends only `{confirmed_candidate_id, nickname, location, notes}` (`PlantProfileView.tsx:291-301`); `save_garden_plant` accepts `payload.image_path` (`profile_garden/repository.py:174`) but receives null. Storage adapters implement only put/delete. There is no StaticFiles/FileResponse anywhere in `backend/app`. Identify-flow preview is a browser blob URL lost on navigation. Local dev storage is ephemeral container `/tmp/storage-data`; production uses GCS.

## Goals / Non-Goals

**Goals:**

- Show the identifying photo on every surface that already renders `image_path`.
- Owner-private delivery with explicit auth on both hops (browser → BFF → backend).
- Deterministic placeholder behavior for imageless plants.

**Non-Goals:**

- No galleries, multi-image uploads, or image history (Phase 1 = one image per garden plant).
- No image replacement/removal UI.
- No public or shared image URLs; no CDN changes.
- No changes to identification ingestion or normalization.

## Decisions

- **Authenticated streaming route, not static mounts.** Backend route resolves the garden plant by id, verifies ownership plus that the referenced path belongs to one of the caller's `identification_images` rows, opens the object through a new adapter read op, streams with stored MIME type and `Cache-Control: private, no-store`. Works identically for local and GCS adapters.
- **Signed URLs deferred.** GCS signed URLs offload bandwidth but add expiry/signing complexity and break the uniform adapter interface; revisit as Phase 2 behind the same contract.
- **BFF proxy mirrors existing routes.** Forwards resolved backend auth headers and pipes the response; the browser never sees storage credentials or bucket paths.
- **Populate at save, validate server-side.** Optional `image_path` accepted only when it matches an owned `identification_images.storage_path` associated with the confirmed candidate being saved; arbitrary paths rejected; written in the same transaction as the rest of the save.
- **Display matrix.** Identify results keep blob preview during flow (unchanged). After save: garden list thumbnail, garden detail header, home dashboard card, plant profile hero — all via `resolveImageUrl(image_path)` with a shared placeholder fallback when null.
- **Manual-search placeholders.** Neutral shared placeholder (glyph/initial), never a broken `<img>` or a foreign photo.
- **Deletion.** Deleting the plant removes the link with the row; identification record/object persists under identification lifecycle; orphan cleanup out of scope.

## Risks / Trade-offs

- Two-hop streaming latency vs signed URLs → acceptable at current scale; contract keeps the door open.
- IDOR/path injection via crafted `image_path` → strict ownership join against `identification_images`; integration tests cover cross-user attempts.
- Large images inflate list views → thumbnails deferred; normalized dimensions already in metadata.
- Ephemeral local dev storage loses images across container restarts → dev-only annoyance; document it.

## Migration Plan

1. Adapter read op + backend media route with tests.
2. BFF proxy; repoint `resolveImageUrl` for storage-relative paths.
3. Extend save schema + frontend mutation; no backfill — old plants legitimately render placeholders.
4. Rollback: revert save-field usage; media route is additive and harmless.

## Open Questions

- GCS delivery: proxy streaming for Phase 1 vs short-lived signed URLs now (adapter contract change)?
- Placeholder visual: letter avatar vs botanical glyph vs neutral illustration?
- Should the identify-results preview survive navigation pre-save, or is post-save display sufficient for Phase 1?
