output "artifact_repository_url" {
  value = module.artifact_registry.repository_url
}

output "backend_service_account_email" {
  value = module.iam.backend_service_account_email
}

output "cloud_sql_database_name" {
  value = module.cloud_sql.database_name
}

output "cloud_sql_instance_connection_name" {
  value = module.cloud_sql.instance_connection_name
}

output "frontend_service_account_email" {
  value = module.iam.frontend_service_account_email
}

output "gke_cluster_location" {
  value       = module.gke.cluster_location
  description = "Location of the GKE cluster (region). The deploy workflow uses this to fetch credentials."
}

output "gke_cluster_name" {
  value       = module.gke.cluster_name
  description = "Name of the GKE cluster. The deploy workflow uses this to fetch credentials."
}

output "object_storage_bucket" {
  value = module.storage.bucket_name
}

output "secret_names" {
  value = module.secret_manager.secret_names
}

output "frontend_static_ip_name" {
  value       = module.static_ip.name
  description = "Name of the reserved global static IP. The Kubernetes Ingress annotation `kubernetes.io/ingress.global-static-ip-name` must use this value."
}

output "frontend_static_ip_address" {
  value       = module.static_ip.address
  description = "IPv4 address of the reserved global static IP. Configure DNS A records to point at this address."
}

output "kubernetes_namespace" {
  value       = var.kubernetes_namespace
  description = "Kubernetes namespace where application workloads run."
}

output "project_id" {
  value       = var.project_id
  description = "GCP project ID."
}

output "runtime_secret_name" {
  value       = "fotosintesis-runtime"
  description = "Name of the runtime Kubernetes Secret projected by External Secrets. The deploy workflow waits for this Secret before applying workloads."
}
