#!/usr/bin/env python3
"""Reusable rendered-manifest policy validator for the hardened workload runtime.

This single implementation is shared by the CLI and the rendered-manifest tests
(``tests/deployment/test_render_hardening.py``) so both call the same checks.

It discovers every ``*.yaml`` / ``*.yml`` file under a directory, handles the
pod spec of Pod, Deployment, StatefulSet, DaemonSet, Job, and CronJob objects,
enumerates regular containers, init containers, and restartable native
sidecars, and rejects any container that:

- has no CPU and memory requests and limits (resources are never excepted),
- is an application container that does not enforce non-root execution,
  disabled privilege escalation, dropped Linux capabilities, ``RuntimeDefault``
  seccomp, and a read-only root,
- is a backend-image or frontend-image container whose numeric UID/GID does not
  match the documented identity (backend ``10001:10001``, frontend ``1001:1001``),
- mounts a broad writable ``/app`` path, or
- is neither a known application container nor a listed, exact exception.

Exceptions are exact per container name (never wildcards), must document the
omitted fields and a concrete reason, and are validated for malformed,
wildcard, duplicate, and unused entries. Resource omissions are never allowed.

Usage:
    python validate_rendered_manifests.py <directory>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

# Application containers that must satisfy the full security baseline.
APP_CONTAINERS = {
    "backend",
    "frontend",
    "worker",
    "migrations",
    "limiter-cleanup",
}

# Backend-image containers that must pin the fixed numeric runtime identity.
BACKEND_IMAGE_CONTAINERS = {"backend", "worker", "migrations", "limiter-cleanup"}
BACKEND_UID = 10001
BACKEND_GID = 10001

# The frontend image pins its own fixed numeric runtime identity.
FRONTEND_IMAGE_CONTAINERS = {"frontend"}
FRONTEND_UID = 1001
FRONTEND_GID = 1001

# Fields that an exception may never omit. Resources and core security
# invariants are never waivable.
_NEVER_OMITABLE = {
    "resources",
    "runAsNonRoot",
    "allowPrivilegeEscalation",
    "capabilities",
    "readOnlyRootFilesystem",
    "seccompProfile",
}

# Exact, structured exceptions keyed by container name. No wildcards. Each entry
# lists the only fields that may be omitted and a concrete workload reason.
EXCEPTIONS: dict[str, dict] = {
    "cloud-sql-proxy": {
        "reason": (
            "runs as the vendor distroless non-root user (not the backend numeric "
            "identity); runAsNonRoot is the compensating control and no numeric "
            "UID/GID is pinned"
        ),
        "omit_fields": {"runAsUser", "runAsGroup"},
    },
}

# Pod-bearing Kubernetes kinds and the path to their pod template spec.
_POD_KINDS = {
    "Pod": ("spec",),
    "Deployment": ("spec", "template", "spec"),
    "StatefulSet": ("spec", "template", "spec"),
    "DaemonSet": ("spec", "template", "spec"),
    "Job": ("spec", "template", "spec"),
    "CronJob": ("spec", "jobTemplate", "spec", "template", "spec"),
}


def _pod_spec(doc: dict) -> dict | None:
    path = _POD_KINDS.get(doc.get("kind"))
    if path is None:
        return None
    node = doc
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node if isinstance(node, dict) else None


def _enumerate_containers(pod_spec: dict) -> list[dict]:
    """Return regular, init, and restartable native-sidecar containers."""
    containers = list(pod_spec.get("containers", []) or [])
    for c in pod_spec.get("initContainers", []) or []:
        containers.append(c)
    return containers


def _container_names(pod_spec: dict) -> list[str]:
    return [c.get("name", "") for c in _enumerate_containers(pod_spec)]


def _resource_missing(res: dict) -> list[str]:
    missing = []
    for scope in ("requests", "limits"):
        for key in ("cpu", "memory"):
            if not (res.get(scope, {}).get(key) or ""):
                missing.append(f"{scope}.{key}")
    return missing


def _drop_all(sec: dict) -> bool:
    return sec.get("capabilities", {}).get("drop") == ["ALL"]


def validate_exceptions(rendered_container_names: set[str]) -> list[str]:
    """Validate the exception config against the containers actually rendered.

    Rejects wildcard, malformed, duplicate, never-omitable, and unused
    exception entries.
    """
    errors: list[str] = []
    seen: set[str] = set()
    for name, entry in EXCEPTIONS.items():
        if name in seen:
            errors.append(f"exception {name!r} is declared more than once")
        seen.add(name)
        if "*" in name or "?" in name or "[" in name or name.lower() in {"all", "any"}:
            errors.append(f"exception container {name!r} is a wildcard; exceptions must be exact")
        if not isinstance(entry, dict):
            errors.append(f"exception {name!r} is malformed: expected a mapping")
            continue
        reason = entry.get("reason")
        omit = entry.get("omit_fields")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"exception {name!r} is missing a concrete reason")
        if not isinstance(omit, (set, list, tuple)) or not omit:
            errors.append(f"exception {name!r} must list the fields it omits")
        else:
            for field in omit:
                if field in _NEVER_OMITABLE:
                    errors.append(
                        f"exception {name!r} may not omit {field!r}: it is never waivable"
                    )
        if name not in rendered_container_names:
            errors.append(
                f"exception {name!r} is unused: no rendered manifest has that container"
            )
    return errors


# NetworkPolicy constants for the network-segmentation baseline.
DEFAULT_DENY_NAME = "fotosintesis-default-deny"
WORKLOAD_LABEL = "app.kubernetes.io/name"
# Runtime probe Pods (deploy smoke and network-policy verification) are created
# with kubectl and are not present in the rendered manifests, but policies may
# legitimately select them. Every other in-namespace selector must match a
# deployed workload's pod template labels.
KNOWN_RUNTIME_SELECTORS = {
    frozenset({("app.kubernetes.io/name", "fotosintesis-smoke")}),
}


def _network_policy_pod_selector_matches(labels: dict, workload_labels: dict) -> bool:
    """Whether ``labels`` select at least one deployed workload pod template.

    A selector matches when every ``matchLabels`` key/value pair is present on
    at least one Deployment/Job/CronJob pod template. Empty selectors and the
    documented runtime probe labels are always accepted.
    """
    if not labels:
        return True
    if frozenset(labels.items()) in KNOWN_RUNTIME_SELECTORS:
        return True
    return any(
        all(template.get(key) == value for key, value in labels.items())
        for template in workload_labels.values()
    )


def validate_network_policies(directory: Path) -> list[str]:
    """Validate rendered NetworkPolicies; return error strings.

    Confirms that the namespace default-deny baseline is present, that every
    in-namespace pod selector used by a policy matches a deployed workload's
    pod template labels (or a documented runtime probe label), and that each
    required allow rule is present. This validates policy structure and label
    coupling; it does not prove live enforcement, which the connectivity probe
    in ``deploy/scripts/verify-network-policy.sh`` covers.
    """
    errors: list[str] = []
    policies: list[tuple[Path, dict]] = []
    workload_labels: dict[str, dict] = {}

    for path in sorted(
        p for p in directory.rglob("*") if p.suffix in {".yaml", ".yml"} and p.is_file()
    ):
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except yaml.YAMLError as exc:
            errors.append(f"{path}: malformed YAML: {exc}")
            continue
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            kind = doc.get("kind")
            if kind == "NetworkPolicy":
                policies.append((path, doc))
                continue
            if kind in {"Deployment", "StatefulSet", "DaemonSet"}:
                template = doc.get("spec", {}).get("template", {})
            elif kind == "Job":
                template = doc.get("spec", {}).get("template", {})
            elif kind == "CronJob":
                template = (
                    doc.get("spec", {})
                    .get("jobTemplate", {})
                    .get("spec", {})
                    .get("template", {})
                )
            else:
                continue
            labels = template.get("metadata", {}).get("labels", {})
            if isinstance(labels, dict) and labels:
                workload_labels[doc.get("metadata", {}).get("name", "")] = labels

    if not policies:
        return [f"no NetworkPolicy resources found under {directory}"]

    deny = next(
        (
            policy
            for _, policy in policies
            if policy.get("metadata", {}).get("name") == DEFAULT_DENY_NAME
        ),
        None,
    )
    if deny is None:
        errors.append(
            f"default-deny NetworkPolicy {DEFAULT_DENY_NAME!r} is missing"
        )
    else:
        spec = deny.get("spec", {})
        policy_types = spec.get("policyTypes", []) or []
        if "Ingress" not in policy_types or "Egress" not in policy_types:
            errors.append(
                "default-deny must declare both Ingress and Egress policyTypes"
            )
        if spec.get("podSelector") != {}:
            errors.append("default-deny must use an empty podSelector covering the namespace")
        if spec.get("ingress") or spec.get("egress"):
            errors.append("default-deny must not carry allow rules")

    # Selector coupling: in-namespace pod selectors must match deployed labels.
    for path, policy in policies:
        spec = policy.get("spec", {})
        name = policy.get("metadata", {}).get("name", "")
        label = f"{path}: NetworkPolicy {name!r}"

        def check_selector(source: str, labels: dict) -> None:
            if not _network_policy_pod_selector_matches(labels, workload_labels):
                errors.append(
                    f"{label} {source} selector {labels} matches no deployed "
                    "workload pod label and is not a known runtime probe selector"
                )

        check_selector("pod", (spec.get("podSelector") or {}).get("matchLabels") or {})
        for rule in spec.get("ingress") or []:
            for src in rule.get("from") or []:
                if src.get("podSelector") and not src.get("namespaceSelector"):
                    check_selector(
                        "ingress from",
                        (src["podSelector"].get("matchLabels") or {}),
                    )
        for rule in spec.get("egress") or []:
            for dst in rule.get("to") or []:
                if dst.get("podSelector") and not dst.get("namespaceSelector"):
                    check_selector(
                        "egress to", (dst["podSelector"].get("matchLabels") or {})
                    )

    # Required allow rules. Each flag flips only when a structural rule is
    # found anywhere in the rendered policy set.
    flags = {
        "DNS egress to kube-dns": False,
        "metadata server egress for Workload Identity": False,
        "frontend ingress from GFE health-check ranges": False,
        "backend ingress from the frontend": False,
        "backend ingress from Managed Prometheus (gmp-system)": False,
        "worker ingress from Managed Prometheus (gmp-system)": False,
        "frontend egress to the backend": False,
        "smoke probe egress to the backend": False,
        "Cloud SQL proxy egress on 3307": False,
        "bounded external HTTPS egress on 443": False,
    }
    for _, policy in policies:
        spec = policy.get("spec", {})
        pod_sel = (spec.get("podSelector") or {}).get("matchLabels") or {}
        pod_name = pod_sel.get(WORKLOAD_LABEL)

        for rule in spec.get("egress") or []:
            port_numbers = {
                port.get("port")
                for port in rule.get("ports") or []
                if isinstance(port, dict) and port.get("port") is not None
            }
            for dst in rule.get("to") or []:
                ns = (dst.get("namespaceSelector") or {}).get("matchLabels") or {}
                ps = (dst.get("podSelector") or {}).get("matchLabels") or {}
                if (
                    ns.get("kubernetes.io/metadata.name") == "kube-system"
                    and 53 in port_numbers
                ):
                    flags["DNS egress to kube-dns"] = True
                cidr = (dst.get("ipBlock") or {}).get("cidr")
                if cidr in ("169.254.169.254/32", "169.254.169.252/32"):
                    flags["metadata server egress for Workload Identity"] = True
                if cidr == "0.0.0.0/0":
                    if 443 in port_numbers:
                        flags["bounded external HTTPS egress on 443"] = True
                    if 3307 in port_numbers:
                        flags["Cloud SQL proxy egress on 3307"] = True
                if (
                    pod_name == "fotosintesis-frontend"
                    and ps.get(WORKLOAD_LABEL) == "fotosintesis-backend"
                ):
                    flags["frontend egress to the backend"] = True
                if (
                    frozenset(pod_sel.items()) in KNOWN_RUNTIME_SELECTORS
                    and ps.get(WORKLOAD_LABEL) == "fotosintesis-backend"
                ):
                    flags["smoke probe egress to the backend"] = True

        for rule in spec.get("ingress") or []:
            port_numbers = {
                port.get("port")
                for port in rule.get("ports") or []
                if isinstance(port, dict) and port.get("port") is not None
            }
            if pod_name == "fotosintesis-frontend":
                cidrs = {
                    (src.get("ipBlock") or {}).get("cidr")
                    for src in rule.get("from") or []
                }
                if cidrs & {"35.191.0.0/16", "130.211.0.0/22", "209.85.152.0/22", "209.85.204.0/22"}:
                    flags["frontend ingress from GFE health-check ranges"] = True
            if pod_name == "fotosintesis-backend":
                for src in rule.get("from") or []:
                    ns = (src.get("namespaceSelector") or {}).get("matchLabels") or {}
                    ps = (src.get("podSelector") or {}).get("matchLabels") or {}
                    if ps.get(WORKLOAD_LABEL) == "fotosintesis-frontend":
                        flags["backend ingress from the frontend"] = True
                    if ns.get("kubernetes.io/metadata.name") == "gmp-system":
                        flags["backend ingress from Managed Prometheus (gmp-system)"] = True
            if pod_name == "fotosintesis-worker":
                for src in rule.get("from") or []:
                    ns = (src.get("namespaceSelector") or {}).get("matchLabels") or {}
                    if ns.get("kubernetes.io/metadata.name") == "gmp-system":
                        flags["worker ingress from Managed Prometheus (gmp-system)"] = True

    for requirement, found in flags.items():
        if not found:
            errors.append(f"required allow rule missing: {requirement}")

    return errors


def validate_directory(directory: Path) -> list[str]:
    """Validate all rendered manifests under ``directory``; return error strings."""
    if not directory.is_dir():
        return [f"not a directory: {directory}"]

    errors: list[str] = []
    rendered_names: set[str] = set()
    files = sorted(
        p for p in directory.rglob("*") if p.suffix in {".yaml", ".yml"} and p.is_file()
    )
    if not files:
        return [f"no YAML manifests found under {directory}"]

    manifests: list[tuple[Path, dict]] = []
    for path in files:
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except yaml.YAMLError as exc:
            errors.append(f"{path}: malformed YAML: {exc}")
            continue
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            spec = _pod_spec(doc)
            if spec is None:
                continue
            manifests.append((path, doc))
            rendered_names.update(_container_names(spec))

    errors.extend(validate_exceptions(rendered_names))

    for path, doc in manifests:
        kind = doc.get("kind", "")
        workload = doc.get("metadata", {}).get("name", "")
        spec = _pod_spec(doc)
        if spec is None:
            continue

        seccomp = spec.get("securityContext", {}).get("seccompProfile", {}).get("type")
        if seccomp != "RuntimeDefault":
            errors.append(
                f"{path}: {kind}/{workload} pod seccomp must be RuntimeDefault"
            )

        volumes = {v.get("name"): v for v in spec.get("volumes", []) or []}
        for container in _enumerate_containers(spec):
            name = container.get("name", "")
            label = f"{path}: {kind}/{workload} container {name!r}"

            if name not in APP_CONTAINERS and name not in EXCEPTIONS:
                errors.append(f"{label} is an unknown container")
                continue

            resources = container.get("resources", {}) or {}
            missing = _resource_missing(resources)
            if missing:
                errors.append(
                    f"{label} missing resource declarations: {sorted(missing)}"
                )

            sec = container.get("securityContext", {}) or {}
            is_app = name in APP_CONTAINERS
            is_exception = name in EXCEPTIONS

            if is_app:
                if sec.get("runAsNonRoot") is not True:
                    errors.append(f"{label} must run as non-root")
                if sec.get("allowPrivilegeEscalation") is not False:
                    errors.append(f"{label} must disable privilege escalation")
                if not _drop_all(sec):
                    errors.append(f"{label} must drop ALL capabilities")
                if sec.get("readOnlyRootFilesystem") is not True:
                    errors.append(f"{label} must use a read-only root")

                if name in BACKEND_IMAGE_CONTAINERS:
                    if sec.get("runAsUser") != BACKEND_UID:
                        errors.append(
                            f"{label} must pin runAsUser {BACKEND_UID}"
                        )
                    if sec.get("runAsGroup") != BACKEND_GID:
                        errors.append(
                            f"{label} must pin runAsGroup {BACKEND_GID}"
                        )
                if name in FRONTEND_IMAGE_CONTAINERS:
                    if sec.get("runAsUser") != FRONTEND_UID:
                        errors.append(
                            f"{label} must pin runAsUser {FRONTEND_UID}"
                        )
                    if sec.get("runAsGroup") != FRONTEND_GID:
                        errors.append(
                            f"{label} must pin runAsGroup {FRONTEND_GID}"
                        )

                # Writable-mount rules apply only to application containers.
                for mount in container.get("volumeMounts", []) or []:
                    mount_path = mount.get("mountPath", "")
                    vol = volumes.get(mount.get("name"))
                    if mount_path in ("/app",) or mount_path.startswith("/app/"):
                        errors.append(f"{label} mounts a broad writable /app path")
                    if mount_path == "/tmp":
                        if vol is None:
                            errors.append(
                                f"{label} /tmp mount has no backing volume"
                            )
                        elif vol.get("emptyDir") is None:
                            errors.append(
                                f"{label} /tmp mount must use an explicit emptyDir volume"
                            )

            if is_exception:
                omit = set(EXCEPTIONS[name].get("omit_fields", set()))
                if sec.get("runAsNonRoot") is not True:
                    errors.append(f"{label} must run as non-root")
                if sec.get("allowPrivilegeEscalation") is not False:
                    errors.append(f"{label} must disable privilege escalation")
                if not _drop_all(sec):
                    errors.append(f"{label} must drop ALL capabilities")
                if sec.get("readOnlyRootFilesystem") is not True:
                    errors.append(f"{label} must use a read-only root")
                if "runAsUser" not in omit and "runAsUser" in sec:
                    errors.append(f"{label} must not pin a numeric runAsUser")
                if "runAsGroup" not in omit and "runAsGroup" in sec:
                    errors.append(f"{label} must not pin a numeric runAsGroup")

    errors.extend(validate_network_policies(directory))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="directory containing rendered manifests")
    args = parser.parse_args(argv)
    errors = validate_directory(Path(args.directory))
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"validation failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("validation passed: all rendered manifests satisfy the baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
