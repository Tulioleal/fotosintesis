"""Keyed HMAC derivation for opaque limiter identifiers.

Account and source identifiers are normalized and then transformed with a
versioned keyed digest before any persistence or observation. Raw accounts
and source addresses are never stored, logged, or exposed in metrics.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from app.limiter.policy import Dimension


def _derive(key: bytes, version: str, dimension: str, identifier: str) -> str:
    material = "\x00".join([version, dimension, identifier])
    return hmac.new(key, material.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class KeyedDigest:
    """Configuration-backed keyed digest derivation."""

    secret: str
    key_version: int

    def derive(self, *, dimension: Dimension, identifier: str) -> str:
        """Derive an opaque versioned keyed digest for ``identifier``.

        The key version is included as a non-secret prefix so rotated secrets
        never collide with digests produced under an older version.
        """
        if not self.secret:
            raise ValueError("limiter HMAC secret is not configured")
        if not identifier:
            raise ValueError("cannot derive a limiter key from an empty identifier")
        normalized = identifier.strip().lower()
        key = self.secret.encode("utf-8")
        return _derive(key, str(self.key_version), dimension.value, normalized)


__all__ = ["KeyedDigest"]
