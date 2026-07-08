resource "google_service_account" "ci" {
  project      = var.project_id
  account_id   = var.ci_service_account_id
  display_name = "Fotosintesis CI service account"
}

resource "google_service_account" "deploy" {
  project      = var.project_id
  account_id   = var.deploy_service_account_id
  display_name = "Fotosintesis deploy service account"
}

resource "google_project_iam_member" "ci" {
  for_each = var.ci_roles

  project = var.project_id
  role    = each.value
  member  = google_service_account.ci.member
}

resource "google_project_iam_member" "deploy" {
  for_each = var.deploy_roles

  project = var.project_id
  role    = each.value
  member  = google_service_account.deploy.member
}

resource "google_service_account_iam_member" "ci_workload_identity" {
  for_each = var.ci_principal_sets

  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = each.value
}

resource "google_service_account_iam_member" "deploy_workload_identity" {
  for_each = var.deploy_principal_sets

  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = each.value
}
