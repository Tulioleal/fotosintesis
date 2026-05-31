variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "artifact_repository_id" {
  type    = string
  default = "fotosintesis"
}

variable "cluster_name" {
  type    = string
  default = "fotosintesis-dev"
}

variable "node_count" {
  type    = number
  default = 1
}

variable "machine_type" {
  type    = string
  default = "e2-medium"
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "database_instance_name" {
  type    = string
  default = "fotosintesis-dev-postgres"
}

variable "database_name" {
  type    = string
  default = "fotosintesis"
}

variable "database_tier" {
  type    = string
  default = "db-f1-micro"
}

variable "database_availability_type" {
  type    = string
  default = "ZONAL"
}

variable "database_disk_size_gb" {
  type    = number
  default = 20
}

variable "object_storage_bucket" {
  type    = string
  default = "replace-with-dev-fotosintesis-storage"
}

variable "storage_location" {
  type    = string
  default = "US"
}

variable "storage_force_destroy" {
  type    = bool
  default = true
}

variable "secret_ids" {
  type = set(string)
  default = [
    "fotosintesis-database-url",
    "fotosintesis-auth-secret",
    "fotosintesis-object-storage-access-key",
    "fotosintesis-object-storage-secret-key",
    "fotosintesis-provider-api-keys",
  ]
}

variable "backend_service_account_id" {
  type    = string
  default = "fotosintesis-backend-dev"
}

variable "frontend_service_account_id" {
  type    = string
  default = "fotosintesis-frontend-dev"
}

variable "backend_roles" {
  type = set(string)
  default = [
    "roles/cloudsql.client",
    "roles/storage.objectAdmin",
    "roles/secretmanager.secretAccessor",
    "roles/monitoring.metricWriter",
  ]
}

variable "frontend_roles" {
  type    = set(string)
  default = ["roles/secretmanager.secretAccessor"]
}

variable "kubernetes_namespace" {
  type    = string
  default = "fotosintesis"
}

variable "backend_kubernetes_service_account" {
  type    = string
  default = "fotosintesis-backend"
}

variable "frontend_kubernetes_service_account" {
  type    = string
  default = "fotosintesis-frontend"
}

variable "notification_email" {
  type    = string
  default = ""
}
