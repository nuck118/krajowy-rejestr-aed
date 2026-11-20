POLAND_LAT_MIN = 49.0
POLAND_LAT_MAX = 55.0
POLAND_LNG_MIN = 14.0
POLAND_LNG_MAX = 24.5

DEFAULT_OVERPASS_BBOX = "53.08,17.92,53.17,18.12"  # Bydgoszcz core for fast live sync

SOURCE_TRUST_TIERS: dict[str, int] = {
    "dane_gov_municipal": 1,
    "direct_submission": 1,
    "uploaded_dataset": 1,
    "pl_geojson": 2,
    "osm_overpass": 3,
}

DEFAULT_TRUST_TIER = 1


def get_source_trust_tier(source_name: str) -> int:
    return SOURCE_TRUST_TIERS.get(source_name, DEFAULT_TRUST_TIER)


OPEN_DATA_HEADERS = {
    "Cache-Control": "public, max-age=300",
    "X-Open-Data-License": "CC0-1.0",
    "X-Open-Data-Standard": "dane.gov.pl-4-star",
    "X-Dataset-Publisher": "Ministry of Digitization (dane.gov.pl)",
}
