output "name" {
  value       = google_compute_global_address.frontend.name
  description = "Name of the reserved static IP. Use in the Ingress annotation `kubernetes.io/ingress.global-static-ip-name`."
}

output "address" {
  value       = google_compute_global_address.frontend.address
  description = "IPv4 address of the reserved static IP. Use to configure DNS A records or to reach the cluster directly when FRONTEND_EXPOSURE_MODE=ip-http."
}
