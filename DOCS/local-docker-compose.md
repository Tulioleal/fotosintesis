# Local Docker Compose

Docker Compose is the local development path. It is separate from cloud OpenTofu provisioning and does not create GCP resources.

## Start The Local Stack

Basic UI/API mode; confirmation scheduling is unavailable:

```bash
docker compose up frontend backend postgres
```

Confirmation and enrichment mode:

```bash
JOBS_PRODUCER_ENABLED=true \
JOBS_REQUIRED_CONTRACTS=enrich_confirmed_plant:1 \
docker compose up frontend backend worker postgres
```

Start optional local object storage:

```bash
docker compose --profile storage up frontend backend postgres minio
```

The local stack uses mock providers by default so development can run without real model, vision, search or embedding credentials.

The backend container runs `alembic upgrade head` before starting Uvicorn so a clean local Postgres volume has the required tables.

## Environment Files

Copy examples when local overrides are needed:

```bash
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env
```

Important local variables:

- `MODEL_PROVIDER=mock`, `VISION_PROVIDER=mock`, `JUDGE_PROVIDER=mock`, `SEARCH_PROVIDER=mock` and `EMBEDDING_PROVIDER=mock` keep providers deterministic.
- To test Gemini for all non-embedding roles locally, set `MODEL_PROVIDER=gemini`, `VISION_PROVIDER=gemini`, `JUDGE_PROVIDER=gemini`, `SEARCH_PROVIDER=gemini`, `GEMINI_API_KEY`, and `GEMINI_SEARCH_MODEL`; keep `EMBEDDING_PROVIDER=openai` with `OPENAI_API_KEY` for production-like vector ingestion or `EMBEDDING_PROVIDER=mock` for deterministic local runs.
- `DATABASE_URL` points to local Postgres in Compose or localhost when running directly.
- `OBJECT_STORAGE_*` points to MinIO only when the storage profile is used.
- `AUTH_SECRET` is required by Auth.js locally.

## Tests

Run backend tests:

```bash
cd backend
pip install -e '.[dev]'
pytest
```

Run frontend component tests:

```bash
pnpm --filter frontend test
```

Run Playwright against the local stack:

```bash
JOBS_PRODUCER_ENABLED=true \
JOBS_REQUIRED_CONTRACTS=enrich_confirmed_plant:1 \
docker compose up frontend backend worker postgres -d
pnpm --filter frontend test:e2e
```

## Evaluation

The backend evaluation runner uses deterministic mocks unless real providers are configured:

```bash
cd backend
python -m app.evaluation.runner
```

Use real provider credentials only through local environment files or secret managers. Do not commit provider keys, database passwords, session secrets or API tokens.
