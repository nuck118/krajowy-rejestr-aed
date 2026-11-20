import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.connectors.base import BaseConnector
from app.connectors.dane_gov_municipal import DaneGovMunicipalConnector
from app.connectors.json_payload import JSONPayloadConnector
from app.connectors.osm_overpass import OSMOverpassConnector
from app.connectors.pl_geojson import PLGeoJSONConnector
from app.core.config import settings
from app.core.constants import get_source_trust_tier
from app.db.models import AED, AEDSourceRecord, IngestionRun
from app.db.spatial import haversine_m
from app.schemas.ingestion import IngestionRunResponse
from app.services.deduplication import (
    RawRecord,
    build_new_aed,
    merge_fields,
    upsert_single_candidate,
)


def get_connector(source: str, bbox: str | None = None) -> BaseConnector:
    if source == "dane_gov_municipal":
        return DaneGovMunicipalConnector()
    if source == "pl_geojson":
        return PLGeoJSONConnector()
    if source == "osm_overpass":
        return OSMOverpassConnector(bbox=bbox)
    raise ValueError(f"Unsupported ingestion source: {source}")


def _grid_cell(lat: float, lng: float) -> tuple[int, int]:
    return int(lat * 1000), int(lng * 1000)


async def _run_bulk_ingestion(
    session: AsyncSession,
    records: list[RawRecord],
    run_id: uuid.UUID,
    radius_m: float,
    is_postgres: bool,
) -> tuple[int, int]:
    now = datetime.now(timezone.utc)

    existing_aeds = (
        await session.execute(select(AED).options(lazyload(AED.source_records)))
    ).scalars().all()
    aed_by_id: dict[uuid.UUID, AED] = {aed.id: aed for aed in existing_aeds}

    grid: dict[tuple[int, int], list[AED]] = defaultdict(list)
    for aed in existing_aeds:
        grid[_grid_cell(aed.latitude, aed.longitude)].append(aed)

    existing_srs = (await session.execute(select(AEDSourceRecord))).scalars().all()
    existing_sr_map: dict[tuple[str, str], AEDSourceRecord] = {}
    aed_sources: dict[uuid.UUID, set[tuple[str, str]]] = defaultdict(set)
    for sr in existing_srs:
        existing_sr_map[(sr.source_name, sr.external_id)] = sr
        aed_sources[sr.aed_id].add((sr.source_name, sr.external_id))

    new_aeds: list[AED] = []
    new_source_records: list[AEDSourceRecord] = []
    records_inserted = 0
    duplicates_merged = 0

    for record in records:
        sr_key = (record.source_name, record.external_id)
        trust_tier = get_source_trust_tier(record.source_name)

        # 1. Idempotency check
        if sr_key in existing_sr_map:
            existing_sr = existing_sr_map[sr_key]
            existing_sr.raw_payload = record.raw_payload
            existing_sr.ingested_at = now
            existing_sr.ingestion_run_id = run_id
            linked_aed = aed_by_id.get(existing_sr.aed_id)
            if linked_aed is not None:
                merge_fields(linked_aed, record.candidate, record.source_name, is_postgres)
            continue

        # 2. Spatial candidate search in 3x3 0.001-deg cells (~111m)
        gx, gy = _grid_cell(record.candidate.latitude, record.candidate.longitude)
        nearby: list[tuple[AED, float]] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for cand in grid.get((gx + dx, gy + dy), ()):
                    dist = haversine_m(
                        record.candidate.latitude,
                        record.candidate.longitude,
                        cand.latitude,
                        cand.longitude,
                    )
                    if dist <= radius_m:
                        nearby.append((cand, dist))
        nearby.sort(key=lambda item: item[1])

        # 3. Same-source multi-unit guard
        matched_aed: AED | None = None
        for cand, _dist in nearby:
            sources_for_cand = aed_sources.get(cand.id, set())
            if any(
                s_name == record.source_name and ext_id != record.external_id
                for s_name, ext_id in sources_for_cand
            ):
                continue
            matched_aed = cand
            break

        if matched_aed is not None:
            merge_fields(matched_aed, record.candidate, record.source_name, is_postgres)
            sr = AEDSourceRecord(
                id=uuid.uuid4(),
                aed_id=matched_aed.id,
                ingestion_run_id=run_id,
                source_name=record.source_name,
                source_trust_tier=trust_tier,
                external_id=record.external_id,
                raw_payload=record.raw_payload,
                ingested_at=now,
            )
            new_source_records.append(sr)
            existing_sr_map[sr_key] = sr
            aed_sources[matched_aed.id].add(sr_key)
            duplicates_merged += 1
        else:
            new_aed = build_new_aed(record, is_postgres)
            new_aed.id = uuid.uuid4()
            new_aeds.append(new_aed)
            aed_by_id[new_aed.id] = new_aed
            grid[(gx, gy)].append(new_aed)
            sr = AEDSourceRecord(
                id=uuid.uuid4(),
                aed_id=new_aed.id,
                ingestion_run_id=run_id,
                source_name=record.source_name,
                source_trust_tier=trust_tier,
                external_id=record.external_id,
                raw_payload=record.raw_payload,
                ingested_at=now,
            )
            new_source_records.append(sr)
            existing_sr_map[sr_key] = sr
            aed_sources[new_aed.id].add(sr_key)
            records_inserted += 1

    chunk_size = 1000
    for i in range(0, len(new_aeds), chunk_size):
        session.add_all(new_aeds[i : i + chunk_size])
        await session.flush()

    for i in range(0, len(new_source_records), chunk_size):
        session.add_all(new_source_records[i : i + chunk_size])
        await session.flush()

    return records_inserted, duplicates_merged


