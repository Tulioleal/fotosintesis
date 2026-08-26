"""Distributed authentication abuse limiter.

The limiter provides a shared, database-backed abuse boundary for
authentication-sensitive operations. Source-aware and normalized
account-aware rules are evaluated before expensive or state-changing
authentication work, and all persisted or observed identifiers are opaque
keyed digests rather than raw addresses or accounts.
"""

from app.limiter.policy import (
    AdmissionOutcome,
    Dimension,
    EndpointCategory,
    LimitProfile,
    LimiterPolicy,
    StorageFailureMode,
)

__all__ = [
    "AdmissionOutcome",
    "Dimension",
    "EndpointCategory",
    "LimitProfile",
    "LimiterPolicy",
    "StorageFailureMode",
]
