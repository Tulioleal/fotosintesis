output "backend_service_account_email" {
  value = google_service_account.backend.email
}

output "frontend_service_account_email" {
  value = google_service_account.frontend.email
}
