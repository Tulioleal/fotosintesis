## Why

Fotosintesis has backend, frontend, OpenTofu, Kubernetes manifests, and deployment documentation, but GCP delivery remains manual and incomplete. This change establishes a production-ready, auditable deployment platform so backend, frontend, infrastructure, and production releases can move through dev and prod predictably from the monorepo.

## What Changes

- Add path-aware GitHub Actions for backend, frontend, OpenTofu, environment deployment, and production release promotion.
- Use GitHub OIDC and GCP Workload Identity Federation instead of long-lived service account keys for CI/CD authentication.
- Add a local-only OpenTofu bootstrap root that owns remote state buckets, required API enablement, GitHub OIDC providers, CI/deploy service accounts, state-bucket IAM, and foundation outputs consumed by GitHub repository variables.
- Keep dev/prod OpenTofu environment roots focused on runtime infrastructure: Artifact Registry, GKE, Cloud SQL, application object storage, Secret Manager containers, runtime workload service accounts, static frontend ingress IP, deployment outputs, and monitoring basics.
- Keep dev and prod isolated in separate GCP projects, each with its own state, Artifact Registry repository, GKE cluster, Cloud SQL instance, GCS object bucket, Secret Manager secrets, workload service accounts, and monitoring basics.
- Build backend and frontend container images with immutable Git SHA tags, auto-deploy successful `main` builds to dev, and promote selected already-built images to prod through `release.yml`.
- Expose the frontend through GKE HTTPS Ingress using a reserved static IP and GKE-managed certificate, with DNS creation documented as a manual operator step for this round.
- Connect backend and migration pods to Cloud SQL through Cloud SQL Auth Proxy sidecars using Workload Identity.
- Add a real GCS-backed backend object storage implementation for GCP environments while preserving local filesystem storage for development.
- Use Secret Manager plus External Secrets Operator for Kubernetes runtime secrets; OpenTofu manages secret containers only, while secret values are populated out of band.
- Define deploy and release verification gates: migration completion, backend/frontend rollout success, backend `/health`, and frontend public 200.
- Document bootstrap, bootstrap-state migration, secret population, DNS, deployment, production release, rollback, and cleanup procedures.

## Capabilities

### New Capabilities

- `gcp-deployment-platform`: Environment-aware GCP CI/CD, infrastructure output contract, immutable image deployment, and production release promotion for the monorepo.

### Modified Capabilities

- `testing-deployment`: Deployment requirements expand from manual OpenTofu/Kubernetes operations to automated GitHub Actions, GKE HTTPS ingress, External Secrets, Cloud SQL proxy connectivity, smoke checks, and image-based rollback documentation.
- `project-foundation`: Object storage requirements expand from a local abstraction to runtime-selectable local or GCS object storage, with GCP environments using durable GCS storage through Workload Identity.

## Impact

- Adds `.github/workflows/backend-ci.yml`, `frontend-ci.yml`, `iac.yml`, `deploy.yml`, and `release.yml`.
- Adds `infra/opentofu/bootstrap` plus focused bootstrap/state-bucket modules for remote state, project API enablement, GitHub OIDC, CI/deploy identities, state-bucket IAM, and foundation outputs.
- Refactors `infra/opentofu/envs/{dev,prod}` so bootstrap-owned resources are removed from environment roots and runtime IAM remains separate from CI/deploy foundation IAM.
- Updates `deploy/k8s` manifests and rendering values for Ingress, ManagedCertificate, External Secrets, Cloud SQL Auth Proxy, runtime storage config, and release-specific image tags.
- Adds backend GCS object storage support and associated dependencies/configuration.
- Updates deployment documentation for GCP bootstrap, GitHub repository variables/environments, DNS, secrets, dev deploy, prod release, rollback, and verification.
- Requires GCP projects, bootstrap operator/admin members, GitHub repository identity values, domain values, notification configuration, and manually populated Secret Manager versions before live deployment.
