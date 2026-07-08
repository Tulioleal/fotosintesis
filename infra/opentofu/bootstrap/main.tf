terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  alias   = "dev"
  project = var.dev_project_id
  region  = var.region
}

provider "google" {
  alias   = "prod"
  project = var.prod_project_id
  region  = var.region
}

locals {
  default_services = [
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "storage.googleapis.com",
    "monitoring.googleapis.com",
    "compute.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]

  envs = {
    dev  = { project_id = var.dev_project_id, project_number = var.dev_project_number }
    prod = { project_id = var.prod_project_id, project_number = var.prod_project_number }
  }

  # PrincipalSet paths require the numeric project number, not the project
  # ID, in the `projects/PROJECT_NUMBER` form. Each environment gets one
  # principalSet per CI/deploy SA, scoped to the configured environment.
  ci_principal_sets = {
    for env, env_cfg in local.envs : "${env}.ci" => "principalSet://iam.googleapis.com/projects/${env_cfg.project_number}/locations/global/workloadIdentityPools/${var.workload_identity_pool_id}/attribute.environment/${env}"
  }
  deploy_principal_sets = {
    for env, env_cfg in local.envs : "${env}.deploy" => "principalSet://iam.googleapis.com/projects/${env_cfg.project_number}/locations/global/workloadIdentityPools/${var.workload_identity_pool_id}/attribute.environment/${env}"
  }
}

# module "bootstrap_state_bucket" {
#   source        = "../modules/state-bucket"
#   project_id    = var.dev_project_id
#   bucket_name   = var.bootstrap_state_bucket_name
#   location      = var.state_bucket_location
#   force_destroy = var.bootstrap_state_bucket_force_destroy
#   labels        = merge(var.labels, { scope = "bootstrap" })

#   admin_principals = var.bootstrap_admin_members
# }

module "dev_state_bucket" {
  source            = "../modules/state-bucket"
  project_id        = var.dev_project_id
  bucket_name       = var.dev_state_bucket_name
  location          = var.state_bucket_location
  force_destroy     = var.dev_state_bucket_force_destroy
  labels            = merge(var.labels, { scope = "dev" })
  ci_principals     = {}
  deploy_principals = {}
  admin_principals  = { for k, v in var.bootstrap_admin_members : k => { role = "roles/storage.admin", member = v } }
}

module "prod_state_bucket" {
  source            = "../modules/state-bucket"
  project_id        = var.prod_project_id
  bucket_name       = var.prod_state_bucket_name
  location          = var.state_bucket_location
  force_destroy     = var.prod_state_bucket_force_destroy
  labels            = merge(var.labels, { scope = "prod" })
  ci_principals     = {}
  deploy_principals = {}
  admin_principals  = { for k, v in var.bootstrap_admin_members : k => { role = "roles/storage.admin", member = v } }
}

# IAM bindings for the dev and prod state buckets use direct
# google_storage_bucket_iam_member resources because the SA emails come
# from the bootstrap-iam module below, and the state-bucket module's
# for_each is resolved at plan time.
resource "google_storage_bucket_iam_member" "dev_state_bucket_ci" {
  bucket = module.dev_state_bucket.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.dev_bootstrap_iam.ci_service_account_email}"
}

resource "google_storage_bucket_iam_member" "dev_state_bucket_deploy" {
  bucket = module.dev_state_bucket.bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${module.dev_bootstrap_iam.deploy_service_account_email}"
}

resource "google_storage_bucket_iam_member" "prod_state_bucket_ci" {
  bucket = module.prod_state_bucket.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.prod_bootstrap_iam.ci_service_account_email}"
}

resource "google_storage_bucket_iam_member" "prod_state_bucket_deploy" {
  bucket = module.prod_state_bucket.bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${module.prod_bootstrap_iam.deploy_service_account_email}"
}

# Required project APIs are owned by the bootstrap root so they are not
# managed by multiple OpenTofu states.
module "dev_project_services" {
  source     = "../modules/project-services"
  project_id = var.dev_project_id
  services   = local.default_services
}

module "prod_project_services" {
  source     = "../modules/project-services"
  project_id = var.prod_project_id
  services   = local.default_services
}

# Per-project Workload Identity pools and providers. Each project gets its
# own pool because pool-level attributes include the project number. Each
# per-project provider is scoped to the matching environment's branches
# only, so a dev provider only accepts dev refs and a prod provider only
# accepts prod refs.
module "dev_workload_identity" {
  source               = "../modules/workload-identity"
  project_id           = var.dev_project_id
  project_number       = var.dev_project_number
  pool_id              = var.workload_identity_pool_id
  provider_id          = var.workload_identity_provider_id
  github_owner         = var.github_owner
  github_repository    = var.github_repository
  environment_branches = { dev = var.environment_branches.dev }
}

module "prod_workload_identity" {
  source               = "../modules/workload-identity"
  project_id           = var.prod_project_id
  project_number       = var.prod_project_number
  pool_id              = var.workload_identity_pool_id
  provider_id          = var.workload_identity_provider_id
  github_owner         = var.github_owner
  github_repository    = var.github_repository
  environment_branches = { prod = var.environment_branches.prod }
}

# CI and deploy service accounts and their project-level IAM bindings.
module "dev_bootstrap_iam" {
  source                    = "../modules/bootstrap-iam"
  project_id                = var.dev_project_id
  ci_service_account_id     = var.dev_ci_service_account_id
  deploy_service_account_id = var.dev_deploy_service_account_id
  ci_roles                  = var.dev_ci_roles
  deploy_roles              = var.dev_deploy_roles
  ci_principal_sets         = { for k, v in local.ci_principal_sets : "dev" => v if startswith(k, "dev.") }
  deploy_principal_sets     = { for k, v in local.deploy_principal_sets : "dev" => v if startswith(k, "dev.") }
}

module "prod_bootstrap_iam" {
  source                    = "../modules/bootstrap-iam"
  project_id                = var.prod_project_id
  ci_service_account_id     = var.prod_ci_service_account_id
  deploy_service_account_id = var.prod_deploy_service_account_id
  ci_roles                  = var.prod_ci_roles
  deploy_roles              = var.prod_deploy_roles
  ci_principal_sets         = { for k, v in local.ci_principal_sets : "prod" => v if startswith(k, "prod.") }
  deploy_principal_sets     = { for k, v in local.deploy_principal_sets : "prod" => v if startswith(k, "prod.") }
}
