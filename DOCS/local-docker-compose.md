# Local Docker Compose

Docker Compose is the local development path. It is separate from cloud OpenTofu provisioning and does not create GCP resources.

## Start The Local Stack

```bash
docker compose up frontend backend postgres
```

Start optional local object storage:

```bash
docker compose --profile storage up frontend backend postgres minio
```

The local stack uses mock providers by default so development can run without real model, vision, search or embedding credentials.

## Environment Files

Copy examples when local overrides are needed:

```bash
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env
```

Important local variables:

- `PROVIDER_PROFILE=mock` keeps providers deterministic.
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
docker compose up frontend backend postgres
pnpm --filter frontend test:e2e
```

## Evaluation

The backend evaluation runner uses deterministic mocks unless real providers are configured:

```bash
cd backend
python -m app.evaluation.runner
```

Use real provider credentials only through local environment files or secret managers. Do not commit provider keys, database passwords, session secrets or API tokens.
