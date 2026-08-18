"""Configurable recovery-link delivery boundary.

A provider returns the user-facing recovery link built from the configured
public origin plus the single raw token. Production delivery providers are
intended to send the link out-of-band; the development ``sink`` provider
never logs or exposes the raw token and simply records that delivery
happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.settings import get_settings


@dataclass
class RecoveryDeliveryResult:
    delivered: bool
    link: str


class RecoveryDeliveryProvider(Protocol):
    def deliver(self, email: str, link: str) -> RecoveryDeliveryResult: ...


class SinkDeliveryProvider:
    """Development sink that never logs the raw token."""

    def deliver(self, email: str, link: str) -> RecoveryDeliveryResult:
        return RecoveryDeliveryResult(delivered=True, link=link)


def build_recovery_link(raw_token: str) -> str:
    settings = get_settings()
    origin = settings.public_origin_url.rstrip("/")
    return f"{origin}/reset-password?token={raw_token}"


def get_delivery_provider() -> RecoveryDeliveryProvider:
    settings = get_settings()
    if settings.recovery_delivery_provider == "sink":
        return SinkDeliveryProvider()
    raise ValueError(
        f"unsupported recovery delivery provider: {settings.recovery_delivery_provider!r}"
    )
