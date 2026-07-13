variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "database_name" {
  type = string
}

variable "tier" {
  type = string
}

variable "edition" {
  type        = string
  default     = "ENTERPRISE"
  description = "Cloud SQL edition. ENTERPRISE supports low-cost tiers like db-f1-micro; ENTERPRISE_PLUS requires db-perf-optimized-* tiers."
}

variable "ipv4_enabled" {
  type        = bool
  default     = true
  description = "Whether the Cloud SQL instance has public IPv4 connectivity. Required for Cloud SQL Auth Proxy unless private IP or PSC is configured."
}

variable "availability_type" {
  type = string
}

variable "disk_size_gb" {
  type = number
}

variable "deletion_protection" {
  type = bool
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "database_user" {
  type    = string
  default = "fotosintesis"
}
