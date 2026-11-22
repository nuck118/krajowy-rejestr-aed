import hashlib
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_harvester_xml_1_13_md5_head_and_validator(client: AsyncClient) -> None:
    # 1. HEAD request on .xml must return 200 and application/xml Content-Type
    head_xml = await client.head("/api/v1/harvester/dane-gov.xml")
    assert head_xml.status_code == 200
    assert "application/xml" in head_xml.headers["content-type"]
    assert head_xml.headers["x-harvester-schema-version"] == "1.13"

    # 2. GET request on .xml must use urn:otwarte-dane:harvester:1.13 and XSD 1.13 tags
    get_xml = await client.get("/api/v1/harvester/dane-gov.xml")
    assert get_xml.status_code == 200
    xml_text = get_xml.text
    assert 'xmlns:ns2="urn:otwarte-dane:harvester:1.13"' in xml_text
    assert "<dbOrCopyrightedLicenseChosen>CC0 1.0</dbOrCopyrightedLicenseChosen>" in xml_text
    assert "<hasHighValueDataFromEuropeanCommissionList>true</hasHighValueDataFromEuropeanCommissionList>" in xml_text
    assert "<License>" not in xml_text
    assert "<opennessScore>" not in xml_text

    # 3. Companion .md5 endpoint must match exact MD5 digest of .xml payload
    head_md5 = await client.head("/api/v1/harvester/dane-gov.md5")
    assert head_md5.status_code == 200
    assert "text/plain" in head_md5.headers["content-type"]

    get_md5 = await client.get("/api/v1/harvester/dane-gov.md5")
    assert get_md5.status_code == 200
    expected_md5 = hashlib.md5(get_xml.content).hexdigest().lower()
    assert get_md5.text.strip() == expected_md5

    # 4. 5-step MCOD validate_xml_url verification endpoint
    val_resp = await client.get("/api/v1/harvester/validate")
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid"] is True
    assert val_data["xsd_schema_version"] == "1.13"
    assert val_data["md5_verified"] is True
    assert val_data["md5_checksum"] == expected_md5
    assert val_data["datasets_count"] == 1
    assert val_data["resources_count"] == 4
    assert val_data["errors"] == []


