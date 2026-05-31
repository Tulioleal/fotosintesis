output "cluster_name" {
  value = google_container_cluster.primary.name
}

output "cluster_location" {
  value = google_container_cluster.primary.location
}

output "node_service_account_email" {
  value = google_service_account.nodes.email
}

output "workload_identity_pool" {
  value = google_container_cluster.primary.workload_identity_config[0].workload_pool
}
