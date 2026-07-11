variable "project_id" {
  type        = string
  description = "GCP project ID where the APIs are enabled."
}

variable "services" {
  type        = set(string)
  description = "Set of service names (e.g. container.googleapis.com) to enable on the project."
}
