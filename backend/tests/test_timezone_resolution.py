import pytest
from pydantic import ValidationError

from app.auth.schemas import TimezoneUpdateRequest
from app.scheduling.timezone import InvalidTimezoneError, resolve_timezone


def test_resolves_canonical_zones() -> None:
    zone = resolve_timezone("America/Argentina/Buenos_Aires")
    assert zone is not None


def test_resolves_legacy_alias_links_via_bundled_tzdata() -> None:
    """Browsers may report legacy IANA link names (e.g. America/Buenos_Aires).

    Slim container images ship incomplete system zoneinfo, so the ``tzdata``
    package must remain a dependency for per-key fallback (PEP 615).
    """

    assert resolve_timezone("America/Buenos_Aires") is not None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_values_resolve_to_none(value: str | None) -> None:
    assert resolve_timezone(value) is None


def test_unknown_zone_raises_invalid_timezone() -> None:
    with pytest.raises(InvalidTimezoneError):
        resolve_timezone("Mars/Olympus_Mons")


def test_timezone_update_request_accepts_legacy_alias() -> None:
    payload = TimezoneUpdateRequest(timezone="America/Buenos_Aires")
    assert payload.timezone == "America/Buenos_Aires"


def test_timezone_update_request_normalizes_blank_to_none() -> None:
    assert TimezoneUpdateRequest(timezone=None).timezone is None
    assert TimezoneUpdateRequest(timezone="  ").timezone is None


def test_timezone_update_request_rejects_unknown_zone() -> None:
    with pytest.raises(ValidationError):
        TimezoneUpdateRequest(timezone="Not/AZone")