async def _execute_connector(
    session: AsyncSession,
    connector: BaseConnector,
) -> IngestionRunResponse:
    started_perf = time.perf_counter()
    run = IngestionRun(
        id=uuid.uuid4(),
        source_name=connector.source_name,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.flush()

    try:
        fetch_result = await connector.fetch()
        run.records_fetched = fetch_result.fetched_count
        run.records_rejected = fetch_result.rejected_count
        run.records_valid = len(fetch_result.records)

        if len(fetch_result.records) > 500:
            inserted, merged = await _run_bulk_ingestion(
                session=session,
                records=fetch_result.records,
                run_id=run.id,
                radius_m=settings.DEDUP_RADIUS_M,
                is_postgres=settings.is_postgres,
            )
        else:
            inserted = 0
            merged = 0
            for record in fetch_result.records:
                action, _aed, _dist = await upsert_single_candidate(
                    session,
                    record,
                    radius_m=settings.DEDUP_RADIUS_M,
                    is_postgres=settings.is_postgres,
                    ingestion_run_id=run.id,
                )
                if action == "created":
                    inserted += 1
                elif action == "merged":
                    merged += 1

        run.records_inserted = inserted
        run.duplicates_merged = merged
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        await session.commit()
    except Exception as exc:
        run.status = "failed"
        run.error_summary = str(exc)[:1000]
        run.finished_at = datetime.now(timezone.utc)
        await session.commit()
        raise

    duration_ms = int((time.perf_counter() - started_perf) * 1000)
    return IngestionRunResponse(
        id=run.id,
        source_name=run.source_name,
        status=run.status,
        records_fetched=run.records_fetched,
        records_valid=run.records_valid,
        records_rejected=run.records_rejected,
        records_inserted=run.records_inserted,
        duplicates_merged=run.duplicates_merged,
        error_summary=run.error_summary,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=duration_ms,
    )


async def execute_ingestion_run(
    session: AsyncSession,
    source: str,
    bbox: str | None = None,
) -> IngestionRunResponse:
    connector = get_connector(source, bbox=bbox)
    return await _execute_connector(session, connector)


async def execute_payload_ingestion(
    session: AsyncSession,
    source_name: str,
    payload: dict[str, Any] | list[Any],
) -> IngestionRunResponse:
    connector = JSONPayloadConnector(source_name=source_name.strip(), payload=payload)
    return await _execute_connector(session, connector)
