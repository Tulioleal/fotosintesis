# Bootstrap

The `infra/opentofu/bootstrap` root is the deployment platform's
**foundation layer**. It owns the resources the dev/prod environment roots
and the GitHub Actions workflows depend on:

- The bootstrap state bucket and the per-environment state buckets
  (`dev`, `prod`) with versioning and uniform bucket-level access.
- Required project API enablement for `dev` and `prod` (so multiple
  OpenTofu states do not try to own the same `google_project_service`
  resources).
- Per-project GitHub Workload Identity pools and providers with
  repository/owner/branch attribute conditions.
- Per-project CI and deploy service accounts with project-level IAM and
  principalSet impersonation bindings.
- State-bucket IAM bindings: CI service accounts get
  `roles/storage.objectAdmin` on their own environment's bucket; deploy
  service accounts get `roles/storage.objectViewer`; `bootstrap_admin_members`
  get `roles/storage.admin` on every state bucket (bootstrap, dev, and
  prod) so a single recovery group can act on any of them when CI or
  deploy identities are unavailable.

The bootstrap root is **local-operator-only**. It is never applied from
GitHub Actions because it owns the OIDC trust path and state buckets
that GitHub Actions itself depends on.

## Prerequisites

- `tofu` (OpenTofu) `>= 1.8.0`.
- `gcloud` configured with administrator credentials for both the dev
  and prod GCP projects.
- The numeric project numbers for the dev and prod projects. Use
  `gcloud projects describe PROJECT_ID --format='value(projectNumber)'`.

## First-time local apply

```bash
gcloud auth application-default login
gcloud config set project "$DEV_PROJECT_ID"

cd infra/opentofu/bootstrap
# First apply: local state. There must be no `backend` block in main.tf
# at this point (the bootstrap root intentionally has none).
tofu init
tofu fmt -recursive
tofu validate
tofu plan -var-file=terraform.tfvars
tofu apply -var-file=terraform.tfvars
```

The first apply creates:

- The bootstrap state bucket and the dev/prod state buckets.
- The CI and deploy service accounts in each project.
- The Workload Identity pools and providers in each project.
- The required project APIs in each project.
- The state-bucket IAM bindings and the CI/deploy project IAM roles.

## Migrate bootstrap state to its GCS backend

After the first apply has created the bootstrap state bucket, migrate
bootstrap state from the local OpenTofu state file to the bootstrap GCS
backend so subsequent local applies read and write state from the
correct location.

```bash
# Create a backend.tf file from the example template.
cp backend.tf.example backend.tf
# Edit the bucket name if you used a non-default
# `bootstrap_state_bucket_name` in terraform.tfvars.
tofu init -migrate-state
tofu plan -var-file=terraform.tfvars   # confirm the plan is empty
```

After migration, subsequent `tofu plan/apply` for the bootstrap root
runs from local operator credentials only. The dev/prod environment
roots are applied from GitHub Actions through OIDC against the state
buckets this root created.

## Configure GitHub from bootstrap outputs

```bash
tofu output -json > bootstrap-outputs.json
```

The full mapping from bootstrap outputs to GitHub repository/environment
variables is in `github-variables.md`. The bootstrap `README.md` has a
short summary.

## Recovery

`bootstrap_admin_members` defines the principals that have
`roles/storage.admin` on every state bucket. Keep at least one human
or group in that map so a single recovery group can read or rewrite any
state bucket when CI or deploy identities are unavailable.

To recover after losing the CI or deploy identities:

1. Authenticate as a `bootstrap_admin_members` principal.
2. Re-run `tofu plan/apply` for the bootstrap root; the principalSets
   and the bootstrap-managed service accounts are still owned by the
   bootstrap state, so a plan against the migrated backend reflects the
   last-applied state.
3. If a service account was deleted, recreate it with the same
   `account_id` and let the bootstrap root re-apply its IAM bindings.
4. If the bootstrap state itself was lost, restore the state file from
   the GCS bucket's version history, then re-apply.

## What this root does NOT manage

- Runtime infrastructure (Artifact Registry, GKE, Cloud SQL, application
  object storage, Secret Manager containers, static IP, monitoring,
  backend/frontend workload service accounts, runtime IAM, deployment
  outputs). Those live in `infra/opentofu/envs/{dev,prod}`.
- Secret Manager **values**. Operators populate versions out of band with
  `gcloud secrets versions add`.
