resource "google_storage_bucket" "app" {
  project                     = var.project_id
  name                        = var.bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  force_destroy               = var.force_destroy
  labels                      = var.labels
}
