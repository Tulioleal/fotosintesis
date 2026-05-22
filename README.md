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
