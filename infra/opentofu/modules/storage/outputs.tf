output "bucket_name" {
  value = google_storage_bucket.app.name
}

output "bucket_url" {
  value = google_storage_bucket.app.url
}
