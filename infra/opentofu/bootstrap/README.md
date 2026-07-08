# Bootstrap OpenTofu root

This root is the deployment platform's **foundation layer**. It owns the
remote-state buckets, the GitHub Workload Identity providers, the CI/deploy
service accounts, and the project API enablement that the dev/prod
environment roots need. The dev/prod environment roots are kept
runtime-only and never recreate these resources.

The bootstrap root is **local-operator-only**. It is never applied from
GitHub Actions because it owns the OIDC trust path and state buckets that
GitHub Actions itself depends on.

## What this root manages

- The bootstrap state bucket (GCS, versioning, UBLA, admin recovery IAM).
- One state bucket per environment (`dev`, `prod`).
- Required project API enablement for `dev` and `prod` (so multiple
  OpenTofu states do not try to own the same `google_project_service`
  resources).
- Per-project GitHub Workload Identity pools and providers with
  repository/owner/branch attribute conditions.
- Per-project CI and deploy service accounts with project-level IAM and
  principalSet bindings.
- State-bucket IAM bindings: CI service accounts get
  `roles/storage.objectAdmin` on their own environment's bucket; deploy
  service accounts get `roles/storage.objectViewer`; `bootstrap_admin_members`
  get `roles/storage.admin` on **every** state bucket (bootstrap, dev, and
  prod) so a single recovery group can act on any of them when CI or
  deploy identities are unavailable.

## What this root does NOT manage

- Runtime infrastructure (Artifact Registry, GKE, Cloud SQL, application
  object storage, Secret Manager containers, static IP, monitoring,
  backend/frontend workload service accounts, runtime IAM, deployment
  outputs). Those live in `infra/opentofu/envs/{dev,prod}`.
- Secret Manager **values**. Operators populate versions out of band with
  `gcloud secrets versions add`.

## One-time local apply flow

The first apply runs with local administrator credentials and local
state. After it creates the bootstrap state bucket, the operator migrates
bootstrap state to that bucket using the documented backend
configuration. The bootstrap root remains local-operator-only after
migration; GitHub Actions does not manage it.

```bash
gcloud auth application-default login
gcloud config set project "$DEV_PROJECT_ID"

cd infra/opentofu/bootstrap
# First apply: local state. Run `tofu init` without a backend block.
tofu init
tofu fmt -recursive
tofu validate
tofu plan -var-file=terraform.tfvars
tofu apply -var-file=terraform.tfvars

# Migrate bootstrap state to the bootstrap GCS bucket.
cp backend.tf.example backend.tf
# edit bucket/prefix if you used a non-default bootstrap_state_bucket_name
tofu init -migrate-state
tofu plan -var-file=terraform.tfvars   # confirm the plan is empty

# Configure GitHub repository variables from the bootstrap outputs.
# (The full list lives in docs/deployment/environment-contract.md.)
tofu output -json > bootstrap-outputs.json
```

After migration, subsequent `tofu plan/apply` for the bootstrap root
runs from local operator credentials only. The dev/prod environment
roots are applied from GitHub Actions through OIDC against the
state buckets this root created.

## Required variables

The full list of required variables is in `variables.tf`. The
`terraform.tfvars.example` file shows the minimum subset. The state
bucket names, environment names, project numbers, and GitHub repository
values are operator-controlled and never committed.
