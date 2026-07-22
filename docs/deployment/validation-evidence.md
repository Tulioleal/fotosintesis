# Validation Evidence

This file is the evidence template the operator fills in after running
the dev end-to-end and prod release flows. Each gate should report
`pass` and reference a real GitHub Actions run URL (or an approved
dry-run URL).

Use the table format below. Replace `<run-url>` and `<commit-sha>`
placeholders with the actual values from the run.

## Sandbox dry-run

CI workflows do not write to this file. Operators record the relevant
run URLs and results after the first push to `main` with the workflow
files.

| Check | Result | Run URL | Notes |
| --- | --- | --- | --- |
| `tofu fmt -recursive -check` | pass | <run-url> | iac.yml format job. |
| `tofu validate` (dev) | pass | <run-url> | iac.yml validate step. |
| `tofu validate` (prod) | pass | <run-url> | iac.yml validate step. |
| `tofu plan -refresh=false` (dev) | partial | <run-url> | Offline shape check, no live authentication. |
| `tofu plan -refresh=false` (prod) | partial | <run-url> | Offline shape check, no live authentication. |
| Backend lint + tests | pass | <run-url> | backend-ci.yml validate job. |
| Frontend lint + typecheck + tests + build | pass | <run-url> | frontend-ci.yml validate job. |
| Actionlint | pass | <run-url> | actionlint.yml job. |

## Dev end-to-end

| Gate | Result | Run URL / Detail | Notes |
| --- | --- | --- | --- |
| Bootstrap dev project API enablement | pass | <bootstrap-output or run-url> | Document project number. |
| Bootstrap dev state bucket created | pass | <bucket-name> | Bootstrap output `dev_state_bucket`. |
| Foundation variables published | pass | <bootstrap apply or variable list> | Bootstrap publishes the `DEV_*` foundation variables. |
| Dev output variables synchronized | pass | <iac apply run-url> | The successful IaC apply publishes `DEV_ARTIFACT_REGISTRY_URL`, storage, static IP, and other non-sensitive outputs. |
| Secret Manager entries present | pass | <secret-list or run-url> | At least one version per container. |
| Dev IaC `iac.yml` plan/apply | pass | <run-url> | Uses `DEV_IAC_SERVICE_ACCOUNT_EMAIL`; successful apply runs output sync. |
| Backend image build (`backend:<sha>`) | pass | <run-url> | backend-ci.yml build job. |
| Frontend image build (`frontend:<sha>`) | pass | <run-url> | frontend-ci.yml build job (skip if path filter excluded it). |
| Backend image tag = `<sha>` | pass | <sha> | From `Resolve and validate image tags` summary. |
| Frontend image tag = `<sha>` | pass | <sha> | From `Resolve and validate image tags` summary. |
| Dev Artifact Registry immutable tags | pending | <repository describe output> | Expect `dockerConfig.immutableTags=True`. |
| Kubernetes server-side admission | pending | <run-url or command output> | All backend, frontend, migration, and worker manifests. |
| Worker rollout | pending | <run-url> | `fotosintesis-worker` rollout completed. |
| Worker `/ready` probe | pending | <run-url> | Worker container reported ready after queue validation. |
| Producer mode | pending | `JOBS_PRODUCER_ENABLED=<value>` | Normal operation requires `true`. |
| Migration Job completion | pass | <run-url> | deploy.yml migration step. |
| Backend rollout | pass | <run-url> | deploy.yml rollout step. |
| Frontend rollout | pass | <run-url> | deploy.yml rollout step. |
| Required provider API keys projected | pass | <run-url> | deploy.yml required-keys step. |
| Backend in-cluster smoke (`/health`) | pass | <run-url> | deploy.yml backend-smoke step. |
| Frontend public smoke (200) | pass | <run-url> | deploy.yml frontend-smoke step. hostname-https requires DNS; ip-http requires the static IP to be reachable. |

## Prod release

| Gate | Result | Run URL / Detail | Notes |
| --- | --- | --- | --- |
| Bootstrap prod project API enablement | pass | <bootstrap-output or run-url> | Document project number. |
| Bootstrap prod state bucket created | pass | <bucket-name> | Bootstrap output `prod_state_bucket`. |
| Foundation variables published | pass | <bootstrap apply or variable list> | Bootstrap publishes the `PROD_*` foundation variables. |
| GitHub prod environment reviewer configured | pass | <reviewer-list> | Required by GitHub Environment protection. |
| Secret Manager entries present | pass | <secret-list or run-url> | At least one version per container. |
| DNS points at the prod static IP | pass | <hostname + lookup> | Required for `hostname-https`. |
| Prod IaC `iac.yml` plan/apply | pass | <run-url> | Uses `PROD_IAC_SERVICE_ACCOUNT_EMAIL`; successful apply runs output sync. |
| Prod output variables synchronized | pass | <iac apply run-url> | Publishes `PROD_ARTIFACT_REGISTRY_URL`, storage, static IP, and other non-sensitive outputs. |
| Prod Artifact Registry immutable tags | pending | <repository describe output> | Expect `dockerConfig.immutableTags=True`. |
| Verify source images (dev tags) | pass | <run-url> | release.yml verify-source-images. |
| Promote images to prod registry | pass | <run-url> | release.yml promote-images. |
| Deploy prod (manifests) | pass | <run-url> | release.yml deploy-prod. |
| Kubernetes server-side admission | pending | <run-url> | All workload manifests admitted. |
| Worker rollout | pending | <run-url> | `fotosintesis-worker` rollout completed. |
| Worker `/ready` probe | pending | <run-url> | Worker container reported ready after queue validation. |
| Producer mode | pending | `JOBS_PRODUCER_ENABLED=<value>` | Normal operation requires `true`. |
| Migration Job completion | pass | <run-url> | deploy.yml migration step. |
| Backend rollout | pass | <run-url> | deploy.yml rollout step. |
| Frontend rollout | pass | <run-url> | deploy.yml rollout step. |
| Required provider API keys projected | pass | <run-url> | deploy.yml required-keys step. |
| Backend in-cluster smoke (`/health`) | pass | <run-url> | deploy.yml backend-smoke step. |
| Frontend public smoke (HTTPS 200) | pass | <run-url> | deploy.yml frontend-smoke step. |
| Release summary | pass | <run-url> | release.yml summary job. Records backend tag, frontend tag, source registry, prod registry, GKE cluster, namespace, and per-gate results. |

## Sign-off

| Role | Name | Date | Notes |
| --- | --- | --- | --- |
| Operator | | | Confirms live runs. |
| Reviewer | | | Confirms dev and prod evidence. |
