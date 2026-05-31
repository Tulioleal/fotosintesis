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
  value = module.gke.cluster_location
}

output "gke_cluster_name" {
  value = module.gke.cluster_name
}

output "object_storage_bucket" {
  value = module.storage.bucket_name
}

output "secret_names" {
  value = module.secret_manager.secret_names
}
