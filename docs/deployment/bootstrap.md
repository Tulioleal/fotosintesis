# Bootstrap

The `infra/opentofu/bootstrap` root is the deployment platform's
**foundation layer**. It owns the resources the dev/prod environment roots
and the GitHub Actions workflows depend on:

- The per-environment state buckets (`dev`, `prod`) with versioning and
  uniform bucket-level access. The bootstrap root does not own a state
  bucket for its own state; bootstrap state stays on the operator
  workstation.
- Required project API enablement for `dev` and `prod` (so multiple
  OpenTofu states do not try to own the same `google_project_service`
  resources).
- Per-project GitHub Workload Identity pools and providers with
  repository/owner/branch attribute conditions.
- Per-project CI, deploy, and IaC service accounts with project-level
  IAM and principalSet impersonation bindings. The IaC account is the
  dedicated identity for OpenTofu applies; the CI account stays limited
  to image build/push and the deploy account stays limited to GKE
  deploys.
- State-bucket IAM bindings: each environment's CI and IaC service
  accounts get `roles/storage.objectAdmin` on their own bucket; the
  deploy service account gets `roles/storage.objectViewer`;
  `bootstrap_admin_members` get `roles/storage.admin` on every state
  bucket so a single recovery group can act on any of them when CI,
  deploy, or IaC identities are unavailable.
- Foundation GitHub repository variables published to the target
  repository (see [the variables table](#foundation-repository-variables)).

The bootstrap root is **local-operator-only** and **local-state-only**.
It is never applied from GitHub Actions because it owns the OIDC trust
path, the state buckets, and the GitHub repository-variable publication
that GitHub Actions itself depends on.

## Prerequisites

- `tofu` (OpenTofu) `>= 1.8.0`.
- `gcloud` configured with administrator credentials for both the dev
  and prod GCP projects.
- The numeric project numbers for the dev and prod projects. Use
  `gcloud projects describe PROJECT_ID --format='value(projectNumber)'`.
- A fine-grained GitHub personal access token (PAT) with **Actions
  variables: Write** permission restricted to the target repository.
  Export it as `GITHUB_TOKEN` in the operator shell before running
  `tofu apply`. The token is read by the GitHub provider from the
  environment variable; it is never written to `terraform.tfvars`,
  OpenTofu outputs, or state.

## First-time local apply

```bash
gcloud auth application-default login
gcloud config set project "$DEV_PROJECT_ID"

cd infra/opentofu/bootstrap
tofu init
tofu fmt -recursive
tofu validate
tofu plan -var-file=terraform.tfvars
tofu apply -var-file=terraform.tfvars
```

The first apply creates:

- The `dev` and `prod` state buckets.
- The CI, deploy, and IaC service accounts in each project.
- The Workload Identity pools and providers in each project.
- The required project APIs in each project.
- The state-bucket IAM bindings and the CI/deploy/IaC project IAM
  roles.
- The foundation GitHub repository variables on the target repository.

## Bootstrap state stays local

There is no `tofu init -migrate-state` for the bootstrap root: the
bootstrap root has no `backend` block and does not own a state bucket.
The `terraform.tfstate` file created by the first apply remains on the
operator workstation and is the source of truth for the bootstrap trust
path (WIF pool/provider, CI/deploy/IaC SAs, state-bucket IAM).

Subsequent `tofu plan/apply` for the bootstrap root reads and writes the
same local `terraform.tfstate`. The recommended local layout is:

```bash
# In a private, backed-up directory on the operator workstation.
mkdir -p ~/fotosintesis-bootstrap-state
cp infra/opentofu/bootstrap/terraform.tfstate ~/fotosintesis-bootstrap-state/
```

If the local state file is lost, recovery requires re-applying the
bootstrap root from scratch. `bootstrap_admin_members` is the recovery
path: those principals can read and rewrite the dev/prod state buckets
and re-create the bootstrap-owned resources. Without admin members,
state loss is unrecoverable.

## Foundation repository variables

The bootstrap root publishes the following GitHub repository variables
to the target repository through the GitHub provider. The iac.yml
post-apply sync jobs own the per-environment outputs and runtime
configuration; bootstrap owns only this foundation-variable namespace.

| Variable | Source |
| --- | --- |
| `DEV_TF_STATE_BUCKET` | bootstrap `dev_state_bucket` output |
| `PROD_TF_STATE_BUCKET` | bootstrap `prod_state_bucket` output |
| `DEV_GCP_PROJECT_ID` | bootstrap `dev_project_id` input |
| `PROD_GCP_PROJECT_ID` | bootstrap `prod_project_id` input |
| `DEV_GCP_PROJECT_NUMBER` | bootstrap `dev_project_number` input |
| `PROD_GCP_PROJECT_NUMBER` | bootstrap `prod_project_number` input |
| `DEV_CI_SERVICE_ACCOUNT_EMAIL` | bootstrap `dev_ci_service_account_email` output |
| `PROD_CI_SERVICE_ACCOUNT_EMAIL` | bootstrap `prod_ci_service_account_email` output |
| `DEV_DEPLOY_SERVICE_ACCOUNT_EMAIL` | bootstrap `dev_deploy_service_account_email` output |
| `PROD_DEPLOY_SERVICE_ACCOUNT_EMAIL` | bootstrap `prod_deploy_service_account_email` output |
| `DEV_IAC_SERVICE_ACCOUNT_EMAIL` | bootstrap `dev_iac_service_account_email` output |
| `PROD_IAC_SERVICE_ACCOUNT_EMAIL` | bootstrap `prod_iac_service_account_email` output |
| `DEV_WIF_PROVIDER_ID` | bootstrap `dev_wif_provider_id` output |
| `PROD_WIF_PROVIDER_ID` | bootstrap `prod_wif_provider_id` output |
| `DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL` | bootstrap `prod_ci_service_account_email` output |

A second `tofu apply` is idempotent: the GitHub provider's
`github_actions_variable` resource creates-or-updates each variable
without duplicating it.

## Recovery

`bootstrap_admin_members` defines the principals that have
`roles/storage.admin` on every state bucket. Keep at least one human
or group in that map so a single recovery group can read or rewrite any
state bucket when CI, deploy, or IaC identities are unavailable.

To recover after losing the CI, deploy, or IaC identities:

1. Authenticate as a `bootstrap_admin_members` principal.
2. Re-run `tofu plan/apply` for the bootstrap root; the principalSets
   and the bootstrap-managed service accounts are still owned by the
   bootstrap state, so a plan against the local state reflects the
   last-applied state.
3. If a service account was deleted, recreate it with the same
   `account_id` and let the bootstrap root re-apply its IAM bindings.
4. If the bootstrap state itself was lost, restore the `terraform.tfstate`
   from the operator workstation's backup directory, then re-apply.

## What this root does NOT manage

- Runtime infrastructure (Artifact Registry, GKE, Cloud SQL, application
  object storage, Secret Manager containers, static IP, monitoring,
  backend/frontend workload service accounts, runtime IAM, deployment
  outputs). Those live in `infra/opentofu/envs/{dev,prod}`.
- Runtime configuration, DNS settings, notification email, model
  selection, or secret values. The iac.yml post-apply sync jobs own
  the per-environment outputs.
- Secret Manager **values**. Operators populate versions out of band with
  `gcloud secrets versions add`.
