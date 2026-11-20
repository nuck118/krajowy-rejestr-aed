import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.metadata import format_poland_level

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
POSTCODE_RE = re.compile(r"\b(\d{2}-\d{3})\b")
HIT_TTL_SECONDS = 86400.0
MISS_TTL_SECONDS = 300.0
MIN_INTERVAL_SECONDS = 1.05

PLACE_KEYS = (
    "office",
    "amenity",
    "public_building",
    "healthcare",
    "hospital",
    "clinic",
    "pharmacy",
    "university",
    "school",
    "railway",
    "station",
    "shop",
    "tourism",
    "leisure",
    "building",
    "historic",
)

IGNORED_PLACE_VALUES = {
    "yes",
    "no",
    "defibrillator",
    "apartments",
    "residential",
    "commercial",
    "retail",
    "industrial",
    "house",
    "detached",
}

STREET_PREFIXES = (
    "ul.",
    "al.",
    "pl.",
    "plac ",
    "os.",
    "osiedle ",
    "rynek",
    "skwer",
    "rondo",
    "wybrzeże",
    "bulwar",
    "droga",
    "trasa",
)


@dataclass(slots=True)
class ReverseGeoResult:
    place_name: str | None
    street_address: str | None
    city: str | None
    postal_code: str | None


_CACHE: dict[tuple[float, float], tuple[float, ReverseGeoResult | None]] = {}
_RATE_LOCK = asyncio.Lock()
_LAST_REQUEST_TS = 0.0


def _clean(val: Any) -> str | None:
    if val is None:
        return None
    cleaned = " ".join(str(val).split())
    return cleaned if cleaned else None


def _is_valid_place(candidate: str | None, road: str | None) -> bool:
    if not candidate:
        return False
    low = candidate.lower()
    if low in IGNORED_VALUES_LOWER:
        return False
    if road and low == road.lower():
        return False
    return True


IGNORED_VALUES_LOWER = {v.lower() for v in IGNORED_PLACE_VALUES}


async def reverse_geocode_poland(lat: float, lng: float) -> ReverseGeoResult | None:
    global _LAST_REQUEST_TS

    key = (round(lat, 5), round(lng, 5))
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached is not None:
        cached_at, cached_res = cached
        ttl = HIT_TTL_SECONDS if cached_res is not None else MISS_TTL_SECONDS
        if (now - cached_at) < ttl:
            return cached_res

    async with _RATE_LOCK:
        now = time.monotonic()
        cached = _CACHE.get(key)
        if cached is not None:
            cached_at, cached_res = cached
            ttl = HIT_TTL_SECONDS if cached_res is not None else MISS_TTL_SECONDS
            if (now - cached_at) < ttl:
                return cached_res

        wait_for = MIN_INTERVAL_SECONDS - (now - _LAST_REQUEST_TS)
        if wait_for > 0:
            await asyncio.sleep(wait_for)

        params = {
            "format": "jsonv2",
            "lat": f"{lat:.6f}",
            "lon": f"{lng:.6f}",
            "zoom": "18",
            "addressdetails": "1",
            "accept-language": "pl",
        }
        headers = {"User-Agent": "KrajowyRejestrAED/1.0 (dane.gov.pl)"}

        _LAST_REQUEST_TS = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=3.0, headers=headers) as client:
                resp = await client.get(NOMINATIM_REVERSE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError, TimeoutError):
            _CACHE[key] = (time.monotonic(), None)
            return None

    if not isinstance(data, dict) or data.get("error"):
        _CACHE[key] = (time.monotonic(), None)
        return None

    address = data.get("address")
    if not isinstance(address, dict):
        address = {}

    road = _clean(
        address.get("road")
        or address.get("pedestrian")
        or address.get("square")
        or address.get("footway")
        or address.get("neighbourhood")
    )
    house_number = _clean(address.get("house_number"))
    if road and house_number:
        street_address = f"{road} {house_number}"
    else:
        street_address = road

    place_name: str | None = None
    top_name = _clean(data.get("name"))
    if _is_valid_place(top_name, road):
        place_name = top_name
    else:
        for pk in PLACE_KEYS:
            cand = _clean(address.get(pk))
            if _is_valid_place(cand, road):
                place_name = cand
                break

    city = _clean(
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
    )

    raw_postcode = _clean(address.get("postcode")) or ""
    m_post = POSTCODE_RE.search(raw_postcode)
    postal_code = m_post.group(1) if m_post else None

    result = ReverseGeoResult(
        place_name=place_name,
        street_address=street_address,
        city=city,
        postal_code=postal_code,
    )
    _CACHE[key] = (time.monotonic(), result)
    return result


def compose_factual_placement(
    geo: ReverseGeoResult,
    *,
    indoor: bool | None,
    level: str | None,
    operator: str | None,
) -> str | None:
    base: str | None = None
    op_clean = _clean(operator)

    if geo.place_name:
        base = geo.place_name
    elif op_clean:
        base = op_clean
    elif geo.street_address:
        street = geo.street_address
        low = street.lower()
        has_prefix = any(low.startswith(p) for p in STREET_PREFIXES)
        if not has_prefix:
            street_part = f"Budynek przy ul. {street}" if indoor is True else f"ul. {street}"
        else:
            street_part = street
        base = f"{street_part}, {geo.city}" if geo.city else street_part
    elif geo.city:
        base = geo.city

    if not base:
        return None

    env_tag = (
        "wewnątrz budynku"
        if indoor is True
        else "na zewnątrz"
        if indoor is False
        else None
    )
    ctx_parts = [p for p in (env_tag, format_poland_level(level)) if p]
    composed = f"{base} ({', '.join(ctx_parts)})" if ctx_parts else base
    return composed[:500] if len(composed) >= 3 else None
