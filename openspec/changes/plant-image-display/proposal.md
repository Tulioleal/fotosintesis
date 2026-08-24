## Why

Identified plants never display the photo they were identified with. Uploads persist normalized JPEGs to object storage (`identifications/{user_id}/{uuid}.jpg`) with full metadata rows, and `garden_plants.image_path` exists and is rendered by every garden surface — but the column is never populated because the save flow omits it, and no serving endpoint exists, so even a populated path would 404. Images are owner-private, so naive static mounting would leak across users. The data model is ready; the linkage and the authenticated delivery path are missing.

## What Changes

- Add an owner-authenticated media-serving backend route that streams objects through the storage adapter with ownership checks, stored content type, and private caching headers.
- Add a storage-adapter read operation (adapters currently implement only put/delete).
- Proxy media through the Next.js BFF with session auth; no static mount of object storage.
- Link the identification image at save time: the garden-save flow sends the identification's storage path, validated server-side against the caller's own `identification_images` rows, and populates `garden_plants.image_path`.
- Render the saved image across surfaces: garden list, garden detail, home dashboard, plant profile.
- Define placeholder rules for plants saved from manual GBIF search (`origin="search"`, no image): neutral placeholder treatment, never a broken image or another user's photo.
- Define deletion expectations: deleting a garden plant removes the link with the row; the underlying identification object remains governed by identification lifecycle.
- Scope Phase 1 to one image per garden plant; galleries and image history are explicitly out of scope.

## Capabilities

### New Capabilities

- `plant-media-display`: Authenticated serving and display of the plant photo a garden plant was saved with.

### Modified Capabilities

- `plant-profile-garden`: Garden save links the identification image into `garden_plants.image_path`.

## Impact

- `backend/app/storage/*`: new read/open adapter operation (local + GCS).
- New authenticated backend media route; ownership join against `identification_images`.
- New Next.js BFF media proxy route forwarding session-resolved backend auth headers.
- Garden-save request schema + `PlantProfileView` save mutation extended with optional `image_path`.
- `frontend/src/lib/images.ts` repointed for storage-relative paths; shared placeholder component for imageless plants.
- Tests: ownership rejection, cross-user access, missing-object behavior, cache headers, placeholder rendering, populate-at-save persistence.
