terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    github = {
      source  = "integrations/github"
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

# The GitHub provider is configured with an explicit `owner` argument. The
# token itself is read from the GITHUB_TOKEN environment variable so it
# never lands in terraform.tfvars, OpenTofu state, or outputs. Operators
# must export a fine-grained personal access token (PAT) restricted to the
# target repository and to "Actions variables: Write" before running the
# bootstrap apply.
provider "github" {
  owner = var.github_owner
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
  # principalSet per identity (CI, deploy, IaC), scoped to the configured
  # environment.
  ci_principal_sets = {
    for env, env_cfg in local.envs : "${env}.ci" => "principalSet://iam.googleapis.com/projects/${env_cfg.project_number}/locations/global/workloadIdentityPools/${var.workload_identity_pool_id}/attribute.environment/${env}"
  }
  deploy_principal_sets = {
    for env, env_cfg in local.envs : "${env}.deploy" => "principalSet://iam.googleapis.com/projects/${env_cfg.project_number}/locations/global/workloadIdentityPools/${var.workload_identity_pool_id}/attribute.environment/${env}"
  }
  iac_principal_sets = {
    for env, env_cfg in local.envs : "${env}.iac" => "principalSet://iam.googleapis.com/projects/${env_cfg.project_number}/locations/global/workloadIdentityPools/${var.workload_identity_pool_id}/attribute.environment/${env}"
  }

  # Foundation repository variables the bootstrap root owns. Each entry
  # pairs the GitHub variable name with the value to publish. Bootstrap
  # never writes runtime configuration, DNS settings, notification email,
  # model selection, or secret values; the iac.yml post-apply sync jobs
  # own the per-environment outputs.
  foundation_variables = merge(
    {
      "DEV_TF_STATE_BUCKET"                      = module.dev_state_bucket.bucket_name
      "PROD_TF_STATE_BUCKET"                     = module.prod_state_bucket.bucket_name
      "DEV_GCP_PROJECT_ID"                       = var.dev_project_id
      "PROD_GCP_PROJECT_ID"                      = var.prod_project_id
      "DEV_GCP_PROJECT_NUMBER"                   = var.dev_project_number
      "PROD_GCP_PROJECT_NUMBER"                  = var.prod_project_number
      "DEV_CI_SERVICE_ACCOUNT_EMAIL"             = module.dev_bootstrap_iam.ci_service_account_email
      "PROD_CI_SERVICE_ACCOUNT_EMAIL"            = module.prod_bootstrap_iam.ci_service_account_email
      "DEV_DEPLOY_SERVICE_ACCOUNT_EMAIL"         = module.dev_bootstrap_iam.deploy_service_account_email
      "PROD_DEPLOY_SERVICE_ACCOUNT_EMAIL"        = module.prod_bootstrap_iam.deploy_service_account_email
      "DEV_IAC_SERVICE_ACCOUNT_EMAIL"            = module.dev_bootstrap_iam.iac_service_account_email
      "PROD_IAC_SERVICE_ACCOUNT_EMAIL"           = module.prod_bootstrap_iam.iac_service_account_email
      "DEV_WIF_PROVIDER_ID"                      = module.dev_workload_identity.provider_name
      "PROD_WIF_PROVIDER_ID"                     = module.prod_workload_identity.provider_name
      "DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL" = module.prod_bootstrap_iam.ci_service_account_email
    },
  )
}

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

# State-bucket IAM bindings are direct resources (not driven from the
# state-bucket module's for_each) because the IaC account emails are
# created by the bootstrap-iam modules below and resolved only after
# plan-time for_each evaluation. Each IaC account gets
# `roles/storage.objectAdmin` on its own environment's state bucket; the
# CI account has its own bucket-level binding.
resource "google_storage_bucket_iam_member" "dev_state_bucket_ci" {
  bucket = module.dev_state_bucket.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.dev_bootstrap_iam.ci_service_account_email}"
}

resource "google_storage_bucket_iam_member" "dev_state_bucket_iac" {
  bucket = module.dev_state_bucket.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.dev_bootstrap_iam.iac_service_account_email}"
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

resource "google_storage_bucket_iam_member" "prod_state_bucket_iac" {
  bucket = module.prod_state_bucket.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.prod_bootstrap_iam.iac_service_account_email}"
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

# CI, deploy, and IaC service accounts and their project-level IAM
# bindings. The IaC account is the dedicated identity for OpenTofu
# applies; the CI account stays limited to image build/push and the
# deploy account stays limited to GKE deploys.
module "dev_bootstrap_iam" {
  source                    = "../modules/bootstrap-iam"
  project_id                = var.dev_project_id
  ci_service_account_id     = var.dev_ci_service_account_id
  deploy_service_account_id = var.dev_deploy_service_account_id
  iac_service_account_id    = var.dev_iac_service_account_id
  ci_roles                  = var.dev_ci_roles
  deploy_roles              = var.dev_deploy_roles
  iac_roles                 = var.dev_iac_roles
  ci_principal_sets         = { for k, v in local.ci_principal_sets : "dev" => v if startswith(k, "dev.") }
  deploy_principal_sets     = { for k, v in local.deploy_principal_sets : "dev" => v if startswith(k, "dev.") }
  iac_principal_sets        = { for k, v in local.iac_principal_sets : "dev" => v if startswith(k, "dev.") }
}

module "prod_bootstrap_iam" {
  source                    = "../modules/bootstrap-iam"
  project_id                = var.prod_project_id
  ci_service_account_id     = var.prod_ci_service_account_id
  deploy_service_account_id = var.prod_deploy_service_account_id
  iac_service_account_id    = var.prod_iac_service_account_id
  ci_roles                  = var.prod_ci_roles
  deploy_roles              = var.prod_deploy_roles
  iac_roles                 = var.prod_iac_roles
  ci_principal_sets         = { for k, v in local.ci_principal_sets : "prod" => v if startswith(k, "prod.") }
  deploy_principal_sets     = { for k, v in local.deploy_principal_sets : "prod" => v if startswith(k, "prod.") }
  iac_principal_sets        = { for k, v in local.iac_principal_sets : "prod" => v if startswith(k, "prod.") }
}

# Foundation repository variables. The GitHub provider authenticates from
# the GITHUB_TOKEN environment variable; the token is never written to
# terraform.tfvars, OpenTofu outputs, or state. A fine-grained PAT scoped
# to the target repository with "Actions variables: Write" permission is
# required.
resource "github_actions_variable" "foundation" {
  for_each = local.foundation_variables

  repository    = var.github_repository
  variable_name = each.key
  value         = each.value
}