@pytest.mark.asyncio
async def test_mcod_v2_63_likes_and_sorting(client: AsyncClient) -> None:
    # Create two AED records
    r1 = await client.post(
        "/api/v1/aeds",
        json={
            "latitude": 52.2297,
            "longitude": 21.0122,
            "street_address": "ul. Marszałkowska 1",
            "city": "Warszawa",
            "postal_code": "00-001",
            "location_description": "Wejście główne przy portierni parter",
            "access_type": "public",
            "is_24_7": True,
            "indoor": False,
            "status": "operational",
        },
    )
    assert r1.status_code == 201
    aed_1_id = r1.json()["aed"]["id"]

    r2 = await client.post(
        "/api/v1/aeds",
        json={
            "latitude": 50.0647,
            "longitude": 19.9450,
            "street_address": "Rynek Główny 1",
            "city": "Kraków",
            "postal_code": "31-042",
            "location_description": "Kapsuła zewnętrzna na ścianie Sukiennic",
            "access_type": "public",
            "is_24_7": True,
            "indoor": False,
            "status": "operational",
        },
    )
    assert r2.status_code == 201
    aed_2_id = r2.json()["aed"]["id"]

    # Like aed_2 as user-A and user-B (2 likes), and aed_1 as user-A (1 like)
    like_2_a = await client.post(
        f"/api/v1/aeds/{aed_2_id}/likes", headers={"X-User-Id": "user-A"}
    )
    assert like_2_a.status_code == 201
    assert like_2_a.json()["likes_count"] == 1
    assert like_2_a.json()["is_liked_by_current_user"] is True

    like_2_b = await client.post(
        f"/api/v1/aeds/{aed_2_id}/likes", headers={"X-User-Id": "user-B"}
    )
    assert like_2_b.status_code == 201
    assert like_2_b.json()["likes_count"] == 2

    like_1_a = await client.post(
        f"/api/v1/aeds/{aed_1_id}/likes", headers={"X-User-Id": "user-A"}
    )
    assert like_1_a.status_code == 201
    assert like_1_a.json()["likes_count"] == 1

    # Sort descending by likes_count (OTD-3183)
    sorted_desc = await client.get(
        "/api/v1/aeds?sort=-likes_count", headers={"X-User-Id": "user-B"}
    )
    assert sorted_desc.status_code == 200
    items_desc = sorted_desc.json()["items"]
    assert items_desc[0]["id"] == aed_2_id
    assert items_desc[0]["likes_count"] == 2
    assert items_desc[0]["is_liked_by_current_user"] is True
    assert items_desc[1]["id"] == aed_1_id
    assert items_desc[1]["likes_count"] == 1
    assert items_desc[1]["is_liked_by_current_user"] is False

    # Dataset likes (OTD-3100 / OTD-3101 / OTD-3155)
    ds_like = await client.post(
        "/api/v1/datasets/1/likes", headers={"X-User-Id": "user-A"}
    )
    assert ds_like.status_code == 201
    assert ds_like.json()["data"]["attributes"]["likes_count"] == 1
    assert ds_like.json()["data"]["attributes"]["is_liked_by_current_user"] is True

    user_likes = await client.get(
        "/api/v1/auth/user/likes", headers={"X-User-Id": "user-A"}
    )
    assert user_likes.status_code == 200
    ul_data = user_likes.json()
    assert ul_data["likes_count"] == 3  # 1 dataset + 2 AEDs
    assert "krajowy-rejestr-aed-polska" in ul_data["liked_datasets_ids"]
    assert aed_1_id in ul_data["liked_aeds_ids"]
    assert aed_2_id in ul_data["liked_aeds_ids"]

    dash_resp = await client.get(
        "/api/v1/auth/user/dashboard", headers={"X-User-Id": "user-A"}
    )
    assert dash_resp.status_code == 200
    assert dash_resp.json()["data"]["attributes"]["likes_count"] == 3

    # Remove like on aed_1 and dataset 1
    del_aed_like = await client.delete(
        f"/api/v1/aeds/{aed_1_id}/likes", headers={"X-User-Id": "user-A"}
    )
    assert del_aed_like.status_code == 204

    del_ds_like = await client.delete(
        "/api/v1/datasets/1/likes", headers={"X-User-Id": "user-A"}
    )
    assert del_ds_like.status_code == 204


