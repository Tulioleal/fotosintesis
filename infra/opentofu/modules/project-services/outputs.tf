output "enabled_services" {
  value       = sort([for service in google_project_service.service : service.service])
  description = "Sorted list of enabled service names."
}
