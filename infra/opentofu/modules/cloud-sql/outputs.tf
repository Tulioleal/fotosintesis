output "instance_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "database_name" {
  value = google_sql_database.app.name
}

output "instance_name" {
  value = google_sql_database_instance.postgres.name
}
