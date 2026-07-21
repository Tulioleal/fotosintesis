# Rollback

The platform supports image-tag rollback and Kubernetes rollout undo.
Database migrations are forward-only for this round; incompatible
migration failures require a database restore or a reviewed
forward-fix migration.

The image-listing command below uses `PROD_ARTIFACT_REGISTRY_URL` and
`PROD_GCP_PROJECT_ID`. Bootstrap publishes the project ID, and a
successful prod `iac.yml` apply publishes the registry URL. Run that
apply first if either variable is missing. Use the corresponding `DEV_*`
variables when investigating a dev rollback.

## Image tag rollback

To roll back the backend/worker image pair or frontend to a previously deployed
40-character Git commit SHA without changing any other infrastructure:

1. Identify the previous tag from the deploy workflow summary of the
   release you want to revert, or by listing image tags in the prod
   Artifact Registry:
   ```bash
   gcloud artifacts docker tags list "$PROD_ARTIFACT_REGISTRY_URL/backend" \
     --project="$PROD_GCP_PROJECT_ID" --format='value(tag)' | sort
   ```
2. Dispatch `deploy.yml` against the target environment with both
   40-character SHAs:
   - `environment: prod` (or `dev`)
   - `backend_image_tag: <previous SHA>`
   - `frontend_image_tag: <previous SHA>`

The image is already in the registry (it was the previous production
release), so no rebuild or promotion is needed. The deploy workflow verifies
the SHA format, renders manifests, runs migrations, and deploys the API and
worker from the same backend SHA.

## `kubectl rollout undo`

For an immediate rollback that uses Kubernetes' own revision history
without changing the image tag input:

```bash
kubectl -n <namespace> rollout undo deployment/fotosintesis-backend
kubectl -n <namespace> rollout undo deployment/fotosintesis-worker
kubectl -n <namespace> rollout undo deployment/fotosintesis-frontend
```

This reverts each Deployment to its previous ReplicaSet's
`spec.template.spec.containers[0].image`. The image must still exist in
the Artifact Registry; if a previous release cleaned up old tags, this
command fails with `ImagePullBackOff`.

The default `revisionHistoryLimit` on the Deployments is `5`, so up to
five prior revisions are available. Older revisions are garbage-collected
by Kubernetes and require a fresh image tag.

## Migration limitations

Migrations are forward-only. The deploy workflow runs a one-shot migration Job
**before** the backend rollout and waits for its native Kubernetes `Complete`
condition. The restartable Cloud SQL proxy init sidecar exits with the Pod, so
Alembic success completes the Job without workflow-managed deletion. The backend
rollout only proceeds after that completion. This guarantees the new backend
never runs against an out-of-date schema.

Incompatible migration failures (a migration that adds a column the new
backend does not expect, or removes data the new backend relies on) are
not recoverable by image rollback. Two options:

1. **Restore from backup** - use the Cloud SQL automated backup or a
   point-in-time recovery to roll the database back to a state compatible
   with the previous image tag. The new image will not run because the
   migration has not been undone; redeploy the previous backend/frontend
   SHAs and confirm the runtime.

2. **Forward-fix migration** - create a new Alembic migration that
   brings the schema back to a state compatible with the image you want
   to keep. Build, push, and deploy the new image with the new
   migration. This is the only path that does not require a database
   restore but it requires a code change.

The deploy workflow does not attempt to undo a migration. It always
runs `alembic upgrade head`. Operators must pick restore or forward-fix
based on the data loss tolerance for the affected environment.

The API and worker must use the same backend SHA and support every persisted
payload version still pending or processing. Before an image rollback, verify
that the previous image is compatible with the current additive schema and
retains the required handlers. If it is not, keep producers disabled and ship a
forward-fix image/migration rather than deploying mismatched API and worker
versions.

## Operator procedure

For a production incident:

1. Stop further deploys by cancelling any in-flight
   `release.yml` / `deploy.yml` runs.
2. Disable new enqueueing with `JOBS_PRODUCER_ENABLED=false`. If consumption
   must also stop, set `JOBS_WORKER_ENABLED=false`; these controls are
   independent and the disabled worker remains ready after its database check.
3. Identify the last known-good backend and frontend SHAs from the
   release summary of the last successful run, or from
   `kubectl -n <namespace> get deploy -o jsonpath='{..image}'`.
4. If the database and persisted payloads are compatible, dispatch `deploy.yml`
   with the previous SHAs. Wait for the rollout and smoke checks to
   pass.
5. If the database or payload contracts are not compatible, restore from backup
   or write a forward-fix migration per the migration limitations
   above.
6. Confirm the backend, worker, and frontend rollouts. A failed worker rollout
   fails the workflow and does not update `fotosintesis-release-state`.
7. Record the rollback in the runbook/incident report and capture the
   relevant workflow run URLs.
