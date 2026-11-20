from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import (
    POLAND_LAT_MAX,
    POLAND_LAT_MIN,
    POLAND_LNG_MAX,
    POLAND_LNG_MIN,
)

AccessType = Literal["public", "customers_only", "private"]
AedStatus = Literal["operational", "out_of_service", "unverified"]
VerificationAction = Literal["confirm_operational", "report_out_of_service", "report_missing"]


def _clean_opt_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned if cleaned else None


class AEDIngestCandidate(BaseModel):
    latitude: float = Field(..., ge=POLAND_LAT_MIN, le=POLAND_LAT_MAX, description="WGS84 latitude within Poland")
    longitude: float = Field(..., ge=POLAND_LNG_MIN, le=POLAND_LNG_MAX, description="WGS84 longitude within Poland")
    street_address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, pattern=r"^\d{2}-\d{3}$")
    teryt_code: str | None = Field(default=None, pattern=r"^\d{7}$")
    location_description: str | None = Field(default=None, max_length=500)
    access_type: AccessType = "public"
    opening_hours: str | None = Field(default=None, max_length=255)
    is_24_7: bool = False
    indoor: bool | None = None
    status: AedStatus = "unverified"
    last_verified_at: datetime | None = None

    @field_validator("latitude", "longitude")
    @classmethod
    def round_coords(cls, value: float) -> float:
        return round(float(value), 6)

    @field_validator("street_address", "city", "location_description", "opening_hours", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return _clean_opt_str(str(value))

    @field_validator("postal_code", "teryt_code", mode="before")
    @classmethod
    def normalize_codes(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned else None

    @model_validator(mode="after")
    def sync_24_7_hours(self) -> "AEDIngestCandidate":
        if self.opening_hours and self.opening_hours.strip().lower() == "24/7":
            self.opening_hours = "24/7"
            self.is_24_7 = True
        elif self.is_24_7 and not self.opening_hours:
            self.opening_hours = "24/7"
        return self


class AEDCreate(AEDIngestCandidate):
    location_description: str = Field(..., min_length=3, max_length=500)
    source_name: str = Field(default="direct_submission", min_length=2, max_length=100)
    external_id: str | None = Field(default=None, max_length=255)


class SourceRecordSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_name: str
    source_trust_tier: int
    external_id: str
    ingested_at: datetime


class AEDRead(AEDIngestCandidate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    completeness_score: int = Field(..., ge=0, le=100)
    completeness_tier: str
    primary_source: str
    sources: list[str] = Field(default_factory=list)
    open_now: bool | None = None
    created_at: datetime
    updated_at: datetime


class AEDExtraMetadata(BaseModel):
    location_pl: str | None = None
    location_en: str | None = None
    operator: str | None = None
    level: str | None = None
    phone: str | None = None
    website: str | None = None
    email: str | None = None
    wheelchair: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    image_url: str | None = None
    note: str | None = None
    fixme: str | None = None
    source_ref: str | None = None
    osm_url: str | None = None


class AEDDetailRead(AEDRead):
    provenance: list[SourceRecordSummary] = Field(default_factory=list)
    extra_metadata: AEDExtraMetadata = Field(default_factory=AEDExtraMetadata)


class AEDNearestRead(AEDRead):
    distance_m: float
    walking_minutes: int


class AEDSubmitResponse(BaseModel):
    action: Literal["created", "merged"]
    merged_distance_m: float | None = None
    aed: AEDRead


class AEDVerifyRequest(BaseModel):
    action: VerificationAction
    reporter_org: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    location_description: str | None = Field(default=None, max_length=500)

    @field_validator("location_description", mode="before")
    @classmethod
    def normalize_location_description(cls, value: object) -> str | None:
        if value is None:
            return None
        return _clean_opt_str(str(value))


class PaginatedAEDResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AEDRead]


class NearestAEDResponse(BaseModel):
    origin: dict[str, float]
    radius_m: float
    count: int
    items: list[AEDNearestRead]
