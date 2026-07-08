variable "dev_project_id" {
  type = string
}

variable "dev_project_number" {
  type        = string
  description = "Numeric GCP project number for the dev project. Required so offline plans do not call the Google Cloud Project API."
}

variable "prod_project_id" {
  type = string
}

variable "prod_project_number" {
  type        = string
  description = "Numeric GCP project number for the prod project. Required so offline plans do not call the Google Cloud Project API."
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "github_owner" {
  type        = string
  description = "GitHub owner used in Workload Identity attribute conditions."
}

variable "github_repository" {
  type        = string
  description = "GitHub repository name used in Workload Identity attribute conditions."
}

variable "workload_identity_pool_id" {
  type    = string
  default = "github-actions"
}

variable "workload_identity_provider_id" {
  type    = string
  default = "github"
}

variable "environment_branches" {
  type        = map(list(string))
  description = "Map of environment name -> list of Git refs allowed to authenticate through the Workload Identity provider. Both dev and prod use the same map; only refs listed for the matching environment are allowed by the provider's attribute_condition."
  default = {
    dev  = ["refs/heads/main"]
    prod = ["refs/heads/main", "refs/tags/release/*"]
  }
}

variable "bootstrap_state_bucket_name" {
  type    = string
  default = "fotosintesis-bootstrap-tfstate"
}

variable "dev_state_bucket_name" {
  type    = string
  default = "fotosintesis-dev-tfstate"
}

variable "prod_state_bucket_name" {
  type    = string
  default = "fotosintesis-prod-tfstate"
}

variable "state_bucket_location" {
  type    = string
  default = "US"
}

variable "bootstrap_state_bucket_force_destroy" {
  type    = bool
  default = false
}

variable "dev_state_bucket_force_destroy" {
  type    = bool
  default = true
}

variable "prod_state_bucket_force_destroy" {
  type    = bool
  default = false
}

variable "bootstrap_admin_members" {
  type        = map(string)
  description = "Map of role label -> principal (user:..., group:..., serviceAccount:...) granted roles/storage.admin on every state bucket the bootstrap root owns (bootstrap, dev, and prod). Use this for human recovery access. The principal form is the same as the IAM member string (e.g. user:admin@example.com). Pick at least one human or group so state remains recoverable when the CI or deploy identities are unavailable."
  default     = {}
}

variable "dev_ci_service_account_id" {
  type    = string
  default = "fotosintesis-ci-dev"
}

variable "dev_deploy_service_account_id" {
  type    = string
  default = "fotosintesis-deploy-dev"
}

variable "prod_ci_service_account_id" {
  type    = string
  default = "fotosintesis-ci-prod"
}

variable "prod_deploy_service_account_id" {
  type    = string
  default = "fotosintesis-deploy-prod"
}

variable "dev_ci_roles" {
  type = set(string)
  default = [
    "roles/artifactregistry.writer",
    "roles/secretmanager.secretAccessor",
    "roles/iam.serviceAccountTokenCreator",
  ]
}

variable "dev_deploy_roles" {
  type = set(string)
  default = [
    "roles/container.developer",
    "roles/artifactregistry.reader",
    "roles/secretmanager.secretAccessor",
  ]
}

variable "prod_ci_roles" {
  type = set(string)
  default = [
    "roles/artifactregistry.writer",
    "roles/secretmanager.secretAccessor",
    "roles/iam.serviceAccountTokenCreator",
  ]
}

variable "prod_deploy_roles" {
  type = set(string)
  default = [
    "roles/container.developer",
    "roles/artifactregistry.reader",
    "roles/secretmanager.secretAccessor",
  ]
}
