output "pool_name" {
  value       = google_iam_workload_identity_pool.github.name
  description = "Resource name of the Workload Identity pool."
}

output "provider_name" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Resource name of the Workload Identity provider. Use as the workload_identity_provider input to google-github-actions/auth."
}

output "provider_id" {
  value       = google_iam_workload_identity_pool_provider.github.workload_identity_pool_provider_id
  description = "Short ID of the Workload Identity provider."
}
