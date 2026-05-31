variable "project_id" {
  type = string
}

variable "notification_email" {
  type    = string
  default = ""
}

variable "cpu_threshold" {
  type    = number
  default = 0.8
}
