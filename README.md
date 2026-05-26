# Fotosintesis AI

Foundation workspace for the Fotosintesis AI MVP.

## Local Development

Copy environment examples when local overrides are needed:

```bash
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env
```

Start the main local stack:

```bash
docker compose up frontend backend postgres
```

Start with local object storage:

```bash
docker compose --profile storage up frontend backend postgres minio
```

Run the backend directly:

```bash
cd backend
pip install -e .
uvicorn app.main:app --reload
```

Run the frontend directly:

```bash
pnpm install
pnpm --filter frontend dev
```

## OpenAPI TypeScript Client

The frontend API contracts are generated from the FastAPI OpenAPI schema. After changing backend request or response models used by the frontend, regenerate the contracts:

```bash
pnpm --filter frontend openapi:generate
```

This exports the backend schema to `frontend/src/lib/generated/openapi.json` and regenerates `frontend/src/lib/generated/openapi.d.ts` with `openapi-typescript`. Do not edit files under `frontend/src/lib/generated/` by hand.

To verify committed generated artifacts are current, run:

```bash
pnpm --filter frontend openapi:check
```
