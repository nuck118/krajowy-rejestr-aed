from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AED, AEDSourceRecord
from app.schemas.aed import AEDIngestCandidate
from app.services.deduplication import RawRecord, upsert_single_candidate


@pytest.mark.asyncio
async def test_spatial_deduplication_merges_within_25m(db_session: AsyncSession) -> None:
    osm_record = RawRecord(
        source_name="osm_overpass",
        external_id="osm:node:1001",
        candidate=AEDIngestCandidate(
            latitude=53.123500,
            longitude=18.008400,
            location_description="Portiernia",
            access_type="public",
            indoor=True,
            status="unverified",
        ),
        raw_payload={"id": 1001},
    )
    action1, aed1, dist1 = await upsert_single_candidate(
        db_session, osm_record, radius_m=25.0, is_postgres=False
    )
    assert action1 == "created"
    assert dist1 is None
    initial_score = aed1.completeness_score

    # Municipal record ~8m away with richer addressing & newer verification
    mun_record = RawRecord(
        source_name="uploaded_dataset",
        external_id="BYD-001",
        candidate=AEDIngestCandidate(
            latitude=53.123550,
            longitude=18.008480,
            street_address="ul. Gdańska 15",
            city="Bydgoszcz",
            postal_code="85-005",
            teryt_code="0461011",
            location_description="Hol główny na parterze przy stanowisku ochrony budynku",
            access_type="public",
            opening_hours="24/7",
            is_24_7=True,
            indoor=True,
            status="operational",
            last_verified_at=datetime.now(timezone.utc),
        ),
        raw_payload={"external_id": "BYD-001"},
    )
    action2, aed2, dist2 = await upsert_single_candidate(
        db_session, mun_record, radius_m=25.0, is_postgres=False
    )
    assert action2 == "merged"
    assert aed2.id == aed1.id
    assert dist2 is not None and dist2 < 25.0
    assert aed2.primary_source == "uploaded_dataset"
    assert aed2.city == "Bydgoszcz"
    assert aed2.street_address == "ul. Gdańska 15"
    assert aed2.completeness_score > initial_score
    assert aed2.completeness_score == 100

    total_aeds = (await db_session.execute(select(func.count(AED.id)))).scalar_one()
    total_srs = (await db_session.execute(select(func.count(AEDSourceRecord.id)))).scalar_one()
    assert total_aeds == 1
    assert total_srs == 2


@pytest.mark.asyncio
async def test_same_source_multi_unit_building_guard(db_session: AsyncSession) -> None:
    rec1 = RawRecord(
        source_name="uploaded_dataset",
        external_id="TERM-FL1",
        candidate=AEDIngestCandidate(
            latitude=52.170750,
            longitude=20.972580,
            city="Warszawa",
            location_description="Terminal A poziom przylotów, strefa ogólnodostępna",
            status="operational",
        ),
        raw_payload={"id": "TERM-FL1"},
    )
    rec2 = RawRecord(
        source_name="uploaded_dataset",
        external_id="TERM-FL2",
        candidate=AEDIngestCandidate(
            latitude=52.170790,
            longitude=20.972620,
            city="Warszawa",
            location_description="Terminal A poziom odlotów przy stanowisku odprawy B",
            status="operational",
        ),
        raw_payload={"id": "TERM-FL2"},
    )

    a1, _, _ = await upsert_single_candidate(db_session, rec1, radius_m=25.0, is_postgres=False)
    a2, _, _ = await upsert_single_candidate(db_session, rec2, radius_m=25.0, is_postgres=False)
    assert a1 == "created"
    assert a2 == "created"

    total_aeds = (await db_session.execute(select(func.count(AED.id)))).scalar_one()
    assert total_aeds == 2


@pytest.mark.asyncio
async def test_idempotent_reingestion_updates_without_duplicating(db_session: AsyncSession) -> None:
    rec = RawRecord(
        source_name="pl_geojson",
        external_id="osm:node:5555",
        candidate=AEDIngestCandidate(
            latitude=53.130000,
            longitude=18.010000,
            location_description="Wejście główne",
            status="unverified",
        ),
        raw_payload={"v": 1},
    )
    a1, aed1, _ = await upsert_single_candidate(db_session, rec, radius_m=25.0, is_postgres=False)
    assert a1 == "created"

    rec_v2 = RawRecord(
        source_name="pl_geojson",
        external_id="osm:node:5555",
        candidate=AEDIngestCandidate(
            latitude=53.130000,
            longitude=18.010000,
            location_description="Wejście główne przy portierni na parterze",
            status="operational",
        ),
        raw_payload={"v": 2},
    )
    a2, aed2, _ = await upsert_single_candidate(db_session, rec_v2, radius_m=25.0, is_postgres=False)
    assert a2 == "updated"
    assert aed2.id == aed1.id
    assert "portierni" in (aed2.location_description or "")
    total_srs = (await db_session.execute(select(func.count(AEDSourceRecord.id)))).scalar_one()
    assert total_srs == 1
