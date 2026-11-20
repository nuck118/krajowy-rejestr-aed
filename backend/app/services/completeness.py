import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.constants import (
    POLAND_LAT_MAX,
    POLAND_LAT_MIN,
    POLAND_LNG_MAX,
    POLAND_LNG_MIN,
)

POSTAL_RE = re.compile(r"^\d{2}-\d{3}$")
TERYT_RE = re.compile(r"^\d{7}$")
VALID_ACCESS_TYPES = {"public", "customers_only", "private"}


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_completeness_score(
    *,
    latitude: float | None,
    longitude: float | None,
    location_description: str | None,
    street_address: str | None,
    city: str | None,
    postal_code: str | None,
    teryt_code: str | None,
    access_type: str | None,
    opening_hours: str | None,
    is_24_7: bool,
    indoor: bool | None,
    status: str | None,
    last_verified_at: datetime | None,
    now: datetime | None = None,
) -> int:
    score = 0
    ref_now = ensure_utc(now) or datetime.now(timezone.utc)

    # 1. Core Geospatial (20 pts)
    if (
        latitude is not None
        and longitude is not None
        and POLAND_LAT_MIN <= latitude <= POLAND_LAT_MAX
        and POLAND_LNG_MIN <= longitude <= POLAND_LNG_MAX
    ):
        score += 20

    # 2. Exact Placement Description (25 pts full, 5 pts minimal)
    desc = (location_description or "").strip()
    if len(desc) >= 10:
        score += 25
    elif len(desc) >= 3:
        score += 5

    # 3. Street Address (10 pts)
    if (street_address or "").strip():
        score += 10

    # 4. City (10 pts)
    if (city or "").strip():
        score += 10

    # 5. Civic Code: postal_code or teryt_code (5 pts)
    has_postal = bool(postal_code and POSTAL_RE.match(postal_code.strip()))
    has_teryt = bool(teryt_code and TERYT_RE.match(teryt_code.strip()))
    if has_postal or has_teryt:
        score += 5

    # 6. Access Type (5 pts)
    if access_type in VALID_ACCESS_TYPES:
        score += 5

    # 7. Availability / Opening Hours (10 pts)
    if is_24_7 or bool((opening_hours or "").strip()):
        score += 10

    # 8. Environment: Indoor / Outdoor (5 pts)
    if indoor is not None:
        score += 5

    # 9. Operational Status (5 pts)
    if status == "operational":
        score += 5

    # 10. Freshness: verified within 365 days (5 pts)
    verified_dt = ensure_utc(last_verified_at)
    if verified_dt is not None and (ref_now - verified_dt) <= timedelta(days=365):
        score += 5

    return score


def compute_completeness_for_obj(obj: Any, now: datetime | None = None) -> int:
    return compute_completeness_score(
        latitude=getattr(obj, "latitude", None),
        longitude=getattr(obj, "longitude", None),
        location_description=getattr(obj, "location_description", None),
        street_address=getattr(obj, "street_address", None),
        city=getattr(obj, "city", None),
        postal_code=getattr(obj, "postal_code", None),
        teryt_code=getattr(obj, "teryt_code", None),
        access_type=getattr(obj, "access_type", None),
        opening_hours=getattr(obj, "opening_hours", None),
        is_24_7=bool(getattr(obj, "is_24_7", False)),
        indoor=getattr(obj, "indoor", None),
        status=getattr(obj, "status", None),
        last_verified_at=getattr(obj, "last_verified_at", None),
        now=now,
    )


def completeness_tier(score: int) -> str:
    if score >= 80:
        return "Standard Compliant"
    if score >= 60:
        return "Minimum Harvestable"
    return "Incomplete"
