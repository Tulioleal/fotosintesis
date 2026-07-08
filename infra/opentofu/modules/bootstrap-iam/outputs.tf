output "ci_service_account_email" {
  value       = google_service_account.ci.email
  description = "Email of the CI service account. Map to GitHub repository variable CI_SERVICE_ACCOUNT_EMAIL."
}

output "ci_service_account_name" {
  value       = google_service_account.ci.name
  description = "Resource name of the CI service account. Used to bind principalSet impersonation."
}

output "deploy_service_account_email" {
  value       = google_service_account.deploy.email
  description = "Email of the deploy service account. Map to GitHub repository variable DEPLOY_SERVICE_ACCOUNT_EMAIL."
}

output "deploy_service_account_name" {
  value       = google_service_account.deploy.name
  description = "Resource name of the deploy service account."
}
