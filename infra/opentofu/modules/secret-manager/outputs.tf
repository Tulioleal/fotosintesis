output "secret_names" {
  value = { for key, secret in google_secret_manager_secret.runtime : key => secret.name }
}
