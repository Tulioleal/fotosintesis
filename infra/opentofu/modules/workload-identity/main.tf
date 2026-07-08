resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = var.pool_id
  display_name              = "GitHub Actions pool"
  description               = "Pool for GitHub Actions OIDC tokens scoped to Fotosintesis workflows."
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = var.provider_id
  display_name                       = "GitHub Actions provider"
  description                        = "OIDC provider for GitHub Actions scoped to ${var.github_owner}/${var.github_repository}."
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
    "attribute.ref"              = "assertion.ref"
    "attribute.environment"      = "assertion.environment"
  }
  attribute_condition = local.attribute_condition
}

locals {
  env_conditions = {
    for env, refs in var.environment_branches : env => join(" || ", [
      for ref in refs : "assertion.ref==${ref}"
    ])
  }

  # Only allow tokens for the configured repository, and only when the
  # token's `environment` claim (set by GitHub Actions) matches one of
  # the configured environment branches. The OIDC provider is per-project
  # because pool-level attributes depend on the project number, but the
  # attribute condition scopes the provider to a single repository and
  # to the configured environment branches only.
  attribute_condition = join(" && ", concat(
    ["assertion.repository==${var.github_owner}/${var.github_repository}"],
    [for env_cond in values(local.env_conditions) : "(${env_cond})"],
  ))
}
