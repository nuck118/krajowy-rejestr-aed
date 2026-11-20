-- Krajowy Rejestr AED — PostgreSQL 16 + PostGIS DDL
-- Runnable directly in Supabase SQL Editor or Docker PostGIS init.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Canonical Unified AED Registry
CREATE TABLE IF NOT EXISTS aeds (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    geom                 GEOMETRY(Point, 4326) NOT NULL,
    latitude             DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN 49.0 AND 55.0),
    longitude            DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN 14.0 AND 24.5),

    street_address       TEXT,
    city                 TEXT,
    postal_code          VARCHAR(6) CHECK (postal_code IS NULL OR postal_code ~ '^\d{2}-\d{3}$'),
    teryt_code           VARCHAR(7) CHECK (teryt_code IS NULL OR teryt_code ~ '^\d{7}$'),
    location_description TEXT,

    access_type          TEXT NOT NULL DEFAULT 'public'
                         CHECK (access_type IN ('public', 'customers_only', 'private')),
    opening_hours        TEXT,
    is_24_7              BOOLEAN NOT NULL DEFAULT FALSE,
    indoor               BOOLEAN,
    status               TEXT NOT NULL DEFAULT 'unverified'
                         CHECK (status IN ('operational', 'out_of_service', 'unverified')),

    completeness_score   SMALLINT NOT NULL DEFAULT 0
                         CHECK (completeness_score BETWEEN 0 AND 100),
    primary_source       TEXT NOT NULL,
    last_verified_at     TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Spatial indexes: planar GIST for bbox & ST_AsGeoJSON; geography GIST for meter-accurate ST_DWithin/ST_Distance
CREATE INDEX IF NOT EXISTS idx_aeds_geom_gist ON aeds USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_aeds_geog_gist ON aeds USING GIST ((geom::geography));

-- Attribute indexes
CREATE INDEX IF NOT EXISTS idx_aeds_lat_lng ON aeds (latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_aeds_city_lower ON aeds (lower(city));
CREATE INDEX IF NOT EXISTS idx_aeds_filters ON aeds (status, access_type, is_24_7, indoor);
CREATE INDEX IF NOT EXISTS idx_aeds_completeness ON aeds (completeness_score);

-- 2. Ingestion Run Telemetry
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name       TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    records_fetched   INTEGER NOT NULL DEFAULT 0,
    records_valid     INTEGER NOT NULL DEFAULT 0,
    records_rejected  INTEGER NOT NULL DEFAULT 0,
    records_inserted  INTEGER NOT NULL DEFAULT 0,
    duplicates_merged INTEGER NOT NULL DEFAULT 0,
    error_summary     TEXT,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_source_started ON ingestion_runs (source_name, started_at DESC);

-- 3. Multi-Source Provenance Table
CREATE TABLE IF NOT EXISTS aed_source_records (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aed_id            UUID NOT NULL REFERENCES aeds(id) ON DELETE CASCADE,
    ingestion_run_id  UUID REFERENCES ingestion_runs(id) ON DELETE SET NULL,
    source_name       TEXT NOT NULL,
    source_trust_tier SMALLINT NOT NULL DEFAULT 2 CHECK (source_trust_tier BETWEEN 1 AND 3),
    external_id       TEXT NOT NULL,
    raw_payload       JSONB NOT NULL,
    ingested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_source_external UNIQUE (source_name, external_id)
);

CREATE INDEX IF NOT EXISTS idx_source_records_aed_id ON aed_source_records (aed_id);
CREATE INDEX IF NOT EXISTS idx_source_records_source_name ON aed_source_records (source_name);

-- 4. Community & Institutional Verification Log
CREATE TABLE IF NOT EXISTS aed_verifications (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aed_id        UUID NOT NULL REFERENCES aeds(id) ON DELETE CASCADE,
    action        TEXT NOT NULL CHECK (action IN ('confirm_operational', 'report_out_of_service', 'report_missing')),
    reporter_org  TEXT,
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_aed_verifications_aed_id ON aed_verifications (aed_id, created_at DESC);
