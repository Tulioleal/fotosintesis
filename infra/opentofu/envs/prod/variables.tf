variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "environment" {
  type    = string
  default = "prod"
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
  default = "fotosintesis-prod"
}

variable "node_count" {
  type    = number
  default = 2
}

variable "machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "database_instance_name" {
  type    = string
  default = "fotosintesis-prod-postgres"
}

variable "database_name" {
  type    = string
  default = "fotosintesis"
}

variable "database_tier" {
  type    = string
  default = "db-custom-2-7680"
}

variable "database_availability_type" {
  type    = string
  default = "REGIONAL"
}

variable "database_disk_size_gb" {
  type    = number
  default = 100
}

variable "object_storage_bucket" {
  type    = string
  default = "replace-with-prod-fotosintesis-storage"
}

variable "storage_location" {
  type    = string
  default = "US"
}

variable "storage_force_destroy" {
  type    = bool
  default = false
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
  default = "fotosintesis-backend-prod"
}

variable "frontend_service_account_id" {
  type    = string
  default = "fotosintesis-frontend-prod"
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

variable "frontend_static_ip_name" {
  type        = string
  default     = "fotosintesis-prod-frontend-ip"
  description = "Name of the reserved global static IP for the prod frontend ingress. Must match the Ingress annotation `kubernetes.io/ingress.global-static-ip-name`."
}

variable "prod_promotion_service_account_email" {
  type        = string
  default     = ""
  description = "Optional. The prod root does not need to grant cross-project reader access; this is left for the dev root to expose instead. Keep the default empty value to disable the binding."
}
