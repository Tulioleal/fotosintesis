resource "google_compute_global_address" "frontend" {
  project      = var.project_id
  name         = var.name
  description  = "Reserved static IP for Fotosintesis frontend ingress."
  address_type = "EXTERNAL"
  labels       = var.labels
}
