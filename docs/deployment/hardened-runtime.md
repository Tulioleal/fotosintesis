# Hardened Container and Workload Runtime

This document records the runtime identity, writable-path inventory, security
baseline, and resource assumptions behind the hardening change. It is the
single source of truth for the image and rendered-manifest checks.

## Runtime identity

The shared backend image (used by the API, durable worker, migration Job, and
limiter cleanup) runs under a fixed unprivileged identity:

| Field | Value |
| --- | --- |
| UID | `10001` |
| GID | `10001` |
| Image default | `USER 10001:10001` |
| Home | `/tmp` |

`10001` is unused by the OS, by the frontend image (`1001`), and by the
Cloud SQL proxy image, so pod and container `runAsUser` / `runAsGroup` can
enforce the same deterministic identity as the Dockerfile. The image check in
`backend/scripts/check-image-runtime.sh` rejects any default of UID 0 and
asserts the exact `10001:10001` identity.

The frontend image uses `nextjs:1001` (fixed in its Dockerfile). The Cloud SQL
Auth Proxy image runs as its own non-root user; its security context uses
`runAsNonRoot: true` without pinning a numeric UID.

The backend image keeps `/app` root-owned and read-only. The runtime user has
no writable ownership inside the image; the image does not run
`chown -R app:app /app`. `HOME=/tmp` and the local object-storage root default
to `/tmp`, so all runtime writes land under the writable `/tmp` mount.

## Production entrypoints

| Workload | Image | Command |
| --- | --- | --- |
| API | backend | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Worker | backend | `python -m app.jobs.worker` |
| Migration | backend | wait-for-proxy, then `alembic upgrade head` |
| Limiter cleanup | backend | wait-for-proxy, then `python -m scripts.cleanup_limiter_state` |
| Frontend | frontend | `node frontend/server.js` |
| Cloud SQL proxy | proxy image | `--structured-logs --port=<port> <instance>` |

## Writable-path inventory

Observed runtime writes for the backend production commands:

| Path | Purpose | Handling |
| --- | --- | --- |
| `/tmp` | Python temporary files, `PYTHONPYCACHEPREFIX`, `HOME`, and the local object-storage staging root (`/tmp/storage-data`) | Backed by an `emptyDir` volume, writable |
| Image root filesystem | `/app` and all other application/system paths | root-owned, read-only (`readOnlyRootFilesystem: true`) |

`PYTHONPYCACHEPREFIX=/tmp/pycache` and `PYTHONDONTWRITEBYTECODE=1` in the
image redirect or disable bytecode cache writes so they cannot hit a
read-only root. Every application container mounts an explicit `emptyDir`
volume at `/tmp` (the generic writable path); the image root filesystem,
including `/app`, stays read-only. The image is never made writable through a
broad `/app` mount or a `chown` of the application tree.

## Security context baseline

Every application container enforces:

- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: [ALL]`
- pod-level `seccompProfile.type: RuntimeDefault` (and `fsGroup`)
- numeric `runAsUser` / `runAsGroup` on each application container (backend
  image `10001`, frontend image `1001`; the pod-level context does not set a
  numeric UID so the proxy is not forced onto the backend identity)
- `readOnlyRootFilesystem: true` with explicit writable `emptyDir` mounts

### Supporting containers

The Cloud SQL Auth Proxy sidecar/init container runs as its vendor image's
non-root user (the default image is `distroless`, which has no shell and runs
as its own non-root user, not the backend identity). Its security context uses
`runAsNonRoot: true`, `allowPrivilegeEscalation: false`,
`capabilities.drop: [ALL]`, and `readOnlyRootFilesystem: true` (the proxy
listens on TCP and needs no writable path). The pod-level security context
enforces `seccompProfile.type: RuntimeDefault` and `fsGroup` at the pod scope
shared by all containers, but does **not** set a numeric `runAsUser` /
`runAsGroup`, so the proxy is never forced onto the backend `10001` identity.

Effective proxy identity: the image's own non-root user (the distroless
`nonroot` user), with `runAsNonRoot: true` as the deterministic enforcement.
This is validated on the development cluster (task 14, "no proxy permission
errors") before promotion.

## Resource profiles

Environment-specific values are declared in each environment's rendered
manifests (via `deploy/k8s/render.sh` using `values.env`). Initial values are
conservative estimates based on the existing worker/proxy settings and
observed development behavior.

| Workload role | requests cpu | requests mem | limits cpu | limits mem |
| --- | --- | --- | --- | --- |
| API (backend) | `200m` | `256Mi` | `1000m` | `1024Mi` |
| Frontend | `100m` | `128Mi` | `500m` | `512Mi` |
| Worker | `200m` | `256Mi` | `1000m` | `1536Mi` |
| Migration | `200m` | `256Mi` | `1000m` | `1024Mi` |
| Limiter cleanup | `50m` | `64Mi` | `500m` | `256Mi` |
| Cloud SQL proxy (sidecar) | `100m` | `64Mi` | `500m` | `256Mi` |
| Cloud SQL proxy (migration/cleanup init) | `100m` | `64Mi` | `500m` | `256Mi` |

### Tuning process

These are starting values, not guarantees. When monitoring shows sustained CPU
throttling (`container_cpu_usage_seconds_total` vs `limit`), OOMKills, or
scheduling pressure, update the explicit value for the affected role in the
environment's `deploy/k8s/{dev,prod}/values.env` (base manifests hold
placeholders only; the renderer fails if any value is absent) through review.
Requests should track steady-state usage to avoid wasting scheduling capacity;
limits should bound worst-case bursts. Always retain both requests and limits
for every container after tuning.

## Policy exceptions

There are no committed application-container exceptions: every application
container satisfies the full baseline. The `cloud-sql-proxy` sidecar/init
container satisfies the security-context baseline (non-root, no privilege
escalation, dropped capabilities, read-only root, `RuntimeDefault` seccomp)
with a single documented, policy-visible deviation: it does not pin a numeric
`runAsUser` / `runAsGroup` because it must run as its vendor image's own
non-root user (the distroless `nonroot` user) rather than the backend
identity. `runAsNonRoot: true` is the compensating control, and the pod-level
security context omits a numeric UID so the proxy is never forced onto `10001`.
Any future exception must identify the exact container, the unsupported field,
the concrete workload reason, and the compensating control in this document
and be covered by a rendered-manifest test fixture.
