# Rollback

The platform supports image-tag rollback and Kubernetes rollout undo.
Database migrations are forward-only for this round; incompatible
migration failures require a database restore or a reviewed
forward-fix migration.

## Image tag rollback

To roll back the backend or frontend to a previously deployed 40-character
Git commit SHA without changing any other infrastructure:

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
release), so no rebuild or promotion is needed. The deploy workflow
verifies the SHA format, renders manifests, and applies them.

## `kubectl rollout undo`

For an immediate rollback that uses Kubernetes' own revision history
without changing the image tag input:

```bash
kubectl -n <namespace> rollout undo deployment/fotosintesis-backend
kubectl -n <namespace> rollout undo deployment/fotosintesis-frontend
```

This reverts the Deployment to its previous ReplicaSet's
`spec.template.spec.containers[0].image`. The image must still exist in
the Artifact Registry; if a previous release cleaned up old tags, this
command fails with `ImagePullBackOff`.

The default `revisionHistoryLimit` on both Deployments is `5`, so up to
five prior revisions are available. Older revisions are garbage-collected
by Kubernetes and require a fresh image tag.

## Migration limitations

Migrations are forward-only. The deploy workflow runs migrations
**before** the backend rollout and waits for the migration Job to
complete. The backend rollout only proceeds once the migration Job has
reported `Complete`. This guarantees the new backend never runs against
an out-of-date schema.

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

## Operator procedure

For a production incident:

1. Stop further deploys by cancelling any in-flight
   `release.yml` / `deploy.yml` runs.
2. Identify the last known-good backend and frontend SHAs from the
   release summary of the last successful run, or from
   `kubectl -n <namespace> get deploy -o jsonpath='{..image}'`.
3. If the database is in a compatible state, dispatch `deploy.yml`
   with the previous SHAs. Wait for the rollout and smoke checks to
   pass.
4. If the database is not in a compatible state, restore from backup
   or write a forward-fix migration per the migration limitations
   above.
5. Record the rollback in the runbook/incident report and capture the
   relevant workflow run URLs.
