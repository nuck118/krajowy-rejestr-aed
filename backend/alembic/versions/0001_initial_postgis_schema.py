"""Initial PostGIS and AED canonical schema

Revision ID: 0001
Revises:
Create Date: 2026-11-20 21:15:00.000000
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    geom_type = (
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
        if is_postgres
        else sa.Text()
    )
    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    op.create_table(
        "aeds",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("geom", geom_type, nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("street_address", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("postal_code", sa.String(length=6), nullable=True),
        sa.Column("teryt_code", sa.String(length=7), nullable=True),
        sa.Column("location_description", sa.Text(), nullable=True),
        sa.Column("access_type", sa.String(length=32), nullable=False, server_default="public"),
        sa.Column("opening_hours", sa.Text(), nullable=True),
        sa.Column("is_24_7", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("indoor", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unverified"),
        sa.Column("completeness_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("primary_source", sa.String(length=100), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("idx_aeds_lat_lng", "aeds", ["latitude", "longitude"])
    op.create_index("idx_aeds_city", "aeds", ["city"])
    op.create_index("idx_aeds_filters", "aeds", ["status", "access_type", "is_24_7", "indoor"])
    op.create_index("idx_aeds_completeness", "aeds", ["completeness_score"])

    if is_postgres:
        op.execute("CREATE INDEX idx_aeds_geom_gist ON aeds USING GIST (geom)")
        op.execute("CREATE INDEX idx_aeds_geog_gist ON aeds USING GIST ((geom::geography))")

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_valid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_merged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_ingestion_runs_source_started", "ingestion_runs", ["source_name", "started_at"])

    op.create_table(
        "aed_source_records",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("aed_id", sa.Uuid(as_uuid=True), sa.ForeignKey("aeds.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "ingestion_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("source_trust_tier", sa.SmallInteger(), nullable=False, server_default="2"),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("raw_payload", json_type, nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_name", "external_id", name="uq_source_external"),
    )
    op.create_index("idx_source_records_aed_id", "aed_source_records", ["aed_id"])
    op.create_index("idx_source_records_source_name", "aed_source_records", ["source_name"])

    op.create_table(
        "aed_verifications",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("aed_id", sa.Uuid(as_uuid=True), sa.ForeignKey("aeds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("reporter_org", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_aed_verifications_aed_id", "aed_verifications", ["aed_id", "created_at"])

    op.create_table(
        "aed_likes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("aed_id", sa.Uuid(as_uuid=True), sa.ForeignKey("aeds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_ident", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("aed_id", "user_ident", name="uq_aed_like_user"),
    )
    op.create_index("idx_aed_likes_aed_id", "aed_likes", ["aed_id"])
    op.create_index("idx_aed_likes_user_ident", "aed_likes", ["user_ident"])

    op.create_table(
        "dataset_likes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("dataset_ext_ident", sa.String(length=100), nullable=False),
        sa.Column("user_ident", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dataset_ext_ident", "user_ident", name="uq_dataset_like_user"),
    )
    op.create_index("idx_dataset_likes_ext_ident", "dataset_likes", ["dataset_ext_ident"])
    op.create_index("idx_dataset_likes_user_ident", "dataset_likes", ["user_ident"])


def downgrade() -> None:
    op.drop_table("dataset_likes")
    op.drop_table("aed_likes")
    op.drop_table("aed_verifications")
    op.drop_table("aed_source_records")
    op.drop_table("ingestion_runs")
    op.drop_table("aeds")
