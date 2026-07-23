# Deploy and Release

The platform splits the application lifecycle into three workflow
families:

- `backend-ci.yml` / `frontend-ci.yml` - source validation, image
  build, dev deploy trigger. Both authenticate as
  `DEV_CI_SERVICE_ACCOUNT_EMAIL` (the image-CI account, not the IaC
  account).
- `iac.yml` - OpenTofu fmt/validate/plan, per-environment apply, and
  post-apply sync jobs that publish per-environment outputs to
  repository variables. Plan/apply paths authenticate as
  `DEV_IAC_SERVICE_ACCOUNT_EMAIL` or `PROD_IAC_SERVICE_ACCOUNT_EMAIL`
  (the dedicated IaC identities, not the image-CI account).
- `deploy.yml` - Kubernetes manifest render, secret projection wait,
  migration, rollout, smoke checks. Authenticates as
  `DEV_DEPLOY_SERVICE_ACCOUNT_EMAIL` or `PROD_DEPLOY_SERVICE_ACCOUNT_EMAIL`.
- `release.yml` - production image promotion and prod deploy.
  `verify-source-images` authenticates as `DEV_CI_SERVICE_ACCOUNT_EMAIL`;
  `promote-images` authenticates as `PROD_CI_SERVICE_ACCOUNT_EMAIL`.

## Image tag contract

Every backend and frontend image is tagged with the **full 40-character
Git commit SHA** (`${{ github.sha }}` in GitHub Actions). `latest` and
branch names are never pushed. The deploy and release workflows enforce
this with a regex guard that rejects anything that is not a 40-character
lower-case hex SHA, including `latest`, branch names, empty values, and
tag prefixes.

The CI build step tags each image with the GitHub Actions `$GITHUB_SHA`
exposed at the start of the run. Tag format alone does not make an image
immutable. The shared Artifact Registry repository sets
`docker_config.immutable_tags = true`, so a tag always resolves to the same
digest and a push of different bytes under an existing SHA fails. If a build
succeeds but deployment fails, retry `deploy.yml` with the existing tag rather
than rebuilding that SHA. SHA-tagged images are retained permanently; that
storage cost is accepted for this university project.

## Auto dev deploy

A push to `main` that changes `backend/**`, `frontend/Dockerfile`, or
`.github/workflows/<service>-ci.yml` triggers the corresponding CI
workflow. On a successful build, the CI workflow's `deploy-dev` job
calls `deploy.yml` through `workflow_call` with:

- `environment: dev`
- `backend_image_tag: <40-character SHA>` (from the build step)
- `frontend_image_tag: <40-character SHA>` (from the build step, or
  reused from the current dev Deployment when the path filter excluded
  the frontend change)

The auto-dev flow is the path-filter-restricted scenario described in
task 8.4. The `Resolve and validate image tags` step reads the
currently deployed tag from the dev Deployment when the calling CI
workflow did not pass one, and reuses it so the deploy can complete
without an explicit tag for the unchanged service.

## Manual dev redeploy

To redeploy dev with a specific SHA, dispatch `deploy.yml` from the
Actions tab:

- `environment: dev`
- `backend_image_tag: <40-character SHA>` (required, 40-character hex)
- `frontend_image_tag: <40-character SHA>` (required, 40-character hex)

The dispatch inputs are `required: true` and the deploy workflow
re-checks the format with a regex guard. The deploy cannot proceed with
`latest`, branch names, or any non-SHA value.

## Production release

Production deploys are a manual two-step process:

1. **Promote** the dev SHA-tagged images to the prod Artifact Registry
   using `release.yml` with:
   - `backend_image_tag: <40-character SHA that passed dev>`
   - `frontend_image_tag: <40-character SHA that passed dev>`

   The `verify-source-images` job authenticates as
   `DEV_CI_SERVICE_ACCOUNT_EMAIL` through the dev WIF provider and
   confirms the tags exist in the dev registry before `promote-images`
   authenticates as `PROD_CI_SERVICE_ACCOUNT_EMAIL` through the prod
   WIF provider and copies them to the prod registry.

