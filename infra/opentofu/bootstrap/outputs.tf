# output "bootstrap_state_bucket" {
#   value       = module.bootstrap_state_bucket.bucket_name
#   description = "Name of the GCS bucket that holds the bootstrap root's OpenTofu state. The first apply runs with local state and the operator migrates state to this bucket using the documented backend configuration."
# }

output "dev_state_bucket" {
  value       = module.dev_state_bucket.bucket_name
  description = "Name of the GCS bucket that holds the dev OpenTofu root state."
}

output "prod_state_bucket" {
  value       = module.prod_state_bucket.bucket_name
  description = "Name of the GCS bucket that holds the prod OpenTofu root state."
}

output "dev_project_id" {
  value = var.dev_project_id
}

output "dev_project_number" {
  value = var.dev_project_number
}

output "prod_project_id" {
  value = var.prod_project_id
}

output "prod_project_number" {
  value = var.prod_project_number
}

output "dev_ci_service_account_email" {
  value       = module.dev_bootstrap_iam.ci_service_account_email
  description = "Email of the dev CI service account. Map to GitHub repository variable DEV_CI_SERVICE_ACCOUNT_EMAIL."
}

output "dev_deploy_service_account_email" {
  value       = module.dev_bootstrap_iam.deploy_service_account_email
  description = "Email of the dev deploy service account. Map to GitHub repository variable DEPLOY_SERVICE_ACCOUNT_EMAIL when deploying to dev."
}

output "prod_ci_service_account_email" {
  value       = module.prod_bootstrap_iam.ci_service_account_email
  description = "Email of the prod CI service account. Map to GitHub repository variable PROD_CI_SERVICE_ACCOUNT_EMAIL and DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL."
}

output "prod_deploy_service_account_email" {
  value       = module.prod_bootstrap_iam.deploy_service_account_email
  description = "Email of the prod deploy service account. Map to GitHub repository variable DEPLOY_SERVICE_ACCOUNT_EMAIL when deploying to prod."
}

output "dev_wif_provider_id" {
  value       = module.dev_workload_identity.provider_name
  description = "Resource name of the dev Workload Identity provider. Map to GitHub repository variable DEV_WIF_PROVIDER_ID and WIF_PROVIDER_ID when deploying to dev."
}

output "prod_wif_provider_id" {
  value       = module.prod_workload_identity.provider_name
  description = "Resource name of the prod Workload Identity provider. Map to GitHub repository variable PROD_WIF_PROVIDER_ID and WIF_PROVIDER_ID when deploying to prod."
}

output "dev_enabled_services" {
  value = module.dev_project_services.enabled_services
}

output "prod_enabled_services" {
  value = module.prod_project_services.enabled_services
}
