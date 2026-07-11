resource "google_storage_bucket" "state" {
  project                     = var.project_id
  name                        = var.bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  versioning {
    enabled = true
  }
  force_destroy = var.force_destroy
  labels        = var.labels
}

resource "google_storage_bucket_iam_member" "ci" {
  for_each = var.ci_principals

  bucket = google_storage_bucket.state.name
  role   = each.value.role
  member = each.value.member
}

resource "google_storage_bucket_iam_member" "deploy" {
  for_each = var.deploy_principals

  bucket = google_storage_bucket.state.name
  role   = each.value.role
  member = each.value.member
}

resource "google_storage_bucket_iam_member" "admin" {
  for_each = var.admin_principals

  bucket = google_storage_bucket.state.name
  role   = each.value.role
  member = each.value.member
}
