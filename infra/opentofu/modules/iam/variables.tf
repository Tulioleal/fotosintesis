variable "project_id" {
  type = string
}

variable "backend_service_account_id" {
  type = string
}

variable "frontend_service_account_id" {
  type = string
}

variable "backend_roles" {
  type = set(string)
}

variable "frontend_roles" {
  type = set(string)
}

variable "kubernetes_namespace" {
  type = string
}

variable "backend_kubernetes_service_account" {
  type = string
}

variable "frontend_kubernetes_service_account" {
  type = string
}

variable "cross_project_artifactregistry_readers" {
  type        = set(string)
  description = "Service account emails from destination-environment projects that need roles/artifactregistry.reader on this project's Artifact Registry. The dev root uses this to grant the prod CI service account reader access so a single OIDC token can both verify source images and copy them into the destination registry."
  default     = []
}
