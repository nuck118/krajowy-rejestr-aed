from typing import Any

from pydantic import ValidationError

from app.connectors.base import BaseConnector, FetchResult
from app.connectors.osm_mapper import build_osm_raw_record, map_osm_access, parse_osm_check_date
from app.schemas.aed import AEDIngestCandidate
from app.services.deduplication import RawRecord


class JSONPayloadConnector(BaseConnector):
    def __init__(self, source_name: str, payload: dict[str, Any] | list[Any]) -> None:
        self.source_name = source_name
        self.payload = payload

    async def fetch(self) -> FetchResult:
        if isinstance(self.payload, dict) and self.payload.get("type") == "FeatureCollection":
            return self._parse_geojson(self.payload.get("features") or [])

        if isinstance(self.payload, dict):
            items = self.payload.get("records") or self.payload.get("items") or self.payload.get("features") or []
        elif isinstance(self.payload, list):
            items = self.payload
        else:
            items = []

        if not isinstance(items, list):
            return FetchResult(fetched_count=0, rejected_count=0, records=[])

        return self._parse_records(items)

    def _parse_geojson(self, features: list[Any]) -> FetchResult:
        records: list[RawRecord] = []
        rejected = 0

        for idx, feature in enumerate(features):
            if not isinstance(feature, dict):
                rejected += 1
                continue
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
            external_id = str(
                props.get("external_id")
                or props.get("id")
                or feature.get("id")
                or (f"osm:{props.get('@osm_type', 'node')}:{props['@osm_id']}" if "@osm_id" in props else f"{self.source_name}:{idx}")
            )

            # Support both canonical properties and OSM properties
            if "location_description" in props or "street_address" in props or "teryt_code" in props:
                try:
                    candidate = AEDIngestCandidate(
                        latitude=lat,
                        longitude=lng,
                        street_address=props.get("street_address") or props.get("addr:street"),
                        city=props.get("city") or props.get("addr:city"),
                        postal_code=props.get("postal_code") or props.get("addr:postcode"),
                        teryt_code=props.get("teryt_code"),
                        location_description=props.get("location_description") or props.get("defibrillator:location"),
                        access_type=map_osm_access(props.get("access_type") or props.get("access")),
                        opening_hours=props.get("opening_hours"),
                        is_24_7=bool(props.get("is_24_7", False)),
                        indoor=props.get("indoor") if isinstance(props.get("indoor"), bool) else None,
                        status=props.get("status", "operational"),
                        last_verified_at=props.get("last_verified_at") or parse_osm_check_date(props.get("check_date")),
                    )
                    records.append(
                        RawRecord(
                            source_name=self.source_name,
                            external_id=external_id,
                            candidate=candidate,
                            raw_payload=feature,
                        )
                    )
                    continue
                except (TypeError, ValueError, ValidationError):
                    rejected += 1
                    continue

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

        return FetchResult(fetched_count=len(features), rejected_count=rejected, records=records)

    def _parse_records(self, items: list[Any]) -> FetchResult:
        records: list[RawRecord] = []
        rejected = 0

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                rejected += 1
                continue
            external_id = str(item.get("external_id") or item.get("id") or f"{self.source_name}:{idx}")
            try:
                lat = float(item["latitude"] if "latitude" in item else item["lat"])
                lng = float(item["longitude"] if "longitude" in item else item.get("lng", item.get("lon")))
                candidate = AEDIngestCandidate(
                    latitude=lat,
                    longitude=lng,
                    street_address=item.get("street_address"),
                    city=item.get("city"),
                    postal_code=item.get("postal_code"),
                    teryt_code=item.get("teryt_code"),
                    location_description=item.get("location_description"),
                    access_type=map_osm_access(item.get("access_type") or item.get("access")),
                    opening_hours=item.get("opening_hours"),
                    is_24_7=bool(item.get("is_24_7", False)),
                    indoor=item.get("indoor") if isinstance(item.get("indoor"), bool) else None,
                    status=item.get("status", "operational"),
                    last_verified_at=item.get("last_verified_at"),
                )
            except (KeyError, TypeError, ValueError, ValidationError):
                rejected += 1
                continue

            records.append(
                RawRecord(
                    source_name=self.source_name,
                    external_id=external_id,
                    candidate=candidate,
                    raw_payload=item,
                )
            )

        return FetchResult(fetched_count=len(items), rejected_count=rejected, records=records)
