output "bucket_name" {
  value       = google_storage_bucket.state.name
  description = "Name of the GCS bucket that holds OpenTofu state."
}

output "bucket_url" {
  value       = google_storage_bucket.state.url
  description = "URL of the GCS bucket."
}
