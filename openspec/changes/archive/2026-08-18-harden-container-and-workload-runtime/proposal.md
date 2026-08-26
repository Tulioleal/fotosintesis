## Why

Application images and Kubernetes workloads do not consistently enforce a non-root runtime identity, restrictive security contexts, or bounded CPU and memory usage. A verifiable baseline is needed so API, worker, migration, frontend, and sidecar execution cannot silently regain unnecessary privileges or consume unbounded node resources.

## What Changes

- Build the backend image with a fixed unprivileged runtime user and group that can access only required application and writable paths.
- Run backend API, worker, and migration commands under the unprivileged identity and verify those production commands in the built image.
- Apply pod and container security contexts to application workloads, including non-root execution, disabled privilege escalation, dropped Linux capabilities, and `RuntimeDefault` seccomp.
- Use read-only root filesystems where supported and provide explicit writable temporary volumes only where runtime behavior requires them.
- Declare environment-specific CPU and memory requests and limits for every regular container, init container, and native sidecar.
- Add rendered-manifest policy checks, image runtime checks, workload smoke tests, and documentation for justified security or resource exceptions.
- Document initial resource assumptions, operational tuning, rollout verification, and bounded-failure expectations.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-foundation`: Require the backend image and its API, worker, and migration commands to operate under a fixed unprivileged runtime identity with minimal writable paths.
- `testing-deployment`: Require automated image and rendered-manifest checks for runtime identity, security contexts, writable storage, and container resource declarations.
- `gcp-deployment-platform`: Require deployed application workloads and supporting containers to enforce the runtime security baseline and environment-specific resource governance.

## Impact

- Backend and potentially frontend Dockerfiles, runtime entrypoints, ownership, cache, home, and temporary-directory configuration.
- Plain Kubernetes manifests and environment overlays for backend, frontend, worker, migration, init, proxy, and other sidecar containers.
- CI policy tooling and smoke tests for built images and rendered manifests.
- Deployment verification and operations documentation for resource tuning, exceptions, rollout, recovery, and rollback.
- Development-cluster validation of health checks, migrations, background jobs, uploads, and provider calls under the hardened runtime.
