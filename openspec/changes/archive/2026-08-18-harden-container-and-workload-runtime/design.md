## Context

The backend image is shared by the API, durable worker, and migration job, but it does not establish an unprivileged runtime identity. Kubernetes manifests also apply security and resource settings unevenly: some worker and Cloud SQL proxy resources are bounded, while application containers and migration execution are not consistently constrained. The change crosses image construction, runtime filesystem behavior, plain Kubernetes manifests, environment configuration, CI policy checks, and deployment verification.

The baseline must remain compatible with health checks, migrations, background jobs, uploads, provider integrations, Workload Identity, External Secrets, and Cloud SQL Auth Proxy connectivity. This is an infrastructure safety boundary only; it does not alter multilingual botanical semantics and must not introduce hardcoded keyword matching, token checks, or language-specific word lists.

## Goals / Non-Goals

**Goals:**

- Establish a fixed non-root backend UID and GID and prove that every production backend command runs with that identity.
- Minimize writable image paths and make runtime writes explicit in workload storage configuration.
- Apply a reviewable security-context baseline independently of image metadata.
- Bound CPU and memory consumption for every deployed container while allowing explicit per-environment values.
- Fail CI when built images or rendered manifests violate enforceable invariants.
- Verify real development-cluster behavior before promoting the same image and policy structure.

**Non-Goals:**

- Add Kubernetes NetworkPolicy resources or claim complete container sandboxing.
- Resize GKE node pools automatically or implement automatic resource tuning.
- Redesign application upload, provider, or job-level limits.
- Change application classification, retrieval, evidence, answerability, or language behavior.

## Decisions

### Use one fixed backend runtime identity

The final backend image stage will create a dedicated group and user with fixed non-zero numeric IDs and set that user as the image default. Build and dependency-install stages may use root, but the final image will grant the runtime identity ownership only of files and directories it must read or write. API, worker, and migration commands will be exercised against the same final image.

Fixed numeric IDs make Kubernetes `runAsUser`, `runAsGroup`, and `fsGroup` behavior predictable across environments. Relying only on a named Dockerfile user was rejected because manifests could not independently enforce the expected identity. Creating separate images or users for API, worker, and migration was rejected because they share code and dependencies and currently promote as one immutable backend artifact.

### Inventory writes before enabling read-only roots

Runtime cache, home, upload-staging, and temporary-file behavior will be observed with the exact production commands. Avoidable caches will be disabled or redirected; required writes will use narrowly scoped directories backed by bounded `emptyDir` volumes where appropriate. Application containers will use `readOnlyRootFilesystem: true` unless a committed exception identifies the workload, failing operation, and required writable path.

Making broad image directories writable was rejected because it obscures runtime dependencies and weakens the containment benefit. Enabling read-only roots globally without testing was rejected because libraries and migration tooling can fail on implicit cache or temporary writes.

### Enforce security at pod and container levels

Pod security contexts will define shared identity and `seccompProfile.type: RuntimeDefault`. Each application container will independently set `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, and drop `ALL` Linux capabilities; numeric user/group fields will be supplied where image compatibility permits deterministic enforcement. Init containers and sidecars will receive equivalent restrictions when supported by their vendor images, with any exception documented and policy-visible.

Enforcing only Dockerfile metadata was rejected because an image or manifest override could restore root execution. Depending only on cluster admission policy was also rejected because repository review and local rendering must expose the intended workload contract.

### Keep resources explicit in environment manifests

Every regular container, init container, and native sidecar will declare CPU and memory requests and limits. Initial values will be conservative estimates informed by existing worker and proxy values and observed development behavior. Environment-specific overlays or rendered values will carry explicit settings, including larger worker allowances for model and embedding work and migration allowances for schema operations.

Leaving values to namespace defaults was rejected because the effective resources would be less visible in code review. Using one shared profile for every command was rejected because API, frontend, worker, migration, and proxy workloads have materially different resource behavior.

### Combine deterministic policy checks with runtime smoke tests

CI will inspect the final backend image user and execute API, worker, and migration smoke commands as the image default user. Rendered-manifest checks will enumerate all pod-spec container classes and assert security-context, resource, and writable-volume invariants. Checkov or an equivalent pinned policy tool may provide standard checks, supplemented by repository checks where generic rules do not cover native sidecars, explicit exceptions, or environment rendering.

Static checks alone were rejected because they cannot detect root-owned runtime paths or commands that fail under the unprivileged identity. Runtime tests alone were rejected because they cannot ensure every rendered environment and container receives the required declarations.

## Risks / Trade-offs

- [Libraries write to implicit root-owned cache or home paths] -> Disable unnecessary caches, configure explicit locations, and cover exact production commands with image smoke tests.
- [Migration tooling requires writable home or temporary storage] -> Exercise the production migration command and mount only the demonstrated path.
- [Read-only filesystems break uploads or temporary files] -> Separate persistent object-storage behavior from bounded temporary staging and add focused development-cluster tests.
- [Initial limits cause CPU throttling or OOM termination] -> Start with measured conservative values, observe per-workload metrics and events, and adjust explicit environment values through review.
- [Requests are oversized and reduce scheduling capacity] -> Compare requests with observed steady-state usage and document tuning decisions.
- [Third-party sidecar images cannot satisfy one field] -> Require a narrowly scoped, documented exception with compensating controls rather than silently omitting the baseline.
- [Policy checks miss a container class] -> Enumerate regular containers, init containers, and native sidecars in rendered-manifest test fixtures.

## Migration Plan

1. Inventory current image users, ownership, runtime writes, container classes, and environment resource values.
2. Build the backend final stage with the fixed unprivileged identity and make API, worker, and migration image smoke tests pass.
3. Add explicit writable volumes and hardened security contexts to application manifests, then add resources for every container class and environment.
4. Add deterministic image and rendered-manifest policy gates, including checks that every exception is documented.
5. Deploy the immutable image and rendered policy structure to development; run migrations and verify API health, frontend health, worker processing, uploads, provider calls, throttling, OOM behavior, and recovery.
6. Promote the same reviewed images and manifest structure after development verification.

Rollback redeploys the prior reviewed immutable image and compatible manifests. A rollback may relax a newly incompatible read-only-path setting through a documented emergency exception, but it must retain the established non-root and resource baseline rather than reverting to unbounded workloads.

## Open Questions

- Which numeric UID/GID is currently unused and compatible with local bind-mounted development workflows?
- Which backend and frontend paths are proven writable under each production command?
- What initial CPU and memory values follow from current development metrics for API, frontend, worker, migration, and each proxy?
- Does every third-party sidecar image support the complete non-root and read-only-root baseline, or is a narrowly scoped exception required?
