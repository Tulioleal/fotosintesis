from __future__ import annotations

import hashlib
import json
from uuid import UUID

from app.enrichment.identity import CanonicalSpeciesIdentity


def _digest(value: dict[str, object]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def build_active_work_key(
    identity: CanonicalSpeciesIdentity, policy_version: int
) -> str:
    if policy_version < 1:
        raise ValueError("policy_version must be positive")
    digest = _digest({"species": identity.key, "policy_version": policy_version})
    return f"enrichment-active:v1:{digest}"


def build_run_idempotency_key(
    identity: CanonicalSpeciesIdentity,
    policy_version: int,
    run_id: UUID | str,
) -> str:
    if policy_version < 1:
        raise ValueError("policy_version must be positive")
    normalized_run_id = str(run_id).strip()
    if not normalized_run_id:
        raise ValueError("run_id must not be blank")
    digest = _digest(
        {
            "species": identity.key,
            "policy_version": policy_version,
            "run_id": normalized_run_id,
        }
    )
    return f"enrichment-run:v1:{digest}"


__all__ = ["build_active_work_key", "build_run_idempotency_key"]
