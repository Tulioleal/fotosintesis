# Cleanup

The platform separates **non-production cleanup** (safe to destroy) from
**production safeguards** (deletion-protected).

## Non-production cleanup

The dev environment uses `deletion_protection = false` everywhere
deletion protection is supported (Cloud SQL, GKE, application
object-storage bucket, state buckets). The dev state bucket uses
`force_destroy = true` so a `tofu destroy` can remove a non-empty
bucket. The bootstrap state bucket is **never** force-destroyed.

To tear down a dev environment:

```bash
cd infra/opentofu/envs/dev
tofu init
tofu destroy
```

This removes:

- The Artifact Registry repository.
- The GKE cluster and node pools.
- The Cloud SQL instance and the application database.
- The application object-storage bucket (with `force_destroy = true`).
- The Secret Manager secret **containers** (versions must be
  destroyed separately if the operator wants to remove all data).
- The frontend static IP.
- The runtime workload service accounts and their IAM bindings.

The bootstrap-managed resources (state bucket, Workload Identity pool
and provider, CI/deploy service accounts, project API enablement) are
**not** removed by the dev env destroy. They live in the bootstrap
root and are reused when a new dev environment is created.

## Production safeguards

The prod environment uses `deletion_protection = true` on every resource
that supports it:

- `deletion_protection = true` on the GKE cluster and Cloud SQL
  instance.
- `force_destroy = false` on the prod state bucket and the application
  object-storage bucket.
- The prod GitHub Environment requires reviewer approval for any
  `iac.yml` or `release.yml` dispatch.

To tear down a production environment:

1. Confirm the decision with the production operators and capture the
   approval in writing.
2. Run `iac.yml` with `environment: prod` and `tofu_command: plan`
   first. Inspect the planned changes carefully.
3. Update the prod env's `terraform.tfvars` to set
   `deletion_protection = false` and `storage_force_destroy = true`,
   then plan/apply. The change is also reviewer-gated.
4. Dispatch `iac.yml` with `environment: prod`,
   `tofu_command: apply`, and the destruction-safe variables. The
   reviewer must approve the run.
5. The OpenTofu `apply` will then succeed in tearing down the
   production runtime resources. Secret Manager secret containers are
   not auto-destroyed; remove them with `gcloud secrets delete <name>`
   if desired.

## Bootstrap state

The bootstrap state bucket is the deployment platform's trust path. It
is never force-destroyed, even on dev environments. To reset the
bootstrap state:

1. Authenticate as a `bootstrap_admin_members` principal.
2. `tofu destroy` in `infra/opentofu/bootstrap`. The bootstrap state
   bucket has `force_destroy = false`; if the bucket is non-empty the
   destroy will fail, by design.
3. Manually empty the bootstrap state bucket with
   `gcloud storage rm -r gs://<bucket>/...` if you are absolutely sure
   you want to start over.
4. Re-apply the bootstrap root with the new `terraform.tfvars` and
   migrate state again as documented in `bootstrap.md`.

## DNS records

The frontend static IP is created in the env roots. Removing the IP
does not remove the DNS A record that points at it. Operators who
destroy a production environment must also remove the matching DNS A
record (and any DNS-only validation records) so the hostname stops
resolving to a stale IP.
