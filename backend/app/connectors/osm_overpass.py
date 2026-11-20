import httpx

from app.connectors.base import BaseConnector, FetchResult
from app.connectors.osm_mapper import build_osm_raw_record
from app.core.config import settings
from app.core.constants import DEFAULT_OVERPASS_BBOX
from app.services.deduplication import RawRecord

OPENAEDMAP_PL_URL = "https://openaedmap.org/api/v1/countries/PL.geojson"


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    parts = [float(p.strip()) for p in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be south,west,north,east")
    return parts[0], parts[1], parts[2], parts[3]


class OSMOverpassConnector(BaseConnector):
    source_name = "osm_overpass"

    def __init__(self, bbox: str | None = None, overpass_url: str | None = None) -> None:
        self.bbox = bbox or DEFAULT_OVERPASS_BBOX
        self.overpass_url = overpass_url or settings.OVERPASS_URL

    async def fetch(self) -> FetchResult:
        query = (
            "[out:json][timeout:8];"
            "("
            f'node["emergency"="defibrillator"]({self.bbox});'
            f'way["emergency"="defibrillator"]({self.bbox});'
            ");"
            "out center tags;"
        )
        headers = {"User-Agent": "KrajowyRejestrAED/1.0 (dane.gov.pl)"}

        # 1. Try direct Overpass interpreter with fast 8s timeout
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                response = await client.post(self.overpass_url, data={"data": query})
                response.raise_for_status()
                payload = response.json()
                elements = payload.get("elements")
                if isinstance(elements, list):
                    return self._parse_overpass_elements(elements)
        except (httpx.HTTPError, ValueError):
            pass

        # 2. Fallback to live OpenAEDMap Poland OSM mirror filtered by requested bbox
        south, west, north, east = _parse_bbox(self.bbox)
        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            resp = await client.get(OPENAEDMAP_PL_URL)
            resp.raise_for_status()
            geojson = resp.json()

        features = geojson.get("features") or []
        records: list[RawRecord] = []
        fetched = 0
        rejected = 0

        for idx, ft in enumerate(features):
            geom = ft.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if geom.get("type") != "Point" or len(coords) < 2:
                continue
            try:
                lng = float(coords[0])
                lat = float(coords[1])
            except (TypeError, ValueError):
                continue

            if not (south <= lat <= north and west <= lng <= east):
                continue

            fetched += 1
            props = ft.get("properties") or {}
            osm_type = props.get("@osm_type") or "node"
            osm_id = props.get("@osm_id") or idx
            external_id = f"osm:{osm_type}:{osm_id}"
            raw_rec = build_osm_raw_record(
                source_name=self.source_name,
                external_id=external_id,
                lat=lat,
                lng=lng,
                props=props,
                raw_payload=ft,
            )
            if raw_rec is None:
                rejected += 1
                continue
            records.append(raw_rec)

        return FetchResult(fetched_count=fetched, rejected_count=rejected, records=records)

    def _parse_overpass_elements(self, elements: list[dict]) -> FetchResult:
        records: list[RawRecord] = []
        rejected = 0

        for elem in elements:
            elem_type = elem.get("type", "node")
            elem_id = elem.get("id")
            if elem_id is None:
                rejected += 1
                continue

            lat = elem.get("lat") or (elem.get("center") or {}).get("lat")
            lng = elem.get("lon") or (elem.get("center") or {}).get("lon")
            if lat is None or lng is None:
                rejected += 1
                continue

            props = elem.get("tags") or {}
            external_id = f"osm:{elem_type}:{elem_id}"
            raw_rec = build_osm_raw_record(
                source_name=self.source_name,
                external_id=external_id,
                lat=float(lat),
                lng=float(lng),
                props=props,
                raw_payload=elem,
            )
            if raw_rec is None:
                rejected += 1
                continue
            records.append(raw_rec)

        return FetchResult(
            fetched_count=len(elements),
            rejected_count=rejected,
            records=records,
        )
