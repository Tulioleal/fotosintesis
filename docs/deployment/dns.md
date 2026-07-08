# DNS and Frontend Exposure Modes

The platform supports two ways to reach the frontend HTTPS endpoint:

- `hostname-https` - GKE-managed certificate, requires DNS.
- `ip-http` - direct HTTP through the reserved static IP. Useful for
  dev or smoke testing where DNS is not available.

The mode is controlled by the `FRONTEND_EXPOSURE_MODE` repository
variable.

## `hostname-https`

This is the production exposure mode. It produces an HTTPS endpoint
that is reachable at a real hostname and protected by a GKE-managed
certificate.

### Steps

1. Reserve the static IP. The `static-ip` OpenTofu module creates a
   `google_compute_global_address` named after
   `frontend_static_ip_name` (default `fotosintesis-prod-frontend-ip`).
2. Read the IP from the env-root outputs:
   ```bash
   tofu output -raw frontend_static_ip_address
   ```
3. Create (or update) a DNS A record for the production hostname
   pointing at that IP. The TTL can be short during the first
   cutover; raise it once the certificate is provisioned.
4. Set `FRONTEND_EXPOSURE_MODE=hostname-https`,
   `FRONTEND_HOSTNAME=<your hostname>`, and
   `MANAGED_CERTIFICATE_NAME=<name>` as repository variables.
5. Run a `deploy.yml` dispatch against `prod`. The `Apply frontend,
   ingress, certificate` step applies the `ManagedCertificate` and
   `Ingress` resources, and the `Frontend public smoke check` step
   waits for `https://<FRONTEND_HOSTNAME>/` to return a 200.
6. The GKE-managed certificate usually provisions in 15-60 minutes.
   If the smoke check times out, inspect the ManagedCertificate status
   with `kubectl describe managedcertificate <name> -n <namespace>`.

The `hostname-https` mode is the only mode the prod release workflow
exercises in the production release summary. Dev uses `ip-http` by
default so the dev end-to-end validation does not depend on DNS.

## `ip-http`

The `ip-http` mode skips the ManagedCertificate and exposes the
frontend over plain HTTP through the reserved static IP. The
`Frontend public smoke check` step uses
`http://<STATIC_IP_ADDRESS>/` instead of the hostname.

Use this mode in environments where DNS is not available, or in CI
smoke checks that need a deterministic endpoint. The certificate is
not provisioned and the HTTPS-only checks in `release.yml` cannot run.

## Smoke checks

The deploy workflow's `Frontend public smoke check` step:

- Reads `STATIC_IP_ADDRESS` from the env-root outputs.
- Reads `FRONTEND_EXPOSURE_MODE` and `FRONTEND_HOSTNAME` from
  repository variables.
- Picks `https://<FRONTEND_HOSTNAME>/` (hostname-https) or
  `http://<STATIC_IP_ADDRESS>/` (ip-http) and polls every 10 seconds
  for 60 attempts.

A successful smoke check is required to mark the deploy workflow as
successful. Failures surface as a `::error::Frontend public endpoint
did not become ready` annotation in the workflow run and propagate to
the summary table.
