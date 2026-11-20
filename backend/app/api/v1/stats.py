from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import get_source_trust_tier
from app.db.models import AED, AEDSourceRecord, IngestionRun
from app.db.session import get_db
from app.schemas.stats import SourceReconciliationRow, StatsResponse
from app.services.completeness import ensure_utc

router = APIRouter(tags=["Harvester Console"])

CORE_SOURCES = ["dane_gov_municipal", "pl_geojson", "osm_overpass", "direct_submission"]


@router.get("/stats", response_model=StatsResponse)
async def get_stats(session: AsyncSession = Depends(get_db)) -> StatsResponse:
    agg_stmt = select(
        func.count(AED.id),
        func.coalesce(func.avg(AED.completeness_score), 0.0),
    )
    total_aeds, avg_comp = (await session.execute(agg_stmt)).one()
    total_aeds = int(total_aeds or 0)
    avg_comp = round(float(avg_comp or 0.0), 1)

    compliant_count = int(
        (
            await session.execute(
                select(func.count(AED.id)).where(AED.completeness_score >= 80)
            )
        ).scalar_one()
        or 0
    )
    harvestable_count = int(
        (
            await session.execute(
                select(func.count(AED.id)).where(AED.completeness_score >= 60)
            )
        ).scalar_one()
        or 0
    )

    total_source_records = int(
        (await session.execute(select(func.count(AEDSourceRecord.id)))).scalar_one() or 0
    )
    total_duplicates_merged = max(0, total_source_records - total_aeds)

    sr_stats_rows = (
        await session.execute(
            select(
                AEDSourceRecord.source_name,
                func.count(AEDSourceRecord.id),
                func.max(AEDSourceRecord.ingested_at),
            ).group_by(AEDSourceRecord.source_name)
        )
    ).all()
    sr_count_map: dict[str, int] = {}
    sr_last_map: dict[str, datetime | None] = {}
    for s_name, cnt, max_ing in sr_stats_rows:
        sr_count_map[s_name] = int(cnt)
        sr_last_map[s_name] = ensure_utc(max_ing)

    active_sources = len(sr_count_map)

    runs = (
        await session.execute(
            select(IngestionRun).order_by(IngestionRun.started_at.desc())
        )
    ).scalars().all()
    latest_run_by_source: dict[str, IngestionRun] = {}
    run_dups_by_source: dict[str, int] = defaultdict(int)
    for r in runs:
        if r.source_name not in latest_run_by_source:
            latest_run_by_source[r.source_name] = r
        run_dups_by_source[r.source_name] += int(r.duplicates_merged or 0)

    # Identify direct/non-run merged records by finding AEDs with >1 provenance row
    multi_source_aed_ids = (
        await session.execute(
            select(AEDSourceRecord.aed_id)
            .group_by(AEDSourceRecord.aed_id)
            .having(func.count(AEDSourceRecord.id) > 1)
        )
    ).scalars().all()

    non_run_dups: dict[str, int] = defaultdict(int)
    if multi_source_aed_ids:
        multi_srs = (
            await session.execute(
                select(AEDSourceRecord)
                .where(AEDSourceRecord.aed_id.in_(multi_source_aed_ids))
                .order_by(AEDSourceRecord.ingested_at.asc())
            )
        ).scalars().all()
        seen_aed: set = set()
        for sr in multi_srs:
            if sr.aed_id not in seen_aed:
                seen_aed.add(sr.aed_id)
                continue
            if sr.ingestion_run_id is None:
                non_run_dups[sr.source_name] += 1

    all_sources = list(CORE_SOURCES)
    for s_name in sorted(set(sr_count_map.keys()) | set(latest_run_by_source.keys())):
        if s_name not in all_sources:
            all_sources.append(s_name)

    source_rows: list[SourceReconciliationRow] = []
    for s_name in all_sources:
        latest_run = latest_run_by_source.get(s_name)
        stored_cnt = sr_count_map.get(s_name, 0)
        if latest_run is not None:
            raw_cnt = int(latest_run.records_fetched)
            valid_cnt = int(latest_run.records_valid)
            pass_rate = round((valid_cnt / raw_cnt) * 100.0, 1) if raw_cnt > 0 else 0.0
            dups = run_dups_by_source.get(s_name, 0) + non_run_dups.get(s_name, 0)
            last_sync = ensure_utc(latest_run.finished_at or latest_run.started_at)
            run_status = latest_run.status
        elif stored_cnt > 0:
            raw_cnt = stored_cnt
            valid_cnt = stored_cnt
            pass_rate = 100.0
            dups = non_run_dups.get(s_name, 0)
            last_sync = sr_last_map.get(s_name)
            run_status = "completed"
        else:
            raw_cnt = 0
            valid_cnt = 0
            pass_rate = 0.0
            dups = 0
            last_sync = None
            run_status = "idle"

        source_rows.append(
            SourceReconciliationRow(
                source_name=s_name,
                trust_tier=get_source_trust_tier(s_name),
                raw_records=raw_cnt,
                valid_records=valid_cnt,
                pass_rate_pct=pass_rate,
                duplicates_merged=dups,
                last_sync_at=last_sync,
                status=run_status,
            )
        )

    source_rows.sort(key=lambda r: (r.trust_tier, r.source_name))

    return StatsResponse(
        total_unified_aeds=total_aeds,
        duplicates_merged=total_duplicates_merged,
        active_sources=active_sources,
        national_completeness_avg=avg_comp,
        standard_compliant_count=compliant_count,
        minimum_harvestable_count=harvestable_count,
        sources=source_rows,
    )
