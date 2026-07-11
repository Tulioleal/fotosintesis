variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "location" {
  type        = string
  default     = null
  description = "GKE cluster and node pool location. Defaults to var.region. Use a zone such as us-central1-a for low-cost dev clusters."
}

variable "cluster_name" {
  type = string
}

variable "node_count" {
  type = number
}

variable "machine_type" {
  type = string
}

variable "release_channel" {
  type    = string
  default = "REGULAR"
}

variable "deletion_protection" {
  type = bool
}

variable "labels" {
  type    = map(string)
  default = {}
}
