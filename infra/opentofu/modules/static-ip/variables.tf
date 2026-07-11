variable "project_id" {
  type        = string
  description = "GCP project ID that owns the reserved static IP."
}

variable "name" {
  type        = string
  description = "Name of the global static IP. Must match the value referenced by the Kubernetes Ingress annotation `kubernetes.io/ingress.global-static-ip-name`."
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "Labels applied to the static IP."
}
