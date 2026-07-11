# GCP Deployment Platform

This directory documents the operational model for deploying Fotosintesis to
GCP. It complements the high-level `DOCS/deployment.md` and the OpenSpec
change artifacts in `openspec/changes/gcp-deployment-platform/`.

## Documents

| File | Purpose |
| --- | --- |
| `bootstrap.md` | One-time local apply of the bootstrap OpenTofu root. Owns state buckets, API enablement, GitHub OIDC, CI/deploy identities. |
| `github-variables.md` | Repository and environment variables consumed by `iac.yml`, `deploy.yml`, and `release.yml`. |
| `github-environments.md` | Required GitHub Environments (`dev` automatic, `prod` approval-gated). |
| `external-secrets.md` | Manual Secret Manager population and the External Secrets Operator projection model. |
| `dns.md` | DNS records that point at the reserved static IPs, plus the `hostname-https` vs `ip-http` exposure modes. |
| `deploy-and-release.md` | Dev auto-deploy, manual dev redeploy, and prod release flows. Includes the immutable 40-character Git commit SHA image tag contract. |
| `rollback.md` | Image-tag rollback, `kubectl rollout undo`, and database migration forward-fix / restore limitations. |
| `cleanup.md` | Non-production cleanup and production deletion-protection safeguards. |
| `validation-runbook.md` | Operator procedure for collecting dev end-to-end and prod release evidence. |
| `validation-evidence.md` | Evidence template used by the validation runbook. |
| `environment-contract.md` | Output contract between the OpenTofu roots and the deploy workflow. |

## Reading order

1. Read `bootstrap.md` to understand the foundation layer.
2. Read `github-variables.md` and `github-environments.md` before configuring
   the repository.
3. Use `external-secrets.md`, `dns.md`, and `deploy-and-release.md` when
   running a first deployment.
4. Use `rollback.md` and `cleanup.md` for operational response.
5. Use `validation-runbook.md` and `validation-evidence.md` when collecting
   live deployment evidence.
