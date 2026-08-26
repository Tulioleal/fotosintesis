# Local Docker Compose

Docker Compose is the local development path. It is separate from cloud OpenTofu provisioning and does not create GCP resources.

## Start The Local Stack

Basic UI/API mode (accepts confirmations; enrichment jobs stay pending until a worker is started):

```bash
docker compose up frontend backend postgres
```

Confirmation and enrichment mode:

```bash
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

### Focused Enrichment E2E

The enrichment journey uses an isolated Compose project, deterministic AI
providers, a local GBIF fixture, real Auth.js registration, PostgreSQL
migrations, the durable worker, and a production Next.js build.

Run:

```bash
pnpm e2e:enrichment
```

The script builds Next.js with offline font responses, waits for every service
to become healthy, runs the enrichment journey serially, and removes only the
isolated `photosynthesis-e2e` containers and volumes.

Port 3000 must be available before starting. The command never reuses an
unrelated frontend server.

PostgreSQL and the backend remain internal to the isolated Compose network and
do not publish host ports during this workflow. The command refuses to start
when another enrichment E2E run is active, preventing concurrent runs from
removing each other's containers or volumes.

## Evaluation

The backend evaluation runner uses deterministic mocks unless real providers are configured:

```bash
cd backend
python scripts/run_evaluation.py --mode recorded
```

Or from the repository root: `pnpm eval`.

### Quality gate

Runs are approved by the `quality_gate` profile (the CLI default):

- Aggregate LLM-judge pass rate over supported cases must reach **0.60**.
- Per-case judge scores follow the shared rubric passing score (0.75); tool assertions must be fully satisfied.
- A supported-case ratio below **0.20** fails the run as a *coverage failure*, distinct from quality failures.
- Execution or metric errors block approval.
- Thresholds must be strictly positive or omitted entirely; `0.0` is invalid profile configuration.

The gate writes `report.md` and `result.json` under `app/evaluation/data/runs/`
(retention bounded by `EVALUATION_RUN_RETENTION`, default latest 10) and exits
non-zero when not approved. CI replays the committed recording set
(`app/evaluation/data/recordings/ci-recording.json`) with `--providers mock`.

Refresh the committed recording after intentional graph changes:

```bash
cd backend
EMBEDDING_DIMENSION=8 python scripts/record_evaluation_set.py
```

The `EMBEDDING_DIMENSION=8` override matches the deterministic mock embedding
provider; omit it only when running against real embedding models.

Use real provider credentials only through local environment files or secret managers. Do not commit provider keys, database passwords, session secrets or API tokens.
