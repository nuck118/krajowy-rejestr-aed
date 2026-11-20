import re
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from app.schemas.aed import AEDIngestCandidate
from app.services.deduplication import RawRecord

POSTCODE_RE = re.compile(r"^\d{2}-\d{3}$")


def map_osm_access(raw_access: str | None) -> str:
    if not raw_access:
        return "public"
    val = raw_access.strip().lower()
    if val in ("yes", "public", "permissive", "unknown"):
        return "public"
    if val in ("customers", "customer", "customers_only"):
        return "customers_only"
    if val in ("private", "permit", "no", "restricted"):
        return "private"
    return "public"


def map_osm_indoor(props: dict[str, Any]) -> bool | None:
    indoor_val = str(props.get("indoor", "")).strip().lower()
    if indoor_val in ("yes", "true", "1"):
        return True
    if indoor_val in ("no", "false", "0"):
        return False

    loc_val = str(props.get("location", "")).strip().lower()
    if loc_val in ("indoor", "inside"):
        return True
    if loc_val in ("outdoor", "outside"):
        return False
    return None


def parse_osm_check_date(raw_date: str | None) -> datetime | None:
    if not raw_date:
        return None
    text = raw_date.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(text[:10], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def build_osm_raw_record(
    *,
    source_name: str,
    external_id: str,
    lat: float,
    lng: float,
    props: dict[str, Any],
    raw_payload: dict[str, Any],
) -> RawRecord | None:
    desc = (
        props.get("defibrillator:location:pl")
        or props.get("defibrillator:location")
        or props.get("defibrillator:location:pdt")
        or props.get("defibrillator:location:en")
        or props.get("defibrillator:location:de")
        or props.get("defibrillator:location:fr")
        or props.get("description:pl")
        or props.get("description")
        or props.get("description:en")
        or props.get("note:pl")
        or props.get("note")
        or props.get("operator")
        or props.get("name")
    )
    if isinstance(desc, str):
        desc = " ".join(desc.split())

    street = props.get("addr:street") or props.get("object:street") or props.get("addr:place")
    housenumber = props.get("addr:housenumber")
    street_address: str | None = None
    if street and housenumber:
        street_address = f"{street} {housenumber}".strip()
    elif street:
        street_address = str(street).strip()
    elif props.get("object:addr"):
        street_address = str(props.get("object:addr")).strip()

    city = props.get("addr:city") or props.get("object:city")
    raw_postcode = str(props.get("addr:postcode") or "").strip()
    postal_code = raw_postcode if POSTCODE_RE.match(raw_postcode) else None

    opening_hours = props.get("opening_hours")
    is_24_7 = bool(isinstance(opening_hours, str) and opening_hours.strip().lower() == "24/7")

    check_dt = parse_osm_check_date(props.get("check_date"))
    status = "unverified"
    if check_dt is not None and (datetime.now(timezone.utc) - check_dt) <= timedelta(days=365):
        status = "operational"

    try:
        candidate = AEDIngestCandidate(
            latitude=lat,
            longitude=lng,
            street_address=street_address,
            city=city,
            postal_code=postal_code,
            teryt_code=None,
            location_description=desc,
            access_type=map_osm_access(props.get("access")),
            opening_hours=opening_hours,
            is_24_7=is_24_7,
            indoor=map_osm_indoor(props),
            status=status,
            last_verified_at=check_dt,
        )
    except ValidationError:
        return None

    return RawRecord(
        source_name=source_name,
        external_id=external_id,
        candidate=candidate,
        raw_payload=raw_payload,
    )