2. **Apply** the prod manifest via `deploy.yml` (called by
   `release.yml`'s `deploy-prod` job with `environment: prod`). The
   `summary` job records the backend tag, frontend tag, source
   registry, prod registry, GKE cluster, namespace, and per-gate
   results in the workflow summary.

The prod environment requires reviewer approval, so the prod dispatch
sits in the queue until the configured reviewer approves the run. The
release workflow does not run an application source build; it only
verifies source images, copies them to the prod registry, and triggers
the prod deploy. Image rebuilds for prod are out of scope for this
round.

## Verification gates

Both `deploy.yml` and `release.yml` enforce the following gates:

1. **Image tag validation** - 40-character lower-case hex SHA.
2. **OpenTofu output presence** - every required output (registry URL,
   GKE cluster, runtime service accounts, storage bucket, Cloud SQL
   connection/database, static IP, namespace, secret name) must be
   non-empty.
3. **External Secrets projection** - the runtime Secret
   (`fotosintesis-runtime`) must be projected before backend rollout.
4. **Provider API key projection** - the `Verify required provider API
   key secrets` step fails the deploy when a configured provider is
   missing its key.
5. **Migration completion** - the workflow applies the one-shot migration Job
     and waits for its native Kubernetes `Complete` condition. The restartable
     Cloud SQL proxy init sidecar exits with the Pod, so Alembic success can
     complete the Job without workflow-managed deletion. Native sidecars
     require Kubernetes 1.29 or newer; the workflow checks the GKE server
     version before applying the Job. The API, worker, and frontend are not
     applied until that wait passes.
6. **Backend, worker, and frontend rollout** - the shared rollout script waits
   up to 600 seconds for each Deployment. On failure it prints Deployment,
   ReplicaSet, Pod, current/previous container, Cloud SQL proxy, and event
    diagnostics before failing the workflow.
7. **Enrichment worker compatibility** - after migrations, the worker is applied
   and must become ready with
   `JOBS_REQUIRED_CONTRACTS=enrich_confirmed_plant:1` before the backend is
   applied. Worker startup verifies that the exact closed job type and payload
   version are registered, so confirmation scheduling cannot lead the consumer.
8. **Backend in-cluster smoke** - a one-off curl pod hits
   `http://fotosintesis-backend.<namespace>.svc.cluster.local:8000/health`.
9. **Frontend public smoke** - 60 retries against the configured
   public URL.

The `release.yml` summary step also includes the per-gate results from
`deploy.yml` (`migration_result`, `rollout_result`,
`required_keys_result`, `backend_smoke_result`, `frontend_smoke_result`)
so a single workflow view captures the entire release.

The last-healthy image pair is written to the
`fotosintesis-release-state` ConfigMap only after migration, all three
rollouts, and both smoke checks pass. A worker rollout failure therefore fails
the deployment and cannot replace the last-known-good release record.

## Durable job rollout controls

`JOBS_PRODUCER_ENABLED` and `JOBS_WORKER_ENABLED` are independent repository
variables. Normal deployment defaults enable both roles:

- `JOBS_PRODUCER_ENABLED=true` allows the API to create durable ingestion jobs.
- `JOBS_WORKER_ENABLED=true` allows the worker to consume eligible persisted
  jobs.
- `JOBS_WORKER_ENABLED=false` keeps the worker process deployed and ready after
  PostgreSQL connectivity and read-only durable-job queue queries, but it does
  not claim work.

Use `JOBS_PRODUCER_ENABLED=false` with the worker enabled to drain existing
backlog without creating more work, or set both switches to `false` for a full
pause. `true` producer with a disabled worker is technically supported but
unsafe for normal operation because backlog grows without a consumer. Local
application defaults remain disabled until developers opt in. API and worker
Deployments always use the same immutable backend SHA so their payload contracts
and registered handlers remain compatible.

Confirmed-plant enrichment adds a stricter rollout invariant. Its canonical
identity is accepted GBIF key plus taxonomy-validated normalized binomial, with
the validated binomial alone only when no key exists. Policy version `1` carries
separate required, locally covered, acquisition-only and final covered aspect
sets. It maps full coverage to `complete`, useful subset coverage to `partial`,
no accepted support to `failed/insufficient_evidence`, transient faults through
the shared retry telemetry, and permanent contract faults directly to `failed`.

Deploy in this order: additive migration, compatible worker and readiness check,
then the backend that makes enrichment scheduling mandatory for successful
confirmation. `JOBS_PRODUCER_ENABLED=false` is a rollout pause, not permission
to confirm without scheduling. If scheduling is unavailable, confirmation must
remain temporarily unavailable and its transaction must roll back.

Rollback should retain a backend and worker compatible with
`enrich_confirmed_plant:1` so already durable jobs can drain. If compatible
enqueueing cannot remain deployed, disable producers and confirmation rather
than weakening mandatory scheduling. Preserve additive jobs, associations,
evidence and provenance, then recover forward with a compatible image or
forward-fix migration; do not reverse migrations or discard queued work.

## How to find the deployed image tag

The `deploy.yml` step `Resolve and validate image tags` reads the
currently deployed image tag from the dev/prod Deployment when the
caller did not provide one. The same logic is exposed to operators:

```bash
kubectl -n <namespace> get deployment fotosintesis-backend \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

The tag is the value after the last `:` in the image string.
