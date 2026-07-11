# GitHub Environments

The repository uses two GitHub Environments to separate automatic dev
deploys from approval-gated prod deploys. Environments enforce deployment
protection rules; deployment configuration is stored in repository
variables, not in environment-scoped variables.

Bootstrap publishes the non-secret `DEV_*` and `PROD_*` foundation
variables during its local apply. Each successful environment IaC apply
then synchronizes non-sensitive environment outputs to repository
variables. Runtime secret values remain in GCP Secret Manager.

## `dev` environment

- **Protection rules:** none.
- **Deployment branches/tags:** any (used by `backend-ci.yml`,
  `frontend-ci.yml`, and `iac.yml` for the dev auto-apply).
- **Purpose:** the dev environment is the destination of every
  successful `main` build for backend and frontend, and of the
  OpenTofu auto-apply for the dev root. The `deploy.yml` job references
  `environment: dev` for the auto-dev path.
- **Required secrets/variables:** no environment-scoped values. Bootstrap
  and the IaC post-apply sync jobs publish repository variables.

## `prod` environment

- **Protection rules:** required reviewers (at least one operator with
  prod access). Configure under Settings -> Environments -> prod ->
  Protection rules -> Required reviewers.
- **Deployment branches/tags:** any. Production deploys run from manual
  `iac.yml` and `release.yml` dispatches, not from push events.
- **Purpose:** production OpenTofu applies, production image
  promotion, and production manifest deploys. Every `prod` job in
  `iac.yml` (`manual`), `release.yml` (`promote-images`, `deploy-prod`,
  `summary`), and `deploy.yml` (when called with `environment: prod`)
  references this environment.
- **Required secrets/variables:** no environment-scoped values. Bootstrap
  and the IaC post-apply sync jobs publish repository variables.

## Setting up a new environment

1. Open the repository on GitHub.
2. Settings -> Environments -> New environment.
3. Name it `dev` (no protection rules) or `prod` (configure required
   reviewers).
4. Save. The `iac.yml` and `deploy.yml` workflows reference the
   environment by name in their `environment:` keys, so GitHub will
   enforce the rules automatically. Apply bootstrap first so its GitHub
   provider can publish the foundation repository variables.

## Verifying the configuration

After configuring both environments, run a manual `iac.yml` dispatch
with `environment=dev` and `tofu_command=plan` to confirm dev can
authenticate without approval. Then run a prod plan and confirm the
configured reviewer approval is required before its job starts.
