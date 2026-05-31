variable "project_id" {
  type = string
}

variable "secret_ids" {
  type = set(string)
}

variable "labels" {
  type    = map(string)
  default = {}
}
