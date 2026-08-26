resource "google_artifact_registry_repository" "app" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  description   = "Fotosintesis AI container images"
  format        = "DOCKER"
  labels        = var.labels

  docker_config {
    immutable_tags = true
  }
}
