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

variable "gke_location" {
  type        = string
  default     = null
  description = "Optional GKE location override. Set to a zone like us-central1-a for dev to avoid regional multi-zone stockouts."
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

variable "database_edition" {
  type        = string
  default     = "ENTERPRISE"
  description = "Cloud SQL edition for the environment. ENTERPRISE supports the default dev tier db-f1-micro; ENTERPRISE_PLUS requires db-perf-optimized-*."
}

variable "database_ipv4_enabled" {
  type        = bool
  default     = true
  description = "Whether the dev Cloud SQL instance has public IPv4 connectivity. Required for Cloud SQL Auth Proxy unless private IP or PSC is configured."
}

variable "database_availability_type" {
  type    = string
  default = "ZONAL"
}

variable "database_disk_size_gb" {
  type    = number
  default = 20
}

variable "database_user" {
  type    = string
  default = "fotosintesis"
}

variable "object_storage_bucket" {
  type        = string
  default     = "fotosintesis-dev-storage"
  description = "Application GCS bucket name. Defaulted for the env root. The iac.yml PR plan and manual apply paths may pass TF_VAR_object_storage_bucket from the DEV_OBJECT_STORAGE_BUCKET_INPUT repository variable on the first apply; subsequent applies leave it empty so the root keeps its default."
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
    "fotosintesis-openai-api-key",
    "fotosintesis-gemini-api-key",
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

variable "frontend_static_ip_name" {
  type        = string
  default     = "fotosintesis-dev-frontend-ip"
  description = "Name of the reserved global static IP for the dev frontend ingress. Must match the Ingress annotation `kubernetes.io/ingress.global-static-ip-name`."
}

variable "prod_promotion_service_account_email" {
  type        = string
  default     = ""
  description = "Email of the prod CI service account. The dev project grants it `roles/artifactregistry.reader` so a single OIDC token can both verify dev source images and copy them into the prod registry. Map from GitHub repository variable DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL (mapped to TF_VAR_prod_promotion_service_account_email)."
}
