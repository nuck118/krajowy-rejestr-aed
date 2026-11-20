import csv
import io
import json

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_and_empty_stats(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    stats_resp = await client.get("/api/v1/stats")
    assert stats_resp.status_code == 200
    assert stats_resp.json()["total_unified_aeds"] == 0


@pytest.mark.asyncio
async def test_submit_merge_nearest_verify_and_exports(client: AsyncClient) -> None:
    payload_1 = {
        "latitude": 53.1235,
        "longitude": 18.0084,
        "street_address": "ul. Jagiellońska 10",
        "city": "Bydgoszcz",
        "postal_code": "85-067",
        "location_description": "Hol wejściowy przy recepcji głównej na parterze",
        "access_type": "public",
        "opening_hours": "24/7",
        "is_24_7": True,
        "indoor": True,
        "status": "operational",
        "source_name": "direct_submission",
    }
    create_resp = await client.post("/api/v1/aeds", json=payload_1)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["action"] == "created"
    aed_id = created_data["aed"]["id"]
    assert created_data["aed"]["completeness_score"] >= 90

    # Submit a near-duplicate (~6m away) from a municipal source -> must merge
    payload_2 = {
        "latitude": 53.12354,
        "longitude": 18.00845,
        "street_address": "ul. Jagiellońska 10",
        "city": "Bydgoszcz",
        "postal_code": "85-067",
        "teryt_code": "0461011",
        "location_description": "Hol wejściowy przy recepcji głównej na parterze, obok windy",
        "access_type": "public",
        "opening_hours": "24/7",
        "is_24_7": True,
        "indoor": True,
        "status": "operational",
        "source_name": "municipal_json",
    }
    merge_resp = await client.post("/api/v1/aeds", json=payload_2)
    assert merge_resp.status_code == 200
    merged_data = merge_resp.json()
    assert merged_data["action"] == "merged"
    assert merged_data["aed"]["id"] == aed_id
    assert merged_data["merged_distance_m"] < 25.0

    # Proximity query via /aeds?lat=...&lng=...&radius=500
    list_resp = await client.get("/api/v1/aeds?lat=53.1235&lng=18.0084&radius=500")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # Nearest query
    nearest_resp = await client.get("/api/v1/aeds/nearest?lat=53.1236&lng=18.0085&radius_m=1000")
    assert nearest_resp.status_code == 200
    items = nearest_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["walking_minutes"] >= 1

    # Verify endpoint updates status and timestamps
    verify_resp = await client.post(
        f"/api/v1/aeds/{aed_id}/verify",
        json={"action": "report_out_of_service", "reporter_org": "OSP Bydgoszcz", "notes": "Brak elektrod"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["status"] == "out_of_service"
    assert verify_resp.json()["last_verified_at"] is not None

    # Harvester stats reflect 1 unified AED + 1 duplicate merged
    stats_resp = await client.get("/api/v1/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_unified_aeds"] == 1
    assert stats["duplicates_merged"] == 1

    # Exports: GeoJSON + ETag / 304
    geo_resp = await client.get("/api/v1/export.geojson")
    assert geo_resp.status_code == 200
    assert geo_resp.headers["x-open-data-license"] == "CC0-1.0"
    assert "krajowy-rejestr-aed.geojson" in geo_resp.headers["content-disposition"]
    etag = geo_resp.headers["etag"]
    geo_json = geo_resp.json()
    assert geo_json["type"] == "FeatureCollection"
    assert len(geo_json["features"]) == 1

    not_mod = await client.get("/api/v1/export.geojson", headers={"If-None-Match": etag})
    assert not_mod.status_code == 304

    # Exports: CSV (UTF-8 BOM)
    csv_resp = await client.get("/api/v1/export.csv")
    assert csv_resp.status_code == 200
    csv_text = csv_resp.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 1
    assert rows[0]["city"] == "Bydgoszcz"

    # Exports: JSON-LD
    ld_resp = await client.get("/api/v1/export.jsonld")
    assert ld_resp.status_code == 200
    ld_doc = json.loads(ld_resp.content.decode("utf-8"))
    assert "@context" in ld_doc
    assert len(ld_doc["@graph"]) == 2

    # Live GeoJSON upload endpoint merges overlapping point within 25m
    upload_resp = await client.post(
        "/api/v1/ingest/upload",
        json={
            "source_name": "um_bydgoszcz_geojson",
            "payload": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [18.00842, 53.12352]},
                        "properties": {
                            "external_id": "UM-BYD-1",
                            "street_address": "ul. Jagiellońska 10",
                            "city": "Bydgoszcz",
                            "location_description": "Hol wejściowy przy recepcji głównej na parterze",
                        },
                    }
                ],
            },
        },
    )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    assert upload_data["records_valid"] == 1
    assert upload_data["duplicates_merged"] == 1
