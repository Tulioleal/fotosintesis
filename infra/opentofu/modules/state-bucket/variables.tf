variable "project_id" {
  type        = string
  description = "GCP project ID that owns the state bucket."
}

variable "bucket_name" {
  type        = string
  description = "Globally unique GCS bucket name for OpenTofu state."
}

variable "location" {
  type        = string
  default     = "US"
  description = "GCS bucket location."
}

variable "force_destroy" {
  type        = bool
  default     = false
  description = "Allow Terraform/OpenTofu to delete a non-empty bucket. Keep false for state buckets that must survive accidental local destroy runs."
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "Labels applied to the bucket."
}

variable "ci_principals" {
  type = map(object({
    role   = string
    member = string
  }))
  default     = {}
  description = "Map of role label -> { role, member } for CI service accounts that need read/write access to this state bucket."
}

variable "deploy_principals" {
  type = map(object({
    role   = string
    member = string
  }))
  default     = {}
  description = "Map of role label -> { role, member } for deploy service accounts that need read-only access to this state bucket."
}

variable "admin_principals" {
  type = map(object({
    role   = string
    member = string
  }))
  default     = {}
  description = "Map of role label -> { role, member } for principals that need administrative recovery access. bootstrap_admin_members use this to retain access to bootstrap/dev/prod state buckets."
}
