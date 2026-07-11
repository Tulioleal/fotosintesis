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

variable "gke_location" {
  type        = string
  default     = null
  description = "Optional GKE location override. Prod may intentionally leave this unset to keep a regional cluster; set to a zone only if you want a zonal prod cluster."
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

variable "database_edition" {
  type        = string
  default     = "ENTERPRISE"
  description = "Cloud SQL edition for the environment. Prod keeps the default ENTERPRISE; switch to ENTERPRISE_PLUS only with a db-perf-optimized-* tier."
}

variable "database_ipv4_enabled" {
  type        = bool
  default     = true
  description = "Whether the prod Cloud SQL instance has public IPv4 connectivity. Set to false to force private IP or PSC; otherwise the Cloud SQL Auth Proxy sidecar requires public IPv4."
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
  type        = string
  default     = "fotosintesis-prod-storage"
  description = "Application GCS bucket name for the prod environment. Operators must override this through TF_VAR_object_storage_bucket (from the PROD_OBJECT_STORAGE_BUCKET_INPUT repository variable) on the first apply because the bucket name must be globally unique and the env root cannot pre-populate it safely."
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
    "fotosintesis-openai-api-key",
    "fotosintesis-gemini-api-key",
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
