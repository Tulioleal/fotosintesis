"""Deployment rendering tests for the durable worker.

These tests run ``deploy/k8s/render.sh`` against the bundled
``values.env.example`` files and assert that:
- the worker Deployment uses the same 40-character backend image SHA
- the worker command is ``python -m app.jobs.worker``
- no Service in the rendered output selects the worker
- all job settings are rendered with no unresolved placeholders
- producer/worker enablement can be configured independently
- the migration Job runs before backend/worker rollout success
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RENDER_SCRIPT = REPO_ROOT / "deploy" / "k8s" / "render.sh"
ROLLOUT_SCRIPT = REPO_ROOT / "deploy" / "scripts" / "rollout-deployment.sh"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
BACKEND_CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backend-ci.yml"
DEV_VALUES = REPO_ROOT / "deploy" / "k8s" / "dev" / "values.env.example"
PROD_VALUES = REPO_ROOT / "deploy" / "k8s" / "prod" / "values.env.example"
ARTIFACT_REGISTRY_MODULE = (
    REPO_ROOT / "infra" / "opentofu" / "modules" / "artifact-registry" / "main.tf"
)
VALIDATE_JOB_SWITCHES_SCRIPT = (
    REPO_ROOT / "deploy" / "scripts" / "validate-job-switches.sh"
)


def _load_yaml(path: Path) -> list[dict]:
    import yaml

    with path.open(encoding="utf-8") as fh:
        return list(yaml.safe_load_all(fh))


def _find_kind(docs: list[dict], kind: str, name: str | None = None) -> dict:
    for doc in docs:
        if doc.get("kind") != kind:
            continue
        if name is None or doc.get("metadata", {}).get("name") == name:
            return doc
    raise KeyError(f"{kind} {name or ''} not found")


def _render(tmp_path: Path, values_file: Path) -> Path:
    if shutil.which("sh") is None:
        pytest.skip("sh not available")
    out = tmp_path / "rendered"
    out.mkdir()
    subprocess.run(
        ["sh", str(RENDER_SCRIPT), str(values_file), str(out)],
        check=True,
        cwd=REPO_ROOT,
    )
    return out


def _render_result(tmp_path: Path, values_file: Path) -> subprocess.CompletedProcess[str]:
    out = tmp_path / "rendered"
    out.mkdir()
    return subprocess.run(
        ["sh", str(RENDER_SCRIPT), str(values_file), str(out)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
class TestRenderedWorkerContract:
    @pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
    def test_render_emits_worker_deployment(
        self, tmp_path: Path, values_file: Path
    ) -> None:
        rendered = _render(tmp_path, values_file)
        backend_docs = _load_yaml(rendered / "30-backend.yaml")
        worker_docs = _load_yaml(rendered / "55-worker.yaml")
        backend = _find_kind(backend_docs, "Deployment", "fotosintesis-backend")
        worker = _find_kind(worker_docs, "Deployment", "fotosintesis-worker")

        backend_image = backend["spec"]["template"]["spec"]["containers"][0]["image"]
        worker_template = worker["spec"]["template"]
        worker_spec = worker_template["spec"]
        worker_container = worker_spec["containers"][0]
        assert worker_container["image"] == backend_image
        assert re.search(r":[0-9a-f]{40}$", backend_image), backend_image
        assert worker_container["command"] == ["python", "-m", "app.jobs.worker"]
        assert worker_spec["serviceAccountName"] == "fotosintesis-backend"
        assert worker_template["metadata"]["labels"][
            "iam.gke.io/workload-identity"
        ] == "fotosintesis-backend"
        assert worker_container["readinessProbe"]["httpGet"] == {
            "path": "/ready",
            "port": "metrics",
        }
        assert worker_container["resources"] == {
            "requests": {"cpu": "200m", "memory": "256Mi"},
            "limits": {"cpu": "1000m", "memory": "1536Mi"},
        }

        env_entries = {item["name"]: item for item in worker_container["env"]}
        assert env_entries["DATABASE_URL"]["valueFrom"]["secretKeyRef"]["name"] == (
            "fotosintesis-runtime"
        )
        for provider_name in (
            "MODEL_PROVIDER",
            "VISION_PROVIDER",
            "JUDGE_PROVIDER",
            "SEARCH_PROVIDER",
            "EMBEDDING_PROVIDER",
        ):
            assert env_entries[provider_name]["valueFrom"]["configMapKeyRef"]["name"] == (
                "fotosintesis-runtime-config"
            )
        for secret_name in ("OPENAI_API_KEY", "GEMINI_API_KEY"):
            assert env_entries[secret_name]["valueFrom"]["secretKeyRef"]["name"] == (
                "fotosintesis-runtime"
            )
        proxy = next(
            container
            for container in worker_spec["containers"]
            if container["name"] == "cloud-sql-proxy"
        )
        assert "--port=5432" in proxy["args"]
        assert any(
            value.endswith((":fotosintesis-dev", ":fotosintesis-prod"))
            for value in proxy["args"]
        )

        monitoring = _find_kind(
            worker_docs, "PodMonitoring", "fotosintesis-worker"
        )
        assert monitoring["spec"]["selector"]["matchLabels"] == {
            "app.kubernetes.io/name": "fotosintesis-worker"
        }
        assert monitoring["spec"]["endpoints"][0]["path"] == "/metrics"

        backend_env = {
            item["name"]: item.get("value")
            for item in backend["spec"]["template"]["spec"]["containers"][0]["env"]
        }
        worker_env = {
            item["name"]: item.get("value")
            for item in worker_container["env"]
        }
        assert backend_env["JOBS_PRODUCER_ENABLED"] == "true"
        assert backend_env["JOBS_MAX_ATTEMPTS_DEFAULT"] == "3"
        assert {
            "JOBS_WORKER_ENABLED",
            "JOBS_POLL_INTERVAL_SECONDS",
            "JOBS_BATCH_SIZE",
            "JOBS_WORKER_CONCURRENCY",
            "JOBS_LEASE_DURATION_SECONDS",
            "JOBS_LEASE_RENEWAL_INTERVAL_SECONDS",
            "JOBS_MAX_ATTEMPTS_DEFAULT",
            "JOBS_BACKOFF_BASE_SECONDS",
            "JOBS_BACKOFF_CAP_SECONDS",
            "JOBS_SHUTDOWN_DRAIN_SECONDS",
            "JOBS_METRICS_HOST",
            "JOBS_METRICS_PORT",
            "JOBS_REQUIRED_CONTRACTS",
        } <= worker_env.keys()
        assert worker_env["JOBS_REQUIRED_CONTRACTS"] == "enrich_confirmed_plant:1,refresh_profile:1"
        assert "__" not in (rendered / "30-backend.yaml").read_text(encoding="utf-8")
        assert "__" not in (rendered / "55-worker.yaml").read_text(encoding="utf-8")



    def test_job_settings_are_resolved(self, tmp_path: Path) -> None:
        rendered = _render(tmp_path, DEV_VALUES)
        text = (rendered / "55-worker.yaml").read_text(encoding="utf-8")
        for placeholder in (
            "__JOBS_PRODUCER_ENABLED__",
            "__JOBS_WORKER_ENABLED__",
            "__JOBS_POLL_INTERVAL_SECONDS__",
            "__JOBS_BATCH_SIZE__",
            "__JOBS_WORKER_CONCURRENCY__",
            "__JOBS_LEASE_DURATION_SECONDS__",
            "__JOBS_LEASE_RENEWAL_INTERVAL_SECONDS__",
            "__JOBS_MAX_ATTEMPTS_DEFAULT__",
            "__JOBS_BACKOFF_BASE_SECONDS__",
            "__JOBS_BACKOFF_CAP_SECONDS__",
            "__JOBS_SHUTDOWN_DRAIN_SECONDS__",
            "__JOBS_METRICS_HOST__",
            "__JOBS_METRICS_PORT__",
            "__JOBS_REQUIRED_CONTRACTS__",
            "__JOBS_TERMINATION_GRACE_PERIOD_SECONDS__",
        ):
            assert placeholder not in text, f"unresolved placeholder {placeholder}"

    @pytest.mark.parametrize(
        ("producer_enabled", "worker_enabled"),
        [("true", "false"), ("false", "true")],
    )
    def test_producer_and_worker_can_be_enabled_independently(
        self, tmp_path: Path, producer_enabled: str, worker_enabled: str
    ) -> None:
        # Opposing values prove the renderer does not couple the API producer
        # switch to the worker runtime switch.
        env_file = tmp_path / "values.env"
        env_file.write_text(
            DEV_VALUES.read_text(encoding="utf-8")
            + f"\nJOBS_PRODUCER_ENABLED={producer_enabled}\nJOBS_WORKER_ENABLED={worker_enabled}\n"
        )
        rendered = _render(tmp_path, env_file)
        worker = _find_kind(
            _load_yaml(rendered / "55-worker.yaml"),
            "Deployment",
            "fotosintesis-worker",
        )
        worker_env = {
            e["name"]: e.get("value")
            for e in worker["spec"]["template"]["spec"]["containers"][0]["env"]
        }
        assert worker_env.get("JOBS_WORKER_ENABLED") == worker_enabled
        backend = _find_kind(
            _load_yaml(rendered / "30-backend.yaml"),
            "Deployment",
            "fotosintesis-backend",
        )
        backend_env = {
            e["name"]: e.get("value")
            for e in backend["spec"]["template"]["spec"]["containers"][0]["env"]
        }
        assert backend_env["JOBS_PRODUCER_ENABLED"] == producer_enabled
        assert backend_env["JOBS_MAX_ATTEMPTS_DEFAULT"] == "3"

    def test_renderer_refuses_missing_values(self, tmp_path: Path) -> None:
        bad = tmp_path / "values.env"
        bad.write_text("NAMESPACE=fotosintesis\n")
        out = tmp_path / "rendered"
        out.mkdir()
        result = subprocess.run(
            ["sh", str(RENDER_SCRIPT), str(bad), str(out)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode != 0
        assert "missing values" in result.stderr.lower()

    def test_termination_grace_exceeds_drain(self, tmp_path: Path) -> None:
        rendered = _render(tmp_path, DEV_VALUES)
        worker = _find_kind(
            _load_yaml(rendered / "55-worker.yaml"),
            "Deployment",
            "fotosintesis-worker",
        )
        grace = int(worker["spec"]["template"]["spec"]["terminationGracePeriodSeconds"])
        worker_container = worker["spec"]["template"]["spec"]["containers"][0]
        drain_env = {
            e["name"]: e.get("value") for e in worker_container["env"]
        }
        drain = int(drain_env["JOBS_SHUTDOWN_DRAIN_SECONDS"])
        assert grace > drain, f"grace={grace}, drain={drain}"

    @pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
    def test_render_emits_native_complete_migration_job(
        self, tmp_path: Path, values_file: Path
    ) -> None:
        rendered = _render(tmp_path, values_file)
        migration = _find_kind(
            _load_yaml(rendered / "50-migrations.yaml"),
            "Job",
            "fotosintesis-migrations",
        )
        backend = _find_kind(
            _load_yaml(rendered / "30-backend.yaml"),
            "Deployment",
            "fotosintesis-backend",
        )
        worker = _find_kind(
            _load_yaml(rendered / "55-worker.yaml"),
            "Deployment",
            "fotosintesis-worker",
        )
        pod_spec = migration["spec"]["template"]["spec"]

        assert migration["apiVersion"] == "batch/v1"
        assert migration["kind"] == "Job"
        assert pod_spec["restartPolicy"] == "Never"
        assert [container["name"] for container in pod_spec["containers"]] == [
            "migrations"
        ]
        migration_command = " ".join(pod_spec["containers"][0]["command"])
        # The migration Job invokes the single committed migration entrypoint
        # (which contains the proxy wait and `alembic upgrade head`) rather
        # than duplicating the wrapper inline.
        assert "/app/scripts/run-migrations.sh" in migration_command
        assert "alembic" not in migration_command
        assert "upgrade" not in migration_command
        proxy = next(
            container
            for container in pod_spec["initContainers"]
            if container["name"] == "cloud-sql-proxy"
        )
        assert proxy["restartPolicy"] == "Always"

        images = {
            pod_spec["containers"][0]["image"],
            backend["spec"]["template"]["spec"]["containers"][0]["image"],
            worker["spec"]["template"]["spec"]["containers"][0]["image"],
        }
        assert len(images) == 1
        assert re.search(r":[0-9a-f]{40}$", images.pop())

    @pytest.mark.parametrize(
        ("drain", "grace", "message"),
        [
            ("30", "30", "termination grace must exceed"),
            ("30", "29", "termination grace must exceed"),
            ("not-a-number", "90", "JOBS_SHUTDOWN_DRAIN_SECONDS must be an integer"),
            (
                "30",
                "not-a-number",
                "JOBS_TERMINATION_GRACE_PERIOD_SECONDS must be an integer",
            ),
        ],
    )
    def test_renderer_rejects_invalid_worker_shutdown_timings(
        self, tmp_path: Path, drain: str, grace: str, message: str
    ) -> None:
        values_file = tmp_path / "values.env"
        values_file.write_text(
            DEV_VALUES.read_text(encoding="utf-8")
            + f"\nJOBS_SHUTDOWN_DRAIN_SECONDS={drain}"
            + f"\nJOBS_TERMINATION_GRACE_PERIOD_SECONDS={grace}\n",
            encoding="utf-8",
        )

        result = _render_result(tmp_path, values_file)

        assert result.returncode != 0
        assert message in result.stderr

    def test_resource_values_render_from_env_per_role(
        self, tmp_path: Path
    ) -> None:
        overrides = (
            "BACKEND_CPU_REQUEST=111m\n"
            "BACKEND_MEM_REQUEST=111Mi\n"
            "BACKEND_CPU_LIMIT=222m\n"
            "BACKEND_MEM_LIMIT=222Mi\n"
            "FRONTEND_CPU_REQUEST=333m\n"
            "FRONTEND_MEM_REQUEST=333Mi\n"
            "FRONTEND_CPU_LIMIT=444m\n"
            "FRONTEND_MEM_LIMIT=444Mi\n"
            "WORKER_CPU_REQUEST=555m\n"
            "WORKER_MEM_REQUEST=555Mi\n"
            "WORKER_CPU_LIMIT=666m\n"
            "WORKER_MEM_LIMIT=666Mi\n"
            "MIGRATION_CPU_REQUEST=777m\n"
            "MIGRATION_MEM_REQUEST=777Mi\n"
            "MIGRATION_CPU_LIMIT=888m\n"
            "MIGRATION_MEM_LIMIT=888Mi\n"
            "LIMITER_CLEANUP_CPU_REQUEST=999m\n"
            "LIMITER_CLEANUP_MEM_REQUEST=999Mi\n"
            "LIMITER_CLEANUP_CPU_LIMIT=1110m\n"
            "LIMITER_CLEANUP_MEM_LIMIT=1110Mi\n"
            "PROXY_CPU_REQUEST=1111m\n"
            "PROXY_MEM_REQUEST=1111Mi\n"
            "PROXY_CPU_LIMIT=1212m\n"
            "PROXY_MEM_LIMIT=1212Mi\n"
        )
        env_file = tmp_path / "values.env"
        env_file.write_text(
            DEV_VALUES.read_text(encoding="utf-8") + "\n" + overrides,
            encoding="utf-8",
        )
        rendered = _render(tmp_path, env_file)

        expectations = [
            # (manifest, kind, name, container, cpu_req, mem_req, cpu_lim, mem_lim)
            (
                "30-backend.yaml", "Deployment", "fotosintesis-backend",
                "backend", "111m", "111Mi", "222m", "222Mi",
            ),
            (
                "30-backend.yaml", "Deployment", "fotosintesis-backend",
                "cloud-sql-proxy", "1111m", "1111Mi", "1212m", "1212Mi",
            ),
            (
                "40-frontend.yaml", "Deployment", "fotosintesis-frontend",
                "frontend", "333m", "333Mi", "444m", "444Mi",
            ),
            (
                "50-migrations.yaml", "Job", "fotosintesis-migrations",
                "migrations", "777m", "777Mi", "888m", "888Mi",
            ),
            (
                "50-migrations.yaml", "Job", "fotosintesis-migrations",
                "cloud-sql-proxy", "1111m", "1111Mi", "1212m", "1212Mi",
            ),
            (
                "55-worker.yaml", "Deployment", "fotosintesis-worker",
                "worker", "555m", "555Mi", "666m", "666Mi",
            ),
            (
                "55-worker.yaml", "Deployment", "fotosintesis-worker",
                "cloud-sql-proxy", "1111m", "1111Mi", "1212m", "1212Mi",
            ),
            (
                "56-limiter-cleanup.yaml", "CronJob", "fotosintesis-limiter-cleanup",
                "limiter-cleanup", "999m", "999Mi", "1110m", "1110Mi",
            ),
            (
                "56-limiter-cleanup.yaml", "CronJob", "fotosintesis-limiter-cleanup",
                "cloud-sql-proxy", "1111m", "1111Mi", "1212m", "1212Mi",
            ),
        ]
        for (
            manifest, kind, name, container_name,
            cpu_req, mem_req, cpu_lim, mem_lim,
        ) in expectations:
            docs = _load_yaml(rendered / manifest)
            obj = _find_kind(docs, kind, name)
            if kind == "CronJob":
                pod_spec = obj["spec"]["jobTemplate"]["spec"]["template"]["spec"]
            else:
                pod_spec = obj["spec"]["template"]["spec"]
            containers = (
                pod_spec.get("containers", [])
                + pod_spec.get("initContainers", [])
            )
            container = next(
                c for c in containers if c["name"] == container_name
            )
            resources = container["resources"]
            assert resources["requests"]["cpu"] == cpu_req, (container_name, resources)
            assert resources["requests"]["memory"] == mem_req, (container_name, resources)
            assert resources["limits"]["cpu"] == cpu_lim, (container_name, resources)
            assert resources["limits"]["memory"] == mem_lim, (container_name, resources)


def selector_matches_labels(
    selector: dict[str, str],
    labels: dict[str, str],
) -> bool:
    return bool(selector) and all(
        labels.get(key) == value
        for key, value in selector.items()
    )


class TestServiceSelector:
    def test_exact_selector_match(self) -> None:
        selector = {"app": "worker"}
        labels = {"app": "worker"}
        assert selector_matches_labels(selector, labels) is True

    def test_one_label_subset_match(self) -> None:
        selector = {"app": "worker"}
        labels = {"app": "worker", "tier": "backend"}
        assert selector_matches_labels(selector, labels) is True

    def test_unrelated_selector(self) -> None:
        selector = {"app": "frontend"}
        labels = {"app": "worker"}
        assert selector_matches_labels(selector, labels) is False

    def test_empty_selector(self) -> None:
        assert selector_matches_labels({}, {"app": "worker"}) is False


def test_no_service_selects_worker_with_subset_selector_check(
    tmp_path: Path,
) -> None:
    rendered = _render(tmp_path, DEV_VALUES)
    worker = _find_kind(
        _load_yaml(rendered / "55-worker.yaml"),
        "Deployment",
        "fotosintesis-worker",
    )
    worker_labels = worker["spec"]["template"]["metadata"]["labels"]
    for service_file in rendered.glob("*.yaml"):
        docs = _load_yaml(service_file)
        for doc in docs:
            if doc.get("kind") != "Service":
                continue
            spec = doc.get("spec") or {}
            svc_selector = spec.get("selector", {})
            if selector_matches_labels(svc_selector, worker_labels):
                pytest.fail(
                    f"Service {service_file.name} selects the worker "
                    f"(selector={svc_selector}, labels={worker_labels})"
                )


def test_deploy_workflow_migration_before_backend_rollout() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    # The deploy workflow must run the migration step before the rollout
    # step that includes backend and worker.
    migration_index = text.find("Wait for migrations")
    backend_apply_index = text.find("Apply backend")
    rollout_index = text.find("Wait for rollouts")
    assert migration_index > 0
    assert backend_apply_index > migration_index
    assert rollout_index > backend_apply_index
    assert "wait_for_rollout fotosintesis-worker" in text
    assert "Native migration sidecars require Kubernetes 1.29 or newer" in text
    healthy_index = text.find("Record last healthy image pair")
    assert healthy_index > rollout_index


def test_artifact_registry_enforces_immutable_docker_tags() -> None:
    text = ARTIFACT_REGISTRY_MODULE.read_text(encoding="utf-8")
    docker_config = text[text.index("docker_config {") : text.index("}", text.index("docker_config {"))]
    assert "immutable_tags = true" in docker_config


def test_deploy_workflow_waits_for_native_migration_job_completion() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    migration_wait = text[
        text.find("name: Wait for migrations") : text.find("name: Apply worker")
    ]

    assert "kubectl wait" in migration_wait
    assert "--for=condition=complete" in migration_wait
    assert "job/fotosintesis-migrations" in migration_wait
    assert '--timeout=600s' in migration_wait
    assert "Migration Job did not complete" in migration_wait
    assert "-c migrations" in migration_wait
    assert "-c cloud-sql-proxy" in migration_wait
    assert "describe job/fotosintesis-migrations" in migration_wait
    assert "exit 1" in migration_wait
    assert "jsonpath" not in migration_wait


def test_backend_ci_triggers_when_deployment_test_dependencies_change() -> None:
    text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")
    push_paths = text[text.find("  push:") : text.find("  pull_request:")]
    pull_request_paths = text[text.find("  pull_request:") : text.find("  workflow_call:")]

    for path in (
        '".github/workflows/deploy.yml"',
        '"deploy/scripts/**"',
        '"docker-compose.yml"',
    ):
        assert path in push_paths
        assert path in pull_request_paths


def test_compose_runs_local_worker_with_postgresql_and_production_entrypoint() -> None:
    compose = _load_yaml(REPO_ROOT / "docker-compose.yml")[0]
    worker = compose["services"]["worker"]

    assert "python -m app.jobs.worker" in worker["command"]
    assert worker["environment"]["DATABASE_URL"].startswith("postgresql+asyncpg://")
    assert worker["environment"]["JOBS_WORKER_ENABLED"] == (
        "${JOBS_WORKER_ENABLED:-true}"
    )
    assert worker["environment"]["JOBS_REQUIRED_CONTRACTS"] == (
        "enrich_confirmed_plant:1,refresh_profile:1"
    )
    assert ".:/workspace" in worker["volumes"]


@pytest.mark.parametrize("exit_code", [1, 124])
def test_worker_rollout_failure_returns_nonzero_and_runs_diagnostics(
    tmp_path: Path, exit_code: int
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "kubectl-calls"
    kubectl = bin_dir / "kubectl"
    kubectl.write_text(
        "#!/usr/bin/env sh\n"
        "printf '%s\\n' \"$*\" >> \"$FAKE_KUBECTL_CALLS\"\n"
        "if [ \"$1 $2\" = \"rollout status\" ]; then exit \"$FAKE_ROLLOUT_EXIT\"; fi\n"
        "if [ \"$1 $2\" = \"get pods\" ] && printf '%s' \"$*\" | grep -q jsonpath; then "
        "printf 'worker-pod'; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)
    env = {
        **__import__("os").environ,
        "PATH": f"{bin_dir}:{__import__('os').environ['PATH']}",
        "FAKE_KUBECTL_CALLS": str(calls),
        "FAKE_ROLLOUT_EXIT": str(exit_code),
    }

    result = subprocess.run(
        [
            "sh",
            str(ROLLOUT_SCRIPT),
            "test-namespace",
            "fotosintesis-worker",
            "worker",
            "1s",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Rollout failed for fotosintesis-worker" in result.stderr
    recorded = calls.read_text(encoding="utf-8")
    assert "describe deployment/fotosintesis-worker" in recorded
    assert "logs worker-pod" in recorded
    assert "cloud-sql-proxy" in recorded


def test_worker_rollout_success_returns_zero(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    kubectl = bin_dir / "kubectl"
    kubectl.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    kubectl.chmod(0o755)
    env = {
        **__import__("os").environ,
        "PATH": f"{bin_dir}:{__import__('os').environ['PATH']}",
    }

    result = subprocess.run(
        ["sh", str(ROLLOUT_SCRIPT), "test", "fotosintesis-worker", "worker", "1s"],
        cwd=REPO_ROOT,
        env=env,
    )

    assert result.returncode == 0


def test_deploy_workflow_worker_restart_after_apply() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    worker_step = text[
        text.find("name: Apply worker") : text.find("name: Apply frontend")
    ]
    apply_index = worker_step.index("kubectl apply")
    restart_index = worker_step.index(
        "kubectl rollout restart deployment/fotosintesis-worker"
    )
    assert restart_index > apply_index


def test_deploy_verifies_compatible_worker_before_backend_can_schedule() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    worker_apply = text.index("name: Apply worker")
    compatibility = text.index("name: Confirm compatible enrichment worker readiness")
    backend_apply = text.index("name: Apply backend")

    assert worker_apply < compatibility < backend_apply
    step = text[compatibility:backend_apply]
    assert "enrich_confirmed_plant:1,refresh_profile:1" in step
    assert "JOBS_REQUIRED_CONTRACTS" in step
    assert "rollout-deployment.sh" in step
    assert "--for=condition=Ready" in step


def test_deploy_workflow_server_side_dry_run_before_migrations() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    dry_run_step = text[
        text.find("Validate workload manifests with Kubernetes API"): text.find(
            "Apply migrations before backend/worker rollout"
        )
    ]
    assert "kubectl apply" in dry_run_step
    assert "--dry-run=server" in dry_run_step
    assert "30-backend.yaml" in dry_run_step
    assert "40-frontend.yaml" in dry_run_step
    assert "50-migrations.yaml" in dry_run_step
    assert "55-worker.yaml" in dry_run_step
    assert "--dry-run=client" not in dry_run_step


def test_deploy_workflow_uses_rollout_wrapper() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    rollout_step = text[
        text.find("name: Wait for rollouts") : text.find("name: Backend health")
    ]
    assert "wait_for_rollout()" in rollout_step
    assert "result=fail" in rollout_step
    assert "result=pass" in rollout_step
    assert "wait_for_rollout fotosintesis-backend" in rollout_step
    assert "wait_for_rollout fotosintesis-worker" in rollout_step
    assert "wait_for_rollout fotosintesis-frontend" in rollout_step


def test_deploy_workflow_reports_worker_readiness_separately() -> None:
    deploy = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    release = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    readiness_index = deploy.find("name: Confirm compatible enrichment worker readiness")

    assert readiness_index < deploy.find("name: Apply backend")
    readiness_step = deploy[readiness_index : deploy.find("name: Apply backend")]
    assert "app.kubernetes.io/name=fotosintesis-worker" in readiness_step
    assert "JOBS_REQUIRED_CONTRACTS" in readiness_step
    assert "enrich_confirmed_plant:1" in readiness_step
    assert 'echo "result=pass" >> "$GITHUB_OUTPUT"' in readiness_step
    assert 'echo "result=fail" >> "$GITHUB_OUTPUT"' in readiness_step
    assert "worker_readiness_result:" in deploy
    assert "steps.worker-readiness.outputs.result" in deploy
    assert "| Worker readiness | ${WORKER_READINESS} |" in deploy
    assert "DEPLOY_WORKER_READINESS" in release
    assert '[ "$WORKER_READINESS" != "pass" ]' in release


def test_deploy_workflow_jobs_producer_default_true() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert (
        "JOBS_PRODUCER_ENABLED: "
        "${{ vars.JOBS_PRODUCER_ENABLED || 'true' }}"
    ) in text


@pytest.mark.parametrize(
    "tag",
    [
        "latest",
        "main",
        "0" * 39,
        "0" * 41,
        "A" + "0" * 39,
        "0" * 39 + "g",
        "abc/def",
        "abc:def",
    ],
)
def test_renderer_rejects_invalid_image_tags(
    tmp_path: Path, tag: str
) -> None:
    env_file = tmp_path / "values.env"
    content = DEV_VALUES.read_text(encoding="utf-8")
    content = content.replace(
        "BACKEND_IMAGE_TAG=0000000000000000000000000000000000000000",
        f"BACKEND_IMAGE_TAG={tag}",
    )
    env_file.write_text(content, encoding="utf-8")

    result = _render_result(tmp_path, env_file)

    assert result.returncode != 0
    assert "40-character lowercase hexadecimal" in result.stderr


@pytest.mark.parametrize(
    "tag",
    [
        "latest",
        "main",
        "0" * 39,
        "0" * 41,
        "A" + "0" * 39,
        "0" * 39 + "g",
        "abc/def",
        "abc:def",
    ],
)
def test_renderer_rejects_invalid_frontend_image_tags(
    tmp_path: Path, tag: str
) -> None:
    env_file = tmp_path / "values.env"
    content = DEV_VALUES.read_text(encoding="utf-8")
    content = content.replace(
        "FRONTEND_IMAGE_TAG=0000000000000000000000000000000000000000",
        f"FRONTEND_IMAGE_TAG={tag}",
    )
    env_file.write_text(content, encoding="utf-8")

    result = _render_result(tmp_path, env_file)

    assert result.returncode != 0
    assert "40-character lowercase hexadecimal" in result.stderr


def test_backend_podmonitoring_emitted(tmp_path: Path) -> None:
    rendered = _render(tmp_path, DEV_VALUES)
    backend_docs = _load_yaml(rendered / "30-backend.yaml")
    monitor = _find_kind(backend_docs, "PodMonitoring", "fotosintesis-backend")
    assert monitor["spec"]["selector"]["matchLabels"] == {
        "app.kubernetes.io/name": "fotosintesis-backend"
    }
    assert monitor["spec"]["endpoints"] == [
        {
            "port": "http",
            "path": "/metrics",
            "interval": "30s",
        }
    ]


def test_backend_podmonitoring_name_differs_from_worker(tmp_path: Path) -> None:
    rendered = _render(tmp_path, DEV_VALUES)
    backend_docs = _load_yaml(rendered / "30-backend.yaml")
    worker_docs = _load_yaml(rendered / "55-worker.yaml")
    backend_monitor = _find_kind(backend_docs, "PodMonitoring", "fotosintesis-backend")
    worker_monitor = _find_kind(worker_docs, "PodMonitoring", "fotosintesis-worker")
    assert (
        backend_monitor["spec"]["selector"]["matchLabels"]
        != worker_monitor["spec"]["selector"]["matchLabels"]
    )
    assert backend_monitor["metadata"]["name"] != worker_monitor["metadata"]["name"]


@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_backend_podmonitoring_emitted_for_all_envs(
    tmp_path: Path, values_file: Path
) -> None:
    rendered = _render(tmp_path, values_file)
    backend_docs = _load_yaml(rendered / "30-backend.yaml")
    monitor = _find_kind(backend_docs, "PodMonitoring", "fotosintesis-backend")
    assert monitor["spec"]["selector"]["matchLabels"] == {
        "app.kubernetes.io/name": "fotosintesis-backend"
    }


class TestDeploymentSwitchPolicy:
    @pytest.mark.skipif(
        not VALIDATE_JOB_SWITCHES_SCRIPT.exists(),
        reason="validate-job-switches.sh missing",
    )
    @pytest.mark.parametrize(
        ("producer", "worker", "paused", "expected"),
        [
            ("true", "false", "false", 1),
            ("true", "false", "true", 1),
            ("false", "false", "false", 1),
            ("false", "false", "true", 0),
            ("false", "true", "false", 0),
            ("true", "true", "false", 0),
            ("false", "true", "true", 1),
            ("true", "true", "true", 1),
            ("TRUE", "true", "false", 1),
            ("false", "1", "false", 1),
            ("false", "false", "yes", 1),
        ],
        ids=[
            "producer-true-worker-false",
            "producer-true-worker-false-paused",
            "both-disabled-unapproved",
            "both-disabled-paused-approved",
            "worker-true-producer-false",
            "normal-worker-true",
            "worker-true-paused",
            "both-true-paused",
            "uppercase-producer",
            "numeric-worker",
            "word-paused",
        ],
    )
    def test_job_switch_combinations_are_validated(
        self, producer: str, worker: str, paused: str, expected: int
    ) -> None:
        if shutil.which("sh") is None:
            pytest.skip("sh not available")
        result = subprocess.run(
            [
                "sh",
                str(VALIDATE_JOB_SWITCHES_SCRIPT),
                producer,
                worker,
                paused,
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == expected, result.stderr
        if expected != 0:
            assert result.stderr.strip()

    def test_deploy_workflow_validates_switches_before_migrations_and_rollout(
        self,
    ) -> None:
        text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        validation = text.index("name: Validate durable job switch combination")
        apply_migrations = text.index(
            "name: Apply migrations before backend/worker rollout"
        )
        apply_worker = text.index("name: Apply worker")
        apply_readiness = text.index(
            "name: Confirm compatible enrichment worker readiness"
        )
        apply_backend = text.index("name: Apply backend")
        assert validation < apply_migrations
        assert apply_migrations < apply_worker
        assert apply_worker < apply_readiness
        assert apply_readiness < apply_backend
        step = text[validation:apply_worker]
        assert "validate-job-switches.sh" in step
        assert "JOBS_PRODUCER_ENABLED" in step
        assert "JOBS_WORKER_ENABLED" in step
        assert "paused_deployment" in step

    def test_deploy_workflow_paused_deployment_input_declared(self) -> None:
        text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        assert "paused_deployment:" in text
        assert "type: boolean" in text

    def test_worker_readiness_requires_worker_enabled_env(self) -> None:
        text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        readiness = text[
            text.index("name: Confirm compatible enrichment worker readiness") :
        ]
        assert "JOBS_WORKER_ENABLED" in readiness
        assert '"$worker_enabled" != "true"' in readiness
        assert "JOBS_REQUIRED_CONTRACTS" in readiness
        assert "enrich_confirmed_plant:1" in readiness
        # Active-consumer readiness can be skipped only for an approved paused
        # deployment, because the preceding switch validator proves paused=true
        # implies both producer and worker are disabled. GitHub Actions
        # preserves the Boolean input type, so the condition negates it rather
        # than comparing it with a string.
        assert "if: ${{ !inputs.paused_deployment }}" in readiness
        assert "inputs.paused_deployment != 'true'" not in readiness

    def test_normal_deployment_checks_contract_and_worker_enabled(self) -> None:
        text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        readiness = text[
            text.index("name: Confirm compatible enrichment worker readiness") :
        ]
        assert "enrich_confirmed_plant:1" in readiness
        assert "JOBS_REQUIRED_CONTRACTS" in readiness
        assert "rollout-deployment.sh" in readiness
        assert "JOBS_WORKER_ENABLED" in readiness


@pytest.mark.parametrize("values_fixture", [DEV_VALUES, PROD_VALUES])
def test_enrichment_activity_settings_render_into_backend(
    tmp_path: Path, values_fixture: Path
) -> None:
    rendered = _render(tmp_path, values_fixture)
    config_text = (rendered / "20-config.yaml").read_text(encoding="utf-8")
    backend_text = (rendered / "30-backend.yaml").read_text(encoding="utf-8")

    assert "__ENRICHMENT_ACTIVITY_" not in config_text
    assert "__ENRICHMENT_ACTIVITY_" not in backend_text
    assert (
        "ENRICHMENT_ACTIVITY_TERMINAL_RETENTION_HOURS" in backend_text
    )
    assert "ENRICHMENT_ACTIVITY_MAX_ITEMS" in backend_text

    values = values_fixture.read_text(encoding="utf-8")
    assert "ENRICHMENT_ACTIVITY_TERMINAL_RETENTION_HOURS=24" in values
    assert "ENRICHMENT_ACTIVITY_MAX_ITEMS=20" in values
