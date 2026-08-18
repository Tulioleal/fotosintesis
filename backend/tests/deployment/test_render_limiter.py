"""Deployment rendering tests for the authentication limiter.

These tests render ``deploy/k8s/render.sh`` against the bundled values files
and verify every frontend and backend replica receives compatible limiter
settings, the cleanup CronJob is emitted with Cloud SQL connectivity, secret
material is projected from External Secrets (never committed inline), the
trusted proxy hop count is documented and consistent, and rendered ConfigMap
values are all strings as Kubernetes requires.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
RENDER_SCRIPT = REPO_ROOT / "deploy" / "k8s" / "render.sh"
DEV_VALUES = REPO_ROOT / "deploy" / "k8s" / "dev" / "values.env.example"
PROD_VALUES = REPO_ROOT / "deploy" / "k8s" / "prod" / "values.env.example"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"


def _render(tmp_path: Path, values_file: Path) -> Path:
    out = tmp_path / "rendered"
    result = subprocess.run(
        ["sh", str(RENDER_SCRIPT), str(values_file), str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out


def _load_yaml(path: Path) -> list[dict]:
    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    return [doc for doc in docs if doc is not None]


def _deployment_env(path: Path) -> dict[str, str]:
    docs = _load_yaml(path)
    deployment = next(doc for doc in docs if doc.get("kind") == "Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    env = {}
    for item in container.get("env", []):
        if "value" in item:
            env[item["name"]] = item["value"]
        elif "valueFrom" in item and "configMapKeyRef" in item["valueFrom"]:
            env[item["name"]] = f"config:{item['valueFrom']['configMapKeyRef']['key']}"
        elif "valueFrom" in item and "secretKeyRef" in item["valueFrom"]:
            env[item["name"]] = f"secret:{item['valueFrom']['secretKeyRef']['key']}"
    return env


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_limiter_settings_rendered_without_placeholders(
    tmp_path: Path, values_file: Path
) -> None:
    rendered = _render(tmp_path, values_file)
    for manifest in ("20-config.yaml", "30-backend.yaml", "40-frontend.yaml", "56-limiter-cleanup.yaml"):
        text = (rendered / manifest).read_text(encoding="utf-8")
        assert "__" not in text, f"unresolved placeholder in {manifest}"


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_rendered_configmap_values_are_all_strings(tmp_path: Path, values_file: Path) -> None:
    rendered = _render(tmp_path, values_file)
    config = _load_yaml(rendered / "20-config.yaml")[0]
    assert config["kind"] == "ConfigMap"
    data = config["data"]
    assert data, "ConfigMap data must not be empty"
    for key, value in data.items():
        assert isinstance(value, str), (
            f"ConfigMap.data['{key}'] must be a string, got {type(value).__name__}"
        )


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_backend_receives_limiter_secrets_from_runtime_secret(
    tmp_path: Path, values_file: Path
) -> None:
    rendered = _render(tmp_path, values_file)
    env = _deployment_env(rendered / "30-backend.yaml")
    assert env["AUTH_LIMITER_HMAC_SECRET"].startswith("secret:")
    assert env["AUTH_LIMITER_ASSERTION_SECRET"].startswith("secret:")
    assert env["AUTH_LIMITER_ENABLED"] == "config:AUTH_LIMITER_ENABLED"


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_frontend_receives_limiter_secrets_and_trusted_hops(
    tmp_path: Path, values_file: Path
) -> None:
    rendered = _render(tmp_path, values_file)
    env = _deployment_env(rendered / "40-frontend.yaml")
    assert env["AUTH_LIMITER_HMAC_SECRET"].startswith("secret:")
    assert env["AUTH_LIMITER_ASSERTION_SECRET"].startswith("secret:")
    assert env["AUTH_LIMITER_TRUSTED_FORWARDED_HOPS"] == "config:AUTH_LIMITER_TRUSTED_FORWARDED_HOPS"


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_limiter_cleanup_cronjob_is_emitted(tmp_path: Path, values_file: Path) -> None:
    rendered = _render(tmp_path, values_file)
    docs = _load_yaml(rendered / "56-limiter-cleanup.yaml")
    cronjob = next(doc for doc in docs if doc.get("kind") == "CronJob")
    assert cronjob["metadata"]["name"] == "fotosintesis-limiter-cleanup"
    assert cronjob["spec"]["concurrencyPolicy"] == "Forbid"
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    assert container["name"] == "limiter-cleanup"
    command = " ".join(container["command"])
    assert "scripts.cleanup_limiter_state" in command
    env_names = {item["name"] for item in container.get("env", [])}
    assert "AUTH_LIMITER_RETENTION_SECONDS" in env_names
    assert "AUTH_LIMITER_CLEANUP_BATCH_SIZE" in env_names


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_limiter_cleanup_cronjob_can_reach_cloud_sql_via_proxy_sidecar(
    tmp_path: Path, values_file: Path
) -> None:
    rendered = _render(tmp_path, values_file)
    docs = _load_yaml(rendered / "56-limiter-cleanup.yaml")
    cronjob = next(doc for doc in docs if doc.get("kind") == "CronJob")
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    init = next(
        container
        for container in pod_spec.get("initContainers", [])
        if container["name"] == "cloud-sql-proxy"
    )
    assert init["restartPolicy"] == "Always"
    assert "--port=" in " ".join(init["args"])
    container = pod_spec["containers"][0]
    command = " ".join(container["command"])
    assert "__CLOUD_SQL_PROXY_PORT__" not in command
    # The cleanup command waits for the local proxy before running.
    assert "127.0.0.1" in command
    env_names = {item["name"] for item in container.get("env", [])}
    assert "DATABASE_URL" in env_names
    assert "AUTH_LIMITER_RETENTION_SECONDS" in env_names
    # The workload-identity label matches the backend service account that the
    # proxy uses to reach Cloud SQL.
    pod_meta = cronjob["spec"]["jobTemplate"]["spec"]["template"]["metadata"]
    labels = pod_meta.get("labels", {})
    assert "iam.gke.io/workload-identity" in labels


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
def test_external_secrets_project_limiter_secrets(tmp_path: Path) -> None:
    rendered = _render(tmp_path, PROD_VALUES)
    docs = _load_yaml(rendered / "80-external-secrets.yaml")
    external_secret = next(doc for doc in docs if doc.get("kind") == "ExternalSecret")
    secret_keys = {entry["secretKey"] for entry in external_secret["spec"]["data"]}
    assert "auth-limiter-hmac-secret" in secret_keys
    assert "auth-limiter-assertion-secret" in secret_keys


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
def test_prod_limiter_enforcement_enabled_as_string(tmp_path: Path) -> None:
    rendered = _render(tmp_path, PROD_VALUES)
    config = _load_yaml(rendered / "20-config.yaml")[0]
    assert config["data"]["AUTH_LIMITER_ENABLED"] == "true"


@pytest.mark.skipif(not DEPLOY_WORKFLOW.exists(), reason="deploy workflow missing")
def test_deploy_workflow_server_side_dry_run_includes_cleanup_cronjob() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    dry_run_step = text[
        text.find("Validate workload manifests with Kubernetes API") : text.find(
            "Apply migrations before backend/worker rollout"
        )
    ]
    assert "kubectl apply" in dry_run_step
    assert "--dry-run=server" in dry_run_step
    assert "56-limiter-cleanup.yaml" in dry_run_step


@pytest.mark.skipif(not DEPLOY_WORKFLOW.exists(), reason="deploy workflow missing")
def test_deploy_workflow_applies_cleanup_cronjob_after_migrations() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    migrations_wait = text.index("name: Wait for migrations")
    cleanup_apply = text.index("name: Apply limiter cleanup CronJob")
    worker_apply = text.index("name: Apply worker")
    # The CronJob is applied only after migrations complete and before any
    # application rollout.
    assert migrations_wait < cleanup_apply < worker_apply
    step = text[cleanup_apply:worker_apply]
    assert "kubectl apply" in step
    assert "56-limiter-cleanup.yaml" in step
    # Idempotent apply only; no one-off Job trigger and no rollout semantics
    # for a CronJob.
    assert "rollout" not in step
    assert "create job" not in step
    assert "kubectl delete job" not in step


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_trusted_forwarded_hops_is_documented_and_consistent(
    tmp_path: Path, values_file: Path
) -> None:
    rendered = _render(tmp_path, values_file)
    config = _load_yaml(rendered / "20-config.yaml")[0]
    hops = config["data"]["AUTH_LIMITER_TRUSTED_FORWARDED_HOPS"]
    if values_file == PROD_VALUES:
        assert hops == "2"
    else:
        assert hops == "0"
    env = _deployment_env(rendered / "40-frontend.yaml")
    assert env["AUTH_LIMITER_TRUSTED_FORWARDED_HOPS"] == "config:AUTH_LIMITER_TRUSTED_FORWARDED_HOPS"
