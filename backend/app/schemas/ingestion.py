from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

IngestionSource = Literal["dane_gov_municipal", "pl_geojson", "osm_overpass"]


class IngestionRunRequest(BaseModel):
    source: IngestionSource
    bbox: str | None = Field(
        default=None,
        description="Optional Overpass bounding box south,west,north,east (e.g. 53.08,17.92,53.17,18.12)",
    )


class IngestionUploadRequest(BaseModel):
    source_name: str = Field(
        default="uploaded_dataset",
        min_length=2,
        max_length=100,
        description="Identifier of the uploaded municipal or institutional dataset",
    )
    payload: dict[str, Any] | list[Any]


class IngestionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_name: str
    status: str
    records_fetched: int
    records_valid: int
    records_rejected: int
    records_inserted: int
    duplicates_merged: int
    error_summary: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int
