## 1. Runtime Inventory and Baseline

- [x] 1.1 Inventory the effective UID/GID, owned paths, cache/home/temp writes, and production entrypoints for backend API, worker, and migration execution.
- [x] 1.2 Inventory every regular container, init container, and native sidecar in each rendered environment, including current security contexts, writable mounts, and CPU/memory settings.
- [x] 1.3 Select and document the fixed backend runtime UID/GID plus initial role-specific resource requests and limits using current development observations.

## 2. Backend Image Hardening

- [x] 2.1 Update the final backend image stage to create the fixed unprivileged user/group, assign only required ownership, and set the non-root user as the image default.
- [x] 2.2 Disable or redirect avoidable runtime caches and configure explicit home, temporary, upload-staging, or migration paths identified by the write inventory.
- [x] 2.3 Add image checks that assert the documented non-zero default UID/GID and reject UID 0.
- [x] 2.4 Add bounded final-image smoke tests for the exact production API, worker, and migration commands without a user override.

## 3. Kubernetes Security Controls

- [x] 3.1 Add pod security contexts with the intended runtime IDs and `RuntimeDefault` seccomp to backend API, frontend, worker, and migration workloads.
- [x] 3.2 Add container security contexts that require non-root execution, disable privilege escalation, and drop `ALL` Linux capabilities for every application container.
- [x] 3.3 Apply compatible restrictions to init containers and sidecars, and document each unsupported field with the exact container, reason, and compensating control.
- [x] 3.4 Enable read-only root filesystems where verified and add only the explicit writable volume mounts required by each workload.

## 4. Resource Governance

- [x] 4.1 Add CPU and memory requests and limits for backend API, frontend, worker, migration, Cloud SQL proxy, and every other regular container, init container, and native sidecar.
- [x] 4.2 Keep development and production values explicit in the existing environment rendering mechanism and use documented role-specific profiles rather than implicit defaults.
- [x] 4.3 Document the initial resource assumptions and the review process for tuning values after throttling, OOM, usage, or scheduling observations.

## 5. Policy and Regression Verification

- [x] 5.1 Add a pinned Checkov or equivalent manifest-policy step covering root execution, privilege escalation, capability drops, seccomp, read-only roots, and resource declarations.
- [x] 5.2 Add rendered-manifest tests that enumerate regular containers, init containers, and native sidecars in every environment and fail on missing security or CPU/memory fields.
- [x] 5.3 Add policy fixtures for valid explicit writable mounts, missing required fields, and narrowly scoped documented exceptions.
- [x] 5.4 Run existing multilingual semantic regression coverage and, if runtime-path changes touch semantic execution, add cases proving non-English, synonym, and paraphrased evidence still reaches semantic judging without keyword matching.

## 6. Deployment Validation and Operations

- [ ] 6.1 Deploy the hardened immutable images and rendered manifests to development and verify migrations, API/frontend health, representative worker processing, uploads, and configured provider calls.
- [ ] 6.2 Perform controlled CPU and memory pressure verification and record that throttling or termination remains workload-bounded and recoverable through Kubernetes.
- [x] 6.3 Update deployment documentation with image identity checks, writable-path assumptions, policy exceptions, resource tuning, rollout verification, and rollback commands.
- [ ] 6.4 Verify rollback to a prior reviewed immutable image and compatible manifests retains non-root execution and explicit resource bounds.
