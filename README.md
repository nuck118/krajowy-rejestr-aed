# Krajowy Rejestr AED // dane.gov.pl

National AED Open Data Hub unifying fragmented municipal, OpenStreetMap, and institutional defibrillator registries into a canonical Polish Open Data standard (`dane.gov.pl` 3★–4★ compliant).

## Architecture

- **Backend (`backend/`)**: Python, FastAPI, Pydantic v2, SQLAlchemy 2.0 + GeoAlchemy2, PostGIS (`GIST` spatial indexes, `ST_DWithin`, `ST_Distance`, `ST_AsGeoJSON`). Supports local zero-dependency async SQLite dev mode (`sqlite+aiosqlite:///backend/aed_registry.db`) when `DATABASE_URL` is omitted.
- **Data (`data/`)**:
  - `PL.geojson` — 18,291 real Polish AED GeoJSON nodes across Poland.
- **Ingestion Connectors**:
  - `pl_geojson` — National Polish GeoJSON registry (`data/PL.geojson`).
  - `osm_overpass` — Live OpenStreetMap Overpass API (`node/way["emergency"="defibrillator"]`) with 25 m spatial deduplication.
  - `POST /api/v1/ingest/upload` — Live JSON / GeoJSON ingestion endpoint for municipal/institutional datasets.
  - `POST /api/v1/aeds` — Validated direct institutional/citizen submissions with real-time 25 m spatial deduplication.
- **Frontend (`frontend/`)**: React 19, TypeScript, Vite, Tailwind CSS v4, MapLibre GL JS (Carto Positron monochrome base layer), Swiss civic-tech design system.

## Quickstart (Local Dev without Docker)

### 1. Backend
```bash
cd backend
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```
API docs: `http://127.0.0.1:8000/docs`

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
App URL: `http://localhost:5173`

## Quickstart (Docker + PostGIS)
```bash
docker compose up --build
```
To apply schema manually in Supabase / PostgreSQL: run `backend/sql/postgis_schema.sql`.

## `dane.gov.pl` Harvester Endpoints

| Endpoint | Standard | Headers |
| :--- | :--- | :--- |
| `GET /api/v1/export.geojson` | RFC 7946 GeoJSON | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |
| `GET /api/v1/export.csv` | UTF-8 BOM CSV | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |
| `GET /api/v1/export.jsonld` | DCAT-AP + `schema.org` JSON-LD | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |
