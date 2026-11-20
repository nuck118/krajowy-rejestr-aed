from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import get_source_trust_tier
from app.db.models import AED, AEDSourceRecord, make_geom_value
from app.db.spatial import find_dedup_candidates
from app.schemas.aed import AEDIngestCandidate
from app.services.completeness import compute_completeness_for_obj, ensure_utc


@dataclass(slots=True)
class RawRecord:
    source_name: str
    external_id: str
    candidate: AEDIngestCandidate
    raw_payload: dict[str, Any]


def _should_prefer_incoming(
    existing_verified: datetime | None,
    existing_tier: int,
    incoming_verified: datetime | None,
    incoming_tier: int,
) -> bool:
    ev = ensure_utc(existing_verified)
    iv = ensure_utc(incoming_verified)
    if ev is not None and iv is not None and ev != iv:
        return iv > ev
    if incoming_tier != existing_tier:
        return incoming_tier < existing_tier
    if iv is not None and ev is None:
        return True
    return False


def merge_fields(
    existing_aed: AED,
    incoming: AEDIngestCandidate,
    incoming_source_name: str,
    is_postgres: bool,
) -> AED:
    existing_tier = get_source_trust_tier(existing_aed.primary_source)
    incoming_tier = get_source_trust_tier(incoming_source_name)
    prefer_incoming = _should_prefer_incoming(
        existing_aed.last_verified_at,
        existing_tier,
        incoming.last_verified_at,
        incoming_tier,
    )

    # Coordinates: keep canonical unless incoming source has strictly higher trust (lower tier number)
    if incoming_tier < existing_tier:
        existing_aed.latitude = incoming.latitude
        existing_aed.longitude = incoming.longitude
        existing_aed.geom = make_geom_value(incoming.latitude, incoming.longitude, is_postgres)
        existing_aed.primary_source = incoming_source_name

    # Scalar metadata fields
    for field_name in (
        "street_address",
        "city",
        "postal_code",
        "teryt_code",
        "opening_hours",
    ):
        cur_val = getattr(existing_aed, field_name)
        inc_val = getattr(incoming, field_name)
        if inc_val is not None and (cur_val is None or prefer_incoming):
            setattr(existing_aed, field_name, inc_val)

    # Indoor boolean (None vs explicit bool)
    if incoming.indoor is not None and (existing_aed.indoor is None or prefer_incoming):
        existing_aed.indoor = incoming.indoor

    # Access type (default is 'public', only overwrite if prefer_incoming or existing was default & incoming is specific)
    if prefer_incoming:
        existing_aed.access_type = incoming.access_type

    # is_24_7 sync
    if incoming.is_24_7 and (not existing_aed.is_24_7 or prefer_incoming):
        existing_aed.is_24_7 = True
        if not existing_aed.opening_hours:
            existing_aed.opening_hours = "24/7"
    elif prefer_incoming and incoming.opening_hours is not None:
        existing_aed.is_24_7 = incoming.is_24_7

    # Placement description: longer wins when tiers/timestamps tie, otherwise prefer_incoming
    cur_desc = (existing_aed.location_description or "").strip()
    inc_desc = (incoming.location_description or "").strip()
    if inc_desc:
        if not cur_desc:
            existing_aed.location_description = inc_desc
        elif prefer_incoming:
            existing_aed.location_description = inc_desc
        elif incoming_tier == existing_tier and len(inc_desc) > len(cur_desc):
            existing_aed.location_description = inc_desc

    # Status merge policy
    ev = ensure_utc(existing_aed.last_verified_at)
    iv = ensure_utc(incoming.last_verified_at)
    if incoming.status == "out_of_service":
        if existing_aed.status == "unverified" or prefer_incoming:
            existing_aed.status = "out_of_service"
    elif incoming.status == "operational":
        if existing_aed.status == "unverified" or prefer_incoming:
            existing_aed.status = "operational"

    # Last verified timestamp: keep newest non-null
    if iv is not None and (ev is None or iv > ev):
        existing_aed.last_verified_at = iv

    existing_aed.updated_at = datetime.now(timezone.utc)
    existing_aed.completeness_score = compute_completeness_for_obj(existing_aed)
    return existing_aed


def build_new_aed(
    record: RawRecord,
    is_postgres: bool,
) -> AED:
    c = record.candidate
    now = datetime.now(timezone.utc)
    aed = AED(
        geom=make_geom_value(c.latitude, c.longitude, is_postgres),
        latitude=c.latitude,
        longitude=c.longitude,
        street_address=c.street_address,
        city=c.city,
        postal_code=c.postal_code,
        teryt_code=c.teryt_code,
        location_description=c.location_description,
        access_type=c.access_type,
        opening_hours=c.opening_hours,
        is_24_7=c.is_24_7,
        indoor=c.indoor,
        status=c.status,
        primary_source=record.source_name,
        last_verified_at=ensure_utc(c.last_verified_at),
        created_at=now,
        updated_at=now,
    )
    aed.completeness_score = compute_completeness_for_obj(aed, now=now)
    return aed


async def upsert_single_candidate(
    session: AsyncSession,
    record: RawRecord,
    *,
    radius_m: float,
    is_postgres: bool,
    ingestion_run_id: UUID | None = None,
) -> tuple[str, AED, float | None]:
    trust_tier = get_source_trust_tier(record.source_name)
    now = datetime.now(timezone.utc)

    # 1. Idempotency check by (source_name, external_id)
    existing_sr_stmt = select(AEDSourceRecord).where(
        AEDSourceRecord.source_name == record.source_name,
        AEDSourceRecord.external_id == record.external_id,
    )
    existing_sr = (await session.execute(existing_sr_stmt)).scalar_one_or_none()
    if existing_sr is not None:
        aed = (await session.execute(select(AED).where(AED.id == existing_sr.aed_id))).scalar_one()
        existing_sr.raw_payload = record.raw_payload
        existing_sr.ingested_at = now
        if ingestion_run_id is not None:
            existing_sr.ingestion_run_id = ingestion_run_id
        merge_fields(aed, record.candidate, record.source_name, is_postgres)
        await session.flush()
        return "updated", aed, 0.0

    # 2. Spatial candidate lookup within radius_m
    candidates = await find_dedup_candidates(
        session,
        record.candidate.latitude,
        record.candidate.longitude,
        radius_m,
        is_postgres,
    )

    # 3. Same-source multi-unit building guard
    matched_aed: AED | None = None
    matched_dist: float | None = None
    for candidate_aed, dist_m in candidates:
        has_same_source_diff_id = any(
            sr.source_name == record.source_name and sr.external_id != record.external_id
            for sr in candidate_aed.source_records
        )
        if has_same_source_diff_id:
            continue
        matched_aed = candidate_aed
        matched_dist = round(dist_m, 1)
        break

    if matched_aed is not None:
        merge_fields(matched_aed, record.candidate, record.source_name, is_postgres)
        sr = AEDSourceRecord(
            aed_id=matched_aed.id,
            ingestion_run_id=ingestion_run_id,
            source_name=record.source_name,
            source_trust_tier=trust_tier,
            external_id=record.external_id,
            raw_payload=record.raw_payload,
            ingested_at=now,
        )
        session.add(sr)
        await session.flush()
        await session.refresh(matched_aed, attribute_names=["source_records"])
        return "merged", matched_aed, matched_dist

    # 4. Insert net-new canonical record
    new_aed = build_new_aed(record, is_postgres)
    session.add(new_aed)
    await session.flush()

    sr = AEDSourceRecord(
        aed_id=new_aed.id,
        ingestion_run_id=ingestion_run_id,
        source_name=record.source_name,
        source_trust_tier=trust_tier,
        external_id=record.external_id,
        raw_payload=record.raw_payload,
        ingested_at=now,
    )
    session.add(sr)
    await session.flush()
    await session.refresh(new_aed, attribute_names=["source_records"])
    return "created", new_aed, None
