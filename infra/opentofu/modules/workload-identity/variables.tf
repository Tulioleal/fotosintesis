variable "project_id" {
  type        = string
  description = "GCP project ID that owns the Workload Identity pool."
}

variable "project_number" {
  type        = string
  description = "Numeric project number for the Workload Identity pool. Required so attribute conditions do not need to call the Cloud Resource Manager API."
}

variable "pool_id" {
  type        = string
  default     = "github-actions"
  description = "Workload Identity pool ID. Must be 4-32 characters matching ^[a-z][a-z0-9-]{3,31}$."
}

variable "provider_id" {
  type        = string
  default     = "github"
  description = "Workload Identity provider ID. Must be 4-32 characters matching ^[a-z][a-z0-9-]{3,31}$."
}

variable "github_owner" {
  type        = string
  description = "GitHub organization or user that owns the repository. Used in the attribute_condition."
}

variable "github_repository" {
  type        = string
  description = "GitHub repository name. Used in the attribute_condition."
}

variable "environment_branches" {
  type        = map(list(string))
  description = "Map of environment name -> list of Git refs allowed to authenticate. The provider's attribute_condition permits only refs listed for the matching environment, so a provider scoped to `dev` rejects prod refs and vice versa."
  default = {
    dev  = ["refs/heads/main"]
    prod = ["refs/heads/main", "refs/tags/release/*"]
  }
}
