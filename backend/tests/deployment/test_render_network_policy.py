"""Rendered NetworkPolicy validation driven by the reusable validator.

These tests render ``deploy/k8s/render.sh`` against the bundled dev and prod
values files and exercise the network-policy checks in the single reusable
validator (``backend/scripts/validate_rendered_manifests.py``). The CLI and
these tests call the same implementation, so the default-deny baseline, allow
rules, and selector-to-workload coupling are enforced on every render.

Every invalid fixture starts from a compliant rendered manifest, applies
exactly one violation, and asserts that the validator emits the specific
rejection message. These checks prove policy structure and label coupling, not
live enforcement; the connectivity probe in
``deploy/scripts/verify-network-policy.sh`` provides the enforcement proof.
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
POLICIES_MANIFEST = "05-network-policies.yaml"
DEFAULT_DENY_NAME = "fotosintesis-default-deny"

_spec = importlib.util.spec_from_file_location("validate_rendered_manifests", VALIDATOR_PATH)
_validate = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_validate)

validate_directory = _validate.validate_directory
DEFAULT_DENY_NAME_CONST = _validate.DEFAULT_DENY_NAME


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


def _policy_docs(rendered: Path, name: str) -> list[dict]:
    return [
        doc
        for doc in _load_yaml(rendered / POLICIES_MANIFEST)
        if doc.get("metadata", {}).get("name") == name
    ]


def _mutate_and_validate(
    tmp_path: Path,
    values_file: Path,
    mutate_fn,
) -> list[str]:
    rendered = _render(tmp_path, values_file)
    path = rendered / POLICIES_MANIFEST
    docs = _load_yaml(path)
    mutate_fn(docs)
    _write_yaml(path, docs)
    return validate_directory(rendered)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_valid_network_policies_pass(tmp_path: Path, values_file: Path) -> None:
    rendered = _render(tmp_path, values_file)
    assert validate_directory(rendered) == []


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
@pytest.mark.parametrize("values_file", [DEV_VALUES, PROD_VALUES])
def test_missing_default_deny_is_rejected(
    tmp_path: Path, values_file: Path
) -> None:
    def mutate(docs: list[dict]) -> None:
        docs[:] = [
            doc
            for doc in docs
            if doc.get("metadata", {}).get("name") != DEFAULT_DENY_NAME
        ]

    errors = _mutate_and_validate(tmp_path, values_file, mutate)
    joined = "\n".join(errors)
    assert "default-deny NetworkPolicy" in joined
    assert DEFAULT_DENY_NAME in joined


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_default_deny_without_both_policy_types_is_rejected(
    tmp_path: Path,
) -> None:
    def mutate(docs: list[dict]) -> None:
        deny = next(doc for doc in docs if doc["metadata"]["name"] == DEFAULT_DENY_NAME)
        deny["spec"]["policyTypes"] = ["Ingress"]

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, mutate)
    assert any("both Ingress and Egress policyTypes" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_default_deny_with_allow_rules_is_rejected(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        deny = next(doc for doc in docs if doc["metadata"]["name"] == DEFAULT_DENY_NAME)
        deny["spec"]["egress"] = [
            {
                "to": [
                    {
                        "namespaceSelector": {
                            "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                        }
                    }
                ],
                "ports": [{"protocol": "UDP", "port": 53}],
            }
        ]

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, mutate)
    assert any("must not carry allow rules" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_default_deny_must_cover_whole_namespace(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        deny = next(doc for doc in docs if doc["metadata"]["name"] == DEFAULT_DENY_NAME)
        deny["spec"]["podSelector"] = {
            "matchLabels": {"app.kubernetes.io/name": "fotosintesis-frontend"}
        }

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, mutate)
    assert any("must use an empty podSelector" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_unmatched_policy_selector_is_rejected(tmp_path: Path) -> None:
    def mutate(docs: list[dict]) -> None:
        frontend = next(
            doc
            for doc in docs
            if doc["metadata"]["name"] == "fotosintesis-allow-frontend-ingress"
        )
        frontend["spec"]["podSelector"] = {
            "matchLabels": {"app.kubernetes.io/name": "fotosintesis-nope"}
        }

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, mutate)
    assert any("matches no deployed workload pod label" in e for e in errors)


@pytest.mark.skipif(not RENDER_SCRIPT.exists(), reason="render.sh missing")
@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
@pytest.mark.parametrize(
    "removed_name,expected_requirement",
    [
        ("fotosintesis-allow-dns", "DNS egress to kube-dns"),
        ("fotosintesis-allow-external-https-egress", "bounded external HTTPS egress on 443"),
    ],
)
def test_missing_required_allow_rule_is_rejected(
    tmp_path: Path, removed_name: str, expected_requirement: str
) -> None:
    def mutate(docs: list[dict]) -> None:
        docs[:] = [
            doc
            for doc in docs
            if doc.get("metadata", {}).get("name") != removed_name
        ]

    errors = _mutate_and_validate(tmp_path, PROD_VALUES, mutate)
    joined = "\n".join(errors)
    assert "required allow rule missing" in joined
    assert expected_requirement in joined


@pytest.mark.skipif(not VALIDATOR_PATH.exists(), reason="validator missing")
def test_runtime_smoke_selector_is_accepted() -> None:
    workload_labels = {
        "fotosintesis-backend": {
            "app.kubernetes.io/name": "fotosintesis-backend",
            "app.kubernetes.io/part-of": "fotosintesis-ai",
        }
    }
    assert _validate._network_policy_pod_selector_matches(
        {"app.kubernetes.io/name": "fotosintesis-smoke"}, workload_labels
    )
    assert _validate._network_policy_pod_selector_matches(
        {"app.kubernetes.io/name": "fotosintesis-backend"}, workload_labels
    )
    assert not _validate._network_policy_pod_selector_matches(
        {"app.kubernetes.io/name": "fotosintesis-nope"}, workload_labels
    )
    assert DEFAULT_DENY_NAME_CONST == "fotosintesis-default-deny"
