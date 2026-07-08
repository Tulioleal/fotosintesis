# External Secrets and Secret Manager

Secret Manager containers are managed by the OpenTofu env roots; secret
**values** are populated out of band and projected into the cluster by
the External Secrets Operator.

## Containers managed by OpenTofu

The env roots create one container per required secret in the project.
The full list is `var.secret_ids` in `infra/opentofu/envs/{dev,prod}`
and includes:

- `fotosintesis-database-url` -> `database-url` in the runtime Secret.
- `fotosintesis-auth-secret` -> `auth-secret` in the runtime Secret.
- `fotosintesis-openai-api-key` -> `openai-api-key` in the runtime
  Secret (optional; only required when an OpenAI family provider is
  configured).
- `fotosintesis-gemini-api-key` -> `gemini-api-key` in the runtime
  Secret (optional; only required when a Gemini family provider is
  configured).

The default dev secret list also includes placeholder
`fotosintesis-object-storage-access-key` and
`fotosintesis-object-storage-secret-key` containers for legacy
configurations. GKE access to GCS uses Workload Identity, so static
storage keys are not required for the current runtime.

## Populate secret values manually

Out of band from OpenTofu, populate each container with at least one
version. Use `gcloud secrets versions add` and read the value from a
local file, environment variable, or your secret manager of record:

```bash
printf '%s' "$DATABASE_URL" | gcloud secrets versions add fotosintesis-database-url \
  --project="$PROJECT_ID" --data-file=-
printf '%s' "$AUTH_SECRET" | gcloud secrets versions add fotosintesis-auth-secret \
  --project="$PROJECT_ID" --data-file=-
printf '%s' "$OPENAI_API_KEY" | gcloud secrets versions add fotosintesis-openai-api-key \
  --project="$PROJECT_ID" --data-file=-
printf '%s' "$GEMINI_API_KEY" | gcloud secrets versions add fotosintesis-gemini-api-key \
  --project="$PROJECT_ID" --data-file=-
```

The deploy workflow waits for the runtime Secret to be projected before
applying workloads, and the `Verify required provider API key secrets`
step fails the deploy when a configured provider is missing its key.

## Runtime projection

The deploy workflow installs (or upgrades) External Secrets Operator at
the pinned `EXTERNAL_SECRETS_OPERATOR_VERSION` (default `0.10.4`) and
waits for its Deployment to be `Available`. Once ESO is ready, the
workflow applies `80-external-secrets.yaml`, which contains:

- A `SecretStore` named after `EXTERNAL_SECRETS_STORE_NAME`
  (default `fotosintesis-secret-store`) that uses Workload Identity
  against the backend Kubernetes service account.
- An `ExternalSecret` that maps each required Secret Manager value
  into a single Kubernetes Secret named after `RUNTIME_SECRET_NAME`
  (default `fotosintesis-runtime`).

The refresh interval is `EXTERNAL_SECRETS_REFRESH_INTERVAL` (default
`5m`). Lower values surface rotated secrets faster at the cost of
additional Secret Manager API calls.

The backend Deployment and the migration Job read the projected Secret
through Kubernetes `secretKeyRef` env vars. The runtime Secret is
created with `creationPolicy: Owner` so the deploy workflow never
conflicts with ESO on Secret reconciliation.

## What is NOT in source control

- Secret Manager values.
- GitHub Actions secrets.
- GCP service account JSON keys.

The workflow files, OpenTofu files, and rendered manifests never embed
secret values.
