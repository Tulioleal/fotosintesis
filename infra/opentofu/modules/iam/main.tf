resource "google_service_account" "backend" {
  project      = var.project_id
  account_id   = var.backend_service_account_id
  display_name = "Fotosintesis backend workload"
}

resource "google_service_account" "frontend" {
  project      = var.project_id
  account_id   = var.frontend_service_account_id
  display_name = "Fotosintesis frontend workload"
}

resource "google_project_iam_member" "backend_roles" {
  for_each = toset(var.backend_roles)
  project  = var.project_id
  role     = each.value
  member   = google_service_account.backend.member
}

resource "google_project_iam_member" "frontend_roles" {
  for_each = toset(var.frontend_roles)
  project  = var.project_id
  role     = each.value
  member   = google_service_account.frontend.member
}

resource "google_service_account_iam_member" "backend_workload_identity" {
  service_account_id = google_service_account.backend.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.kubernetes_namespace}/${var.backend_kubernetes_service_account}]"
}

resource "google_service_account_iam_member" "frontend_workload_identity" {
  service_account_id = google_service_account.frontend.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.kubernetes_namespace}/${var.frontend_kubernetes_service_account}]"
}

resource "google_project_iam_member" "cross_project_artifactregistry_readers" {
  for_each = toset(var.cross_project_artifactregistry_readers)

  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${each.value}"
}
