## 1. Replace Deployment Artifacts

- [x] 1.1 Remove the Helm chart under `deploy/helm/fotosintesis` from the required deployment path
- [x] 1.2 Add plain Kubernetes base manifests under `deploy/k8s/base` for namespace, frontend Deployment and Service, backend Deployment and Service, migration Job, Kubernetes service accounts and runtime configuration references
- [x] 1.3 Add environment-specific overlays or documented placeholder substitution under `deploy/k8s` for dev/prod values derived from OpenTofu outputs
- [x] 1.4 Ensure manifests reference image registry, Workload Identity service account emails, object storage bucket, database connection information and secret names without hardcoded cloud project values
- [x] 1.5 Move any example Secret out of applied manifest directories or document it clearly as a non-applied example

## 2. Update Documentation

- [x] 2.1 Update deployment prerequisites to remove Helm and require only OpenTofu, GCP credentials, `gcloud` and `kubectl` as applicable
- [x] 2.2 Document how to generate or fill environment-specific Kubernetes values from `tofu output`
- [x] 2.3 Replace `helm upgrade --install` deployment steps with `kubectl apply` commands and rollout status checks
- [x] 2.4 Replace Helm rollback guidance with `kubectl rollout undo` for frontend/backend and explicit migration/job rollback guidance
- [x] 2.5 Document Kubernetes cleanup with `kubectl delete` and non-production infrastructure cleanup with `tofu destroy`

## 3. Align OpenSpec And Verification

- [x] 3.1 Update any existing `add-testing-deployment` design, spec or task references that still require or prefer Helm over Kubernetes manifests
- [x] 3.2 Verify deployment artifacts satisfy the `Deployment artifacts` and `Deployment consumes IaC outputs` requirements using plain Kubernetes manifests
- [x] 3.3 Run existing backend tests and confirm they continue to pass
- [x] 3.4 Run existing frontend tests and confirm they continue to pass
