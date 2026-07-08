variable "project_id" {
  type        = string
  description = "GCP project ID where the CI/deploy service accounts live."
}

variable "ci_service_account_id" {
  type        = string
  description = "Short ID for the CI service account. Becomes ci_service_account_id@{project_id}.iam.gserviceaccount.com."
}

variable "deploy_service_account_id" {
  type        = string
  description = "Short ID for the deploy service account. Becomes deploy_service_account_id@{project_id}.iam.gserviceaccount.com."
}

variable "ci_roles" {
  type        = set(string)
  description = "Project IAM roles granted to the CI service account. Use this for Artifact Registry push, Secret Manager access metadata, and any other CI-only permissions."
}

variable "deploy_roles" {
  type        = set(string)
  description = "Project IAM roles granted to the deploy service account. Use this for GKE deploy, Artifact Registry read, and any other deploy-only permissions."
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