@pytest.mark.asyncio
async def test_mcod_middlewares_slow_sql_prometheus_and_counters(client: AsyncClient) -> None:
    # 1. ApiVersionMiddleware & LocaleMiddleware headers
    ping_resp = await client.get("/ping?lang=en", headers={"X-API-Version": "1.4"})
    assert ping_resp.status_code == 200
    assert ping_resp.json() == {"data": None}
    assert ping_resp.headers["x-api-version"] == "1.4"
    assert ping_resp.headers["content-language"] == "en"

    # Unsupported X-API-Version returns 400 Bad Request matching MCOD
    bad_ver = await client.get("/ping", headers={"X-API-Version": "9.9"})
    assert bad_ver.status_code == 400
    assert bad_ver.json()["title"] == "Unsupported version"

    # 2. SlowSQLMiddleware (OTD-3073) detection via simulated slow query header
    slow_resp = await client.get(
        "/api/v1/stats",
        headers={"X-Simulate-Slow-SQL-Ms": "1500", "X-User-Id": "auditor"},
    )
    assert slow_resp.status_code == 200

    cluster_resp = await client.get("/api/v1/cluster/health")
    assert cluster_resp.status_code == 200
    cluster_data = cluster_resp.json()
    assert cluster_data["status"] == "green"
    assert cluster_data["slow_sql_total_detected"] >= 1
    latest_slow = cluster_data["recent_slow_sql_events"][-1]
    assert latest_slow["event_type"] == "slow_sql"
    assert latest_slow["duration"] >= 1.5
    assert latest_slow["operation"] == "GET /api/v1/stats"
    assert len(latest_slow["sql_hash"]) == 16

    # 3. CounterMiddleware increments views_count & downloads_count
    await client.get("/api/v1/export.geojson")
    ds_resp = await client.get("/api/v1/datasets")
    assert ds_resp.status_code == 200
    ds_attrs = ds_resp.json()["data"][0]["attributes"]
    assert ds_attrs["downloads_count"] >= 1

    res_resp = await client.get("/api/v1/datasets/1/resources")
    assert res_resp.status_code == 200
    geo_res = res_resp.json()["data"][0]["attributes"]
    assert geo_res["downloads_count"] >= 1

    # 4. Prometheus /metrics endpoint (OTD-3073)
    metrics_resp = await client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "text/plain" in metrics_resp.headers["content-type"]
    metrics_text = metrics_resp.text
    assert "http_requests_total" in metrics_text
    assert "http_request_duration_seconds_sum" in metrics_text
    assert "falcon_db_query_duration_seconds_sum" in metrics_text
    assert "slow_sql_queries_total" in metrics_text
    assert "resources_total" in metrics_text


@pytest.mark.asyncio
async def test_dcat_ap_pl_catalog_vocabs_dga_and_broken_links(client: AsyncClient) -> None:
    # 1. DCAT-AP-PL RDF Catalog in JSON-LD, Turtle, RDF/XML, and N-Triples
    cat_jsonld = await client.get("/api/v1/catalog")
    assert cat_jsonld.status_code == 200
    assert "application/ld+json" in cat_jsonld.headers["content-type"]
    assert cat_jsonld.json()["@type"] == "dcat:Catalog"

    cat_ttl = await client.get("/api/v1/catalog.ttl")
    assert cat_ttl.status_code == 200
    assert "text/turtle" in cat_ttl.headers["content-type"]
    assert "dcatappl:opennessScore" in cat_ttl.text

    cat_xml = await client.get("/api/v1/catalog.xml")
    assert cat_xml.status_code == 200
    assert "application/rdf+xml" in cat_xml.headers["content-type"]
    assert "<dcat:Catalog" in cat_xml.text

    cat_nt = await client.get("/api/v1/catalog.nt")
    assert cat_nt.status_code == 200
    assert "application/n-triples" in cat_nt.headers["content-type"]

    # 2. Controlled SKOS Vocabularies (openness-score & special-sign)
    vocab_os = await client.get("/api/v1/vocab/openness-score")
    assert vocab_os.status_code == 200
    assert "4-stars" in vocab_os.json()["entries"]

    entry_4 = await client.get("/api/v1/vocab/openness-score/4-stars")
    assert entry_4.status_code == 200
    assert entry_4.json()["notation"] == "****"

    missing_entry = await client.get("/api/v1/vocab/openness-score/9-stars")
    assert missing_entry.status_code == 404

    vocab_ss = await client.get("/api/v1/vocab/special-sign")
    assert vocab_ss.status_code == 200
    assert "-" in vocab_ss.json()["entries"]

    # 3. Broken Links Report, DGA Aggregated, and Dynamic dane.gov.pl Discovery
    bl_resp = await client.get("/api/v1/reports/brokenlinks")
    assert bl_resp.status_code == 200
    assert bl_resp.json()["meta"]["total_checked_resources"] == 4

    dga_resp = await client.get("/api/v1/dga-aggregated")
    assert dga_resp.status_code == 200
    assert dga_resp.json()["data"]["attributes"]["contains_protected_data"] is False

    disc_resp = await client.get("/api/v1/ingest/discover-dane-gov?q=AED")
    assert disc_resp.status_code == 200
    assert disc_resp.json()["total_resources"] >= 4
