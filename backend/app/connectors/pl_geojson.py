import json
from pathlib import Path

from app.connectors.base import BaseConnector, FetchResult
from app.connectors.osm_mapper import build_osm_raw_record
from app.core.config import settings
from app.services.deduplication import RawRecord


class PLGeoJSONConnector(BaseConnector):
    source_name = "pl_geojson"

    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or (settings.DATA_DIR / "PL.geojson")

    async def fetch(self) -> FetchResult:
        with self.file_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        features = payload.get("features", [])
        records: list[RawRecord] = []
        rejected = 0

        for idx, feature in enumerate(features):
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates")
            if geom.get("type") != "Point" or not isinstance(coords, list) or len(coords) < 2:
                rejected += 1
                continue

            try:
                lng = float(coords[0])
                lat = float(coords[1])
            except (TypeError, ValueError):
                rejected += 1
                continue

            props = feature.get("properties") or {}
            osm_type = props.get("@osm_type") or "node"
            osm_id = props.get("@osm_id") or idx
            external_id = f"osm:{osm_type}:{osm_id}"

            raw_rec = build_osm_raw_record(
                source_name=self.source_name,
                external_id=external_id,
                lat=lat,
                lng=lng,
                props=props,
                raw_payload=feature,
            )
            if raw_rec is None:
                rejected += 1
                continue
            records.append(raw_rec)

        return FetchResult(
            fetched_count=len(features),
            rejected_count=rejected,
            records=records,
        )
