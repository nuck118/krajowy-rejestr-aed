import uuid
from datetime import datetime, timezone
from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_geom_value(latitude: float, longitude: float, is_postgres: bool) -> Any:
    wkt = f"POINT({longitude} {latitude})"
    if is_postgres:
        return WKTElement(wkt, srid=4326)
    return wkt


class Base(DeclarativeBase):
    pass


class AED(Base):
    __tablename__ = "aeds"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    geom: Mapped[Any] = mapped_column(
        Text().with_variant(Geometry(geometry_type="POINT", srid=4326, spatial_index=False), "postgresql"),
        nullable=False,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    street_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    teryt_code: Mapped[str | None] = mapped_column(String(7), nullable=True)
    location_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    access_type: Mapped[str] = mapped_column(String(32), nullable=False, default="public")
    opening_hours: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_24_7: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    indoor: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified")

    completeness_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    primary_source: Mapped[str] = mapped_column(String(100), nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    source_records: Mapped[list["AEDSourceRecord"]] = relationship(
        back_populates="aed",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    verifications: Mapped[list["AEDVerification"]] = relationship(
        back_populates="aed",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint("latitude >= 49.0 AND latitude <= 55.0", name="ck_aeds_lat_bounds"),
        CheckConstraint("longitude >= 14.0 AND longitude <= 24.5", name="ck_aeds_lng_bounds"),
        CheckConstraint("access_type IN ('public', 'customers_only', 'private')", name="ck_aeds_access_type"),
        CheckConstraint("status IN ('operational', 'out_of_service', 'unverified')", name="ck_aeds_status"),
        CheckConstraint("completeness_score >= 0 AND completeness_score <= 100", name="ck_aeds_completeness"),
        Index("idx_aeds_lat_lng", "latitude", "longitude"),
        Index("idx_aeds_city", "city"),
        Index("idx_aeds_filters", "status", "access_type", "is_24_7", "indoor"),
        Index("idx_aeds_completeness", "completeness_score"),
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    records_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_valid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_merged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_ingestion_runs_status"),
        Index("idx_ingestion_runs_source_started", "source_name", "started_at"),
    )


class AEDSourceRecord(Base):
    __tablename__ = "aed_source_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("aeds.id", ondelete="CASCADE"), nullable=False
    )
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True
    )
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_trust_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    aed: Mapped["AED"] = relationship(back_populates="source_records")

    __table_args__ = (
        UniqueConstraint("source_name", "external_id", name="uq_source_external"),
        CheckConstraint("source_trust_tier >= 1 AND source_trust_tier <= 3", name="ck_source_trust_tier"),
        Index("idx_source_records_aed_id", "aed_id"),
        Index("idx_source_records_source_name", "source_name"),
    )


class AEDVerification(Base):
    __tablename__ = "aed_verifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("aeds.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    reporter_org: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    aed: Mapped["AED"] = relationship(back_populates="verifications")

    __table_args__ = (
        CheckConstraint(
            "action IN ('confirm_operational', 'report_out_of_service', 'report_missing')",
            name="ck_aed_verifications_action",
        ),
        Index("idx_aed_verifications_aed_id", "aed_id", "created_at"),
    )
