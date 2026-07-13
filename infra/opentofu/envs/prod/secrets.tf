resource "google_secret_manager_secret_version" "database_url" {
  secret = module.secret_manager.secret_names["fotosintesis-database-url"]

  secret_data = "postgresql+asyncpg://${module.cloud_sql.database_user}:${urlencode(module.cloud_sql.database_password)}@127.0.0.1:5432/${module.cloud_sql.database_name}"
}

resource "random_password" "auth_secret" {
  length  = 48
  special = true
}

resource "google_secret_manager_secret_version" "auth_secret" {
  secret      = module.secret_manager.secret_names["fotosintesis-auth-secret"]
  secret_data = random_password.auth_secret.result
}
