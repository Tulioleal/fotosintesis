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
  type    = number
  default = null
}

variable "autoscaling_min_node_count" {
  type    = number
  default = null
}

variable "autoscaling_max_node_count" {
  type    = number
  default = null
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

variable "dataplane_v2" {
  type        = bool
  default     = true
  description = "Enable GKE Dataplane V2 (ADVANCED_DATAPATH). Dataplane V2 provides built-in Kubernetes NetworkPolicy enforcement. Enabling it on an existing cluster recreates the node pools; it cannot be disabled in place. When true, do not also enable the Calico network_policy addon (GKE rejects it)."
}

variable "labels" {
  type    = map(string)
  default = {}
}
