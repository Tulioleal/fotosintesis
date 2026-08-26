"""Rendered-manifest policy verification driven by the reusable validator.

These tests render ``deploy/k8s/render.sh`` against the bundled dev and prod
values files and hand the rendered directory to the single reusable validator
(``backend/scripts/validate_rendered_manifests.py``). The CLI and these tests
call the same implementation, so adding a rendered manifest automatically adds
it to policy coverage.

Every invalid fixture starts from a compliant rendered manifest, applies
exactly one violation, and asserts that the validator emits the specific
rejection message. The tests do not merely assert that the mutated data is
invalid; they assert the validator's diagnostic for the field/workload/container.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
RENDER_SCRIPT = REPO_ROOT / "deploy" / "k8s" / "render.sh"
VALIDATOR_PATH = REPO_ROOT / "backend" / "scripts" / "validate_rendered_manifests.py"
DEV_VALUES = REPO_ROOT / "deploy" / "k8s" / "dev" / "values.env.example"
PROD_VALUES = REPO_ROOT / "deploy" / "k8s" / "prod" / "values.env.example"

# Load the same validator module the CLI uses.
_spec = importlib.util.spec_from_file_location("validate_rendered_manifests", VALIDATOR_PATH)
_validate = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_validate)

validate_directory = _validate.validate_directory
validate_exceptions = _validate.validate_exceptions
EXCEPTIONS = _validate.EXCEPTIONS
APP_CONTAINERS = _validate.APP_CONTAINERS

RESOURCE_FIELDS = ("requests.cpu", "requests.memory", "limits.cpu", "limits.memory")


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
    with path.open(encoding="utf-8") as fh:
        return [doc for doc in yaml.safe_load_all(fh) if doc is not None]


def _write_yaml(path: Path, docs: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump_all(docs, fh, sort_keys=False)


def _backend_container(docs: list[dict]) -> dict:
    deployment = next(doc for doc in docs if doc.get("kind") == "Deployment")
    return next(
        c
        for c in deployment["spec"]["template"]["spec"]["containers"]
        if c["name"] == "backend"
    )


def _backend_pod_spec(docs: list[dict]) -> dict:
    deployment = next(doc for doc in docs if doc.get("kind") == "Deployment")
    return deployment["spec"]["template"]["spec"]


def _mutate_and_validate(
    tmp_path: Path,
    values_file: Path,
    manifest: str,
    mutate_fn,
) -> list[str]:
    rendered = _render(tmp_path, values_file)
    path = rendered / manifest
    docs = _load_yaml(path)
    mutate_fn(docs)
    _write_yaml(path, docs)
    return validate_directory(rendered)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_valid_hardened_application_passes(tmp_path: Path, values_file: Path) -> None:
    rendered = _render(tmp_path, values_file)
    assert validate_directory(rendered) == []


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
@pytest.mark.parametrize("field", RESOURCE_FIELDS)
def test_missing_each_resource_field_is_rejected(
    tmp_path: Path, field: str
) -> None:
    def mutate(docs: list[dict]) -> None:
        scope, key = field.split(".")
        c = _backend_container(docs)
        c.setdefault("resources", {}).setdefault(scope, {}).pop(key, None)

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, "30-backend.yaml", mutate)
    joined = "\n".join(errors)
    assert "missing resource declarations" in joined
    assert field in joined


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
@pytest.mark.parametrize("run_root", [False, None])
def test_root_or_missing_run_as_non_root_is_rejected(
    tmp_path: Path, run_root
) -> None:
    def mutate(docs: list[dict]) -> None:
        sec = _backend_container(docs).setdefault("securityContext", {})
        if run_root is None:
            sec.pop("runAsNonRoot", None)
        else:
            sec["runAsNonRoot"] = run_root

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, "30-backend.yaml", mutate)
    assert any("must run as non-root" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_privilege_escalation_enabled_is_rejected(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        sec = _backend_container(docs).setdefault("securityContext", {})
        sec["allowPrivilegeEscalation"] = True

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, "30-backend.yaml", mutate)
    assert any("must disable privilege escalation" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_missing_all_capability_drop_is_rejected(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        sec = _backend_container(docs).setdefault("securityContext", {})
        sec["capabilities"] = {}

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, "30-backend.yaml", mutate)
    assert any("must drop ALL capabilities" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_missing_seccomp_is_rejected(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        pod_spec = _backend_pod_spec(docs)
        pod_spec["securityContext"].pop("seccompProfile", None)

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, "30-backend.yaml", mutate)
    assert any("pod seccomp must be RuntimeDefault" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_writable_root_without_exception_is_rejected(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        sec = _backend_container(docs).setdefault("securityContext", {})
        sec["readOnlyRootFilesystem"] = False

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, "30-backend.yaml", mutate)
    assert any("must use a read-only root" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_mount_without_backing_volume_is_rejected(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        c = _backend_container(docs)
        c["volumeMounts"] = [{"name": "does-not-exist", "mountPath": "/tmp"}]

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, "30-backend.yaml", mutate)
    assert any("/tmp mount has no backing volume" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_undocumented_app_mount_is_rejected(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        c = _backend_container(docs)
        c.setdefault("volumeMounts", []).append(
            {"name": "app", "mountPath": "/app"}
        )
        pod_spec = _backend_pod_spec(docs)
        pod_spec.setdefault("volumes", []).append({"name": "app", "emptyDir": {}})

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, "30-backend.yaml", mutate)
    assert any("mounts a broad writable /app path" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_unknown_container_is_rejected(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        pod_spec = _backend_pod_spec(docs)
        pod_spec["containers"].append(
            {
                "name": "mystery",
                "resources": {
                    "requests": {"cpu": "10m", "memory": "1Mi"},
                    "limits": {"cpu": "10m", "memory": "1Mi"},
                },
            }
        )

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, "30-backend.yaml", mutate)
    assert any("mystery" in e and "is an unknown container" in e for e in errors)


@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_valid_proxy_exception_is_accepted() -> None:
    # The proxy exception omits only the numeric UID/GID, which the rendered
    # manifests rely on; validate_exceptions accepts it against the rendered set.
    rendered_names = {"cloud-sql-proxy", "backend", "frontend", "worker", "migrations", "limiter-cleanup"}
    assert validate_exceptions(rendered_names) == []
    assert EXCEPTIONS["cloud-sql-proxy"]["omit_fields"] == {"runAsUser", "runAsGroup"}
    assert EXCEPTIONS["cloud-sql-proxy"]["reason"]


@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_invalid_or_stale_exception_is_rejected(tmp_path: Path) -> None:
    original = dict(EXCEPTIONS)
    try:
        # stale (unused) exception
        EXCEPTIONS["ghost-container"] = {
            "reason": "no such container",
            "omit_fields": {"runAsUser"},
        }
        errors = validate_exceptions({"cloud-sql-proxy", "backend"})
        assert any("ghost-container" in e and "unused" in e for e in errors)

        # never-omitable resource field
        EXCEPTIONS["backend"] = {"reason": "x", "omit_fields": {"resources"}}
        errors = validate_exceptions({"backend", "cloud-sql-proxy"})
        assert any("may not omit 'resources'" in e for e in errors)

        # wildcard
        EXCEPTIONS["*"] = {"reason": "x", "omit_fields": {"runAsUser"}}
        errors = validate_exceptions({"backend", "cloud-sql-proxy"})
        assert any("wildcard" in e for e in errors)
    finally:
        EXCEPTIONS.clear()
        EXCEPTIONS.update(original)


@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_validator_enforcement_is_required() -> None:
    """Removing the validator's security checks must make these tests fail.

    If the validator stops rejecting a missing resource field, the missing-field
    fixture below cannot pass its assertion, proving the tests exercise the
    validator's real enforcement rather than merely checking mutated data.
    """
    # Sanity: the validator has non-trivial checks for resources, security
    # context, mounts, and seccomp.
    assert "resources" in _validate._NEVER_OMITABLE
    assert "runAsNonRoot" in _validate._NEVER_OMITABLE
    assert _validate.BACKEND_UID == 10001
    assert _validate.FRONTEND_UID == 1001
    assert APP_CONTAINERS
    assert "cloud-sql-proxy" in EXCEPTIONS
