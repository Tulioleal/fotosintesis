variable "project_id" {
  type = string
}

variable "backend_service_account_id" {
  type = string
}

variable "frontend_service_account_id" {
  type = string
}

variable "backend_roles" {
  type = set(string)
}

variable "frontend_roles" {
  type = set(string)
}

variable "kubernetes_namespace" {
  type = string
}

variable "backend_kubernetes_service_account" {
  type = string
}

variable "frontend_kubernetes_service_account" {
  type = string
}
