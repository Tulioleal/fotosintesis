variable "project_id" {
  type        = string
  description = "GCP project ID where the CI/deploy/IaC service accounts live."
}

variable "ci_service_account_id" {
  type        = string
  description = "Short ID for the CI service account. Becomes ci_service_account_id@{project_id}.iam.gserviceaccount.com."
}

variable "deploy_service_account_id" {
  type        = string
  description = "Short ID for the deploy service account. Becomes deploy_service_account_id@{project_id}.iam.gserviceaccount.com."
}

variable "iac_service_account_id" {
  type        = string
  description = "Short ID for the IaC service account. Becomes iac_service_account_id@{project_id}.iam.gserviceaccount.com. The IaC account owns OpenTofu applies for the environment; it is separate from the image-CI account so apply permissions can grow without touching image-build permissions."
}

variable "ci_roles" {
  type        = set(string)
  description = "Project IAM roles granted to the CI service account. Keep this limited to image build/push roles (Artifact Registry writer, Secret Manager accessor, Service Account Token Creator)."
}

variable "deploy_roles" {
  type        = set(string)
  description = "Project IAM roles granted to the deploy service account. Keep this limited to GKE deployment roles (Container Developer, Artifact Registry reader, Secret Manager accessor)."
}

variable "iac_roles" {
  type        = set(string)
  description = "Project IAM roles granted to the IaC service account. These are the roles an OpenTofu apply for the environment needs: Artifact Registry admin, GKE admin, Cloud SQL admin, Cloud Storage admin, Secret Manager admin, Monitoring admin, Compute Global Address admin, Service Account admin/user, and the narrowly necessary IAM bindings."
}

variable "ci_principal_sets" {
  type        = map(string)
  default     = {}
  description = "Map of label -> principalSet that may impersonate the CI service account. Populated by the bootstrap root with per-environment principalSet paths."
}

variable "deploy_principal_sets" {
  type        = map(string)
  default     = {}
  description = "Map of label -> principalSet that may impersonate the deploy service account. Populated by the bootstrap root with per-environment principalSet paths."
}

variable "iac_principal_sets" {
  type        = map(string)
  default     = {}
  description = "Map of label -> principalSet that may impersonate the IaC service account. Populated by the bootstrap root with per-environment principalSet paths."
}
