import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from app.db.models import AEDSourceRecord
from app.services.completeness import ensure_utc

OSM_EXTERNAL_ID_RE = re.compile(r"^osm:(node|way|relation):(\d+)$")


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    cleaned = " ".join(str(val).split())
    return cleaned if cleaned else None


def _clean_http_url(val: Any) -> str | None:
    cleaned = _clean_str(val)
    if cleaned and (cleaned.startswith("http://") or cleaned.startswith("https://")):
        return cleaned
    return None


def _unwrap_props(raw_payload: Any) -> dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return {}
    props = raw_payload.get("properties")
    if isinstance(props, dict):
        return props
    return raw_payload


def format_poland_level(level: str | None) -> str | None:
    cleaned = _clean_str(level)
    if not cleaned:
        return None
    if cleaned == "0":
        return "parter"
    if cleaned == "-1":
        return "poziom -1"
    if cleaned == "1":
        return "1. piętro"
    return f"poziom {cleaned}"


def extract_source_metadata(source_records: list[AEDSourceRecord]) -> dict[str, Any]:
    result: dict[str, str | None] = {
        "location_pl": None,
        "location_en": None,
        "operator": None,
        "level": None,
        "phone": None,
        "website": None,
        "email": None,
        "wheelchair": None,
        "manufacturer": None,
        "model": None,
        "image_url": None,
        "note": None,
        "fixme": None,
        "source_ref": None,
        "osm_url": None,
    }
    if not source_records:
        return result

    ordered = sorted(
        source_records,
        key=lambda sr: (
            sr.source_trust_tier,
            -(ensure_utc(sr.ingested_at) or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
        ),
    )

    def _pick(field: str, *candidates: Any) -> None:
        if result[field] is not None:
            return
        for cand in candidates:
            cleaned = _clean_str(cand)
            if cleaned is not None:
                result[field] = cleaned
                return

    for sr in ordered:
        props = _unwrap_props(sr.raw_payload)
        if not props and not sr.external_id:
            continue

        _pick(
            "location_pl",
            props.get("defibrillator:location:pl"),
            props.get("defibrillator:location"),
            props.get("defibrillator:location:pdt"),
        )
        _pick(
            "location_en",
            props.get("defibrillator:location:en"),
            props.get("description:en"),
        )
        _pick("operator", props.get("operator"), props.get("operator:short"))
        _pick("level", props.get("level"), props.get("addr:floor"), props.get("floor"))
        _pick("phone", props.get("phone"), props.get("emergency:phone"))
        if result["website"] is None:
            result["website"] = _clean_http_url(props.get("website"))
        _pick("email", props.get("email"))
        _pick("wheelchair", props.get("wheelchair"))
        _pick("manufacturer", props.get("manufacturer"), props.get("brand"))
        _pick("model", props.get("model"))

        if result["image_url"] is None:
            direct_img = _clean_http_url(props.get("image"))
            if direct_img is not None:
                result["image_url"] = direct_img
            else:
                wc = _clean_str(props.get("wikimedia_commons"))
                if wc and wc.lower().startswith("file:"):
                    filename = wc[5:].strip()
                    if filename:
                        result["image_url"] = (
                            f"https://commons.wikimedia.org/wiki/Special:FilePath/"
                            f"{urllib.parse.quote(filename)}"
                        )

        _pick(
            "note",
            props.get("note:pl"),
            props.get("note"),
            props.get("description:pl"),
            props.get("description"),
        )
        _pick("fixme", props.get("fixme"))
        _pick("source_ref", props.get("ref"), props.get("source"))

        if result["osm_url"] is None:
            osm_type = _clean_str(props.get("@osm_type"))
            osm_id = _clean_str(props.get("@osm_id"))
            if osm_type in ("node", "way", "relation") and osm_id and osm_id.isdigit():
                result["osm_url"] = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
            elif sr.external_id:
                m = OSM_EXTERNAL_ID_RE.match(sr.external_id.strip())
                if m:
                    result["osm_url"] = f"https://www.openstreetmap.org/{m.group(1)}/{m.group(2)}"

    return result
