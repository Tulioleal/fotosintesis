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
  description = "GitHub owner used in Workload Identity attribute conditions and as the GitHub provider's owner. The bootstrap root publishes foundation variables to repositories owned by this user or organization."
}

variable "github_repository" {
  type        = string
  description = "GitHub repository name that the bootstrap root publishes foundation variables to and that the Workload Identity attribute conditions scope to."
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
  description = "Map of environment name -> list of Git refs allowed to authenticate through the Workload Identity provider. Both dev and prod use the same map; only refs listed for the matching environment are allowed by the provider's attribute_condition. Refs containing a wildcard (`*`) are matched with CEL `matches()`; refs without a wildcard are matched with CEL `==`."
  default = {
    dev  = ["refs/heads/main"]
    prod = ["refs/heads/main", "refs/tags/release/*"]
  }
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
  description = "Map of role label -> principal (user:..., group:..., serviceAccount:...) granted roles/storage.admin on every state bucket the bootstrap root owns (dev and prod). Use this for human recovery access. The principal form is the same as the IAM member string (e.g. user:admin@example.com). Pick at least one human or group so state remains recoverable when the CI, deploy, or IaC identities are unavailable."
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

variable "dev_iac_service_account_id" {
  type    = string
  default = "fotosintesis-iac-dev"
}

variable "prod_ci_service_account_id" {
  type    = string
  default = "fotosintesis-ci-prod"
}

variable "prod_deploy_service_account_id" {
  type    = string
  default = "fotosintesis-deploy-prod"
}

variable "prod_iac_service_account_id" {
  type    = string
  default = "fotosintesis-iac-prod"
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
    "roles/container.admin",
    "roles/artifactregistry.reader",
    "roles/secretmanager.secretAccessor",
  ]
}

variable "dev_iac_roles" {
  type        = set(string)
  description = "Project IAM roles granted to the dev IaC service account. These cover the OpenTofu apply surface for the dev env root: Artifact Registry, GKE, Cloud SQL, Cloud Storage, Secret Manager container administration, Monitoring, Compute Network (covers global static IP addresses), Service Account management, and the narrowly necessary IAM bindings."
  default = [
    "roles/artifactregistry.admin",
    "roles/container.admin",
    "roles/cloudsql.admin",
    "roles/storage.admin",
    "roles/secretmanager.admin",
    "roles/monitoring.admin",
    "roles/compute.networkAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/resourcemanager.projectIamAdmin",
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
    "roles/container.admin",
    "roles/artifactregistry.reader",
    "roles/secretmanager.secretAccessor",
  ]
}

variable "prod_iac_roles" {
  type        = set(string)
  description = "Project IAM roles granted to the prod IaC service account. Same surface as the dev IaC account: Artifact Registry, GKE, Cloud SQL, Cloud Storage, Secret Manager container administration, Monitoring, Compute Network (covers global static IP addresses), Service Account management, and the narrowly necessary IAM bindings."
  default = [
    "roles/artifactregistry.admin",
    "roles/container.admin",
    "roles/cloudsql.admin",
    "roles/storage.admin",
    "roles/secretmanager.admin",
    "roles/monitoring.admin",
    "roles/compute.networkAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/resourcemanager.projectIamAdmin",
  ]
}
