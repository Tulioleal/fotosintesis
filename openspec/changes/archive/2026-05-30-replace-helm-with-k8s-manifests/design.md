## Context

The `add-testing-deployment` implementation currently provides the GKE workload deployment as a Helm chart under `deploy/helm/fotosintesis`. The requirement permits either Kubernetes/GKE manifests or Helm, and the MVP does not need Helm-specific templating, release management or chart packaging.

This change keeps cloud infrastructure in OpenTofu and replaces the workload deployment layer with plain Kubernetes manifests that can be reviewed and applied with `kubectl`.

## Goals / Non-Goals

**Goals:**

- Remove Helm as a required deployment dependency.
- Provide static Kubernetes manifests for namespace, frontend, backend, services, migration job, Workload Identity service accounts and runtime configuration references.
- Support environment-specific deployment through overlays or documented placeholder substitution using OpenTofu outputs.
- Keep real secrets out of source control and outside rendered deployment paths.
- Update deployment, verification, rollback and cleanup documentation to use `kubectl` and OpenTofu.

**Non-Goals:**

- No changes to provisioned GCP infrastructure or OpenTofu modules unless outputs need documentation alignment.
- No new application features, API changes or database schema changes.
- No introduction of another deployment tool that replaces Helm, such as Argo CD, Flux or Kustomize as a required dependency.

## Decisions

- Use plain Kubernetes YAML under `deploy/k8s` instead of Helm. This favors direct `kubectl apply` workflows, lowers the prerequisite set and keeps the MVP deployment artifacts easy to inspect.
- Organize manifests as `deploy/k8s/base` plus optional environment directories or documented substitution inputs. This preserves a clean shared manifest set while allowing dev/prod values to come from OpenTofu outputs.
- Keep placeholders for image references, workload identity service account emails, bucket names, database connection values and secret names out of hardcoded project-specific values. Deployment documentation will show how to generate or fill environment-specific values from `tofu output`.
- Represent non-secret runtime values with ConfigMaps or documented environment variables, and reference secrets by Kubernetes Secret name only. Example Secret content, if retained, will be moved outside applied manifest paths or labeled as non-applied example documentation.
- Use Kubernetes Deployment rollout commands for application rollback and explicit migration-job guidance for database rollback. This avoids Helm release rollback semantics and makes migration recovery an operator decision tied to the actual migration behavior.

## Risks / Trade-offs

- Plain manifests provide less parameterization than Helm -> Keep only the needed substitution points and document their source OpenTofu outputs.
- `kubectl apply` does not provide Helm release history -> Use Deployment revision history and documented `kubectl rollout undo` commands for frontend/backend rollback.
- Migration jobs are not automatically reversible -> Document backup, forward-fix and manual rollback guidance rather than implying automatic rollback safety.
- Environment overlays can drift -> Keep base manifests authoritative and restrict environment-specific files to values, patches or generated outputs.

## Migration Plan

- Remove `deploy/helm/fotosintesis` from the deployment path.
- Add `deploy/k8s/base` manifests for common Kubernetes resources and optional environment-specific files under `deploy/k8s/dev` and `deploy/k8s/prod` or documented generated values.
- Update docs to apply infrastructure with OpenTofu, derive deployment values from `tofu output`, apply Kubernetes resources with `kubectl apply` and verify rollout status.
- Update rollback docs to use `kubectl rollout undo` for Deployments and documented migration-job recovery guidance.
- Update cleanup docs to delete Kubernetes resources with `kubectl delete` and destroy cloud resources with `tofu destroy` for non-production environments.

## Open Questions

- None.
