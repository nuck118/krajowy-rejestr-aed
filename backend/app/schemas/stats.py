from datetime import datetime
from pydantic import BaseModel


class SourceReconciliationRow(BaseModel):
    source_name: str
    trust_tier: int
    raw_records: int
    valid_records: int
    pass_rate_pct: float
    duplicates_merged: int
    last_sync_at: datetime | None = None
    status: str


class StatsResponse(BaseModel):
    total_unified_aeds: int
    duplicates_merged: int
    active_sources: int
    national_completeness_avg: float
    standard_compliant_count: int
    minimum_harvestable_count: int
    sources: list[SourceReconciliationRow]
