# Cleanup

The platform separates **non-production cleanup** (safe to destroy) from
**production safeguards** (deletion-protected).

## Non-production cleanup

The dev environment uses `deletion_protection = false` everywhere
deletion protection is supported (Cloud SQL, GKE, application
object-storage bucket, state buckets). The dev state bucket uses
`force_destroy = true` so a `tofu destroy` can remove a non-empty
bucket. The bootstrap root does not own a state bucket — bootstrap
state stays on the operator workstation, so there is no bootstrap
state to clean up.

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

The bootstrap-managed resources (state buckets, Workload Identity pool
and provider, CI/deploy/IaC service accounts, project API enablement)
are **not** removed by the dev env destroy. They live in the bootstrap
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

The bootstrap root is local-state-only. Bootstrap state lives on the
operator workstation (the recommended layout is a private, backed-up
directory such as `~/fotosintesis-bootstrap-state/`), not in a GCS
bucket. To reset the bootstrap state:

1. Authenticate as a `bootstrap_admin_members` principal.
2. `tofu destroy` in `infra/opentofu/bootstrap`. Because the bootstrap
   root does not own a state bucket, the destroy will not need to
   empty one. (Destroying the bootstrap root removes the
   Workload Identity pool, provider, and CI/deploy/IaC service
   accounts, but the dev/prod state buckets are owned by the bootstrap
   root and are removed along with everything else.)
3. Delete the local `terraform.tfstate` and `terraform.tfstate.backup`
   files if you want to start over with no prior state.
4. Re-apply the bootstrap root with the new `terraform.tfvars` and a
   fresh `GITHUB_TOKEN` in the operator's environment.

If the local state file is lost, recovery requires re-applying the
bootstrap root from scratch. `bootstrap_admin_members` is the recovery
path: those principals can read and rewrite the dev/prod state buckets
and re-create the bootstrap-owned resources. Without admin members,
state loss is unrecoverable.

## DNS records

The frontend static IP is created in the env roots. Removing the IP
does not remove the DNS A record that points at it. Operators who
destroy a production environment must also remove the matching DNS A
record (and any DNS-only validation records) so the hostname stops
resolving to a stale IP.
