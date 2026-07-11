terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  labels = merge(var.labels, { app = "fotosintesis", environment = var.environment })
}

module "artifact_registry" {
  source        = "../../modules/artifact-registry"
  project_id    = var.project_id
  region        = var.region
  repository_id = var.artifact_repository_id
  labels        = local.labels
}

module "gke" {
  source              = "../../modules/gke"
  project_id          = var.project_id
  region              = var.region
  location            = var.gke_location
  cluster_name        = var.cluster_name
  node_count          = var.node_count
  machine_type        = var.machine_type
  deletion_protection = var.deletion_protection
  labels              = local.labels
}

module "cloud_sql" {
  source              = "../../modules/cloud-sql"
  project_id          = var.project_id
  region              = var.region
  instance_name       = var.database_instance_name
  database_name       = var.database_name
  tier                = var.database_tier
  edition             = var.database_edition
  availability_type   = var.database_availability_type
  disk_size_gb        = var.database_disk_size_gb
  ipv4_enabled        = var.database_ipv4_enabled
  deletion_protection = var.deletion_protection
  labels              = local.labels
}

module "storage" {
  source        = "../../modules/storage"
  project_id    = var.project_id
  bucket_name   = var.object_storage_bucket
  location      = var.storage_location
  force_destroy = var.storage_force_destroy
  labels        = local.labels
}

module "secret_manager" {
  source     = "../../modules/secret-manager"
  project_id = var.project_id
  secret_ids = var.secret_ids
  labels     = local.labels
}

module "iam" {
  source                              = "../../modules/iam"
  project_id                          = var.project_id
  backend_service_account_id          = var.backend_service_account_id
  frontend_service_account_id         = var.frontend_service_account_id
  backend_roles                       = var.backend_roles
  frontend_roles                      = var.frontend_roles
  kubernetes_namespace                = var.kubernetes_namespace
  backend_kubernetes_service_account  = var.backend_kubernetes_service_account
  frontend_kubernetes_service_account = var.frontend_kubernetes_service_account
  cross_project_artifactregistry_readers = compact([
    var.prod_promotion_service_account_email,
  ])

  depends_on = [module.gke]
}

module "monitoring" {
  source             = "../../modules/monitoring"
  project_id         = var.project_id
  notification_email = var.notification_email
}

module "static_ip" {
  source     = "../../modules/static-ip"
  project_id = var.project_id
  name       = var.frontend_static_ip_name
  labels     = local.labels
}
