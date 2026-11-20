# Krajowy Rejestr AED (dane.gov.pl)

**[Wersja polska](#wersja-polska) | [English version](#english-version)**

---

## Wersja polska

**Krajowy Rejestr AED** to ogólnopolska platforma otwartych danych o automatycznych defibrylatorach zewnętrznych (AED), zaprojektowana dla Ministerstwa Cyfryzacji i portalu `dane.gov.pl`. System ujednolica rozproszone rejestry samorządowe, dane z OpenStreetMap oraz bezpośrednie zgłoszenia instytucji i obywateli w jeden kanoniczny standard danych otwartych (zgodny z 3 i 4 poziomem otwartości danych: GeoJSON RFC 7946, CSV UTF-8 z BOM oraz DCAT-AP / `schema.org` JSON-LD na licencji CC0-1.0).

### Architektura systemu

- **Backend i silnik walidacji (`backend/`)**:
  - Python 3.11+, **FastAPI**, **Pydantic v2** (automatyczna walidacja schematu i interaktywna dokumentacja OpenAPI 3.1 pod adresem `/docs`).
  - **PostgreSQL + PostGIS** (`SQLAlchemy 2.0` + `GeoAlchemy2`, indeksy przestrzenne `GIST`, zapytania `ST_DWithin`, `ST_Distance`, `ST_AsGeoJSON`). W środowisku lokalnym bez Dockera system automatycznie uruchamia asynchroniczną bazę SQLite (`backend/aed_registry.db`).
  - **Przestrzenna deduplikacja 25 m (`backend/app/services/deduplication.py`)**: Automatyczne łączenie rekordów znajdujących się w promieniu 25 metrów z zachowaniem pełnej historii pochodzenia w tabeli `aed_source_records`.
  - **Wskaźnik kompletności danych 0 do 100 (`backend/app/services/completeness.py`)**: Deterministyczna ocena jakości rekordu według 10 kryteriów (próg 60% dla minimalnego standardu `dane.gov.pl`, próg 80% dla pełnej zgodności).
  - **Wzbogacanie metadanych i geokodowanie odwrotne (`backend/app/services/metadata.py`, `backend/app/services/reverse_geocode.py`)**: Ekstrakcja atrybutów z surowych rekordów OpenStreetMap (`operator`, `level`, `phone`, `wheelchair`, `manufacturer`, `model`, `image_url`, `osm_url`) oraz automatyczne, zapisywane w bazie uzupełnianie brakujących adresów ulic, kodów pocztowych i nazw obiektów za pomocą OpenStreetMap Nominatim.
- **Prawdziwe źródła danych (brak danych testowych / mocków)**:
  - `pl_geojson` (`data/PL.geojson`): Bazowy ogólnopolski zbiór 18 291 rzeczywistych punktów AED na terenie Polski.
  - `dane_gov_municipal`: Oficjalne rejestry miejskie pobierane na żywo z portalu `dane.gov.pl` (UM Legionowo CSV, UM Krosno CSV, UM Marki CSV, UM Przemyśl GeoJSON).
  - `osm_overpass`: Synchronizacja na żywo z OpenStreetMap Overpass API (`emergency=defibrillator`) oraz OpenAEDMap dla wybranego obszaru.
  - `POST /api/v1/ingest/upload`: Endpoint do importu lokalnych plików JSON lub GeoJSON z rejestrów samorządowych i instytucjonalnych.
  - `POST /api/v1/aeds` oraz `POST /api/v1/aeds/{id}/verify`: Bezpośrednie zgłaszanie nowych defibrylatorów oraz terenowa weryfikacja sprawności i uzupełnianie dokładnego opisu miejsca montażu.
- **Frontend (`frontend/`)**:
  - **React 19**, **TypeScript**, **Vite**, **Tailwind CSS v4** oraz **MapLibre GL JS** (monochromatyczny podkład Carto Positron).
  - Wzorzec projektowy polskiej administracji publicznej (`gov.pl` / `Ministerstwo Cyfryzacji`), zgodność ze standardem dostępności **WCAG 2.1 AA/AAA** (przełącznik wysokiego kontrastu oraz skalowania tekstu `A / A+`).
  - Język polski jako domyślny z przełącznikiem `PL | EN`, oficjalne Godło Polski (`/godlo-polski.svg`) jako ikona karty przeglądarki oraz ikony PWA / Add-to-Home-Screen inspirowane oznakowaniem AED (`/apple-touch-icon.png`, `/aed-icon-192.png`, `/aed-icon-512.png`, `/manifest.webmanifest`).

### Szybki start (środowisko lokalne bez Dockera)

#### 1. Backend (FastAPI)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/seed.py
cd ..
backend/.venv/bin/uvicorn main:app --reload --port 8000
```
- Aplikacja i API: `http://127.0.0.1:8000`
- Dokumentacja OpenAPI (Swagger UI): `http://127.0.0.1:8000/docs`

#### 2. Frontend (tryb deweloperski Vite)
```bash
cd frontend
npm install
npm run dev
```
- Serwer deweloperski Vite: `http://127.0.0.1:5173`
- Budowanie wersji produkcyjnej SPA (serwowanej również bezpośrednio przez FastAPI z katalogu `frontend/dist`):
```bash
cd frontend
npm run build
```

#### 3. Testy automatyczne
```bash
backend/.venv/bin/pytest backend/tests -v
```

### Uruchomienie z Docker Compose i PostGIS
```bash
docker compose up --build
```
Aby ręcznie utworzyć schemat w bazie Supabase lub zewnętrznym PostgreSQL z rozszerzeniem PostGIS, wykonaj skrypt `backend/sql/postgis_schema.sql`.

### Wdrożenie w FastAPI Cloud

Główny plik `pyproject.toml` zawiera jawną konfigurację odkrywania pakietu (`package-dir = {"" = "backend"}`, `where = ["backend"]`, `include = ["app*"]`) oraz punkt wejścia `[tool.fastapi] entrypoint = "app.main:app"`, dzięki czemu budowanie pakietu w FastAPI Cloud przebiega bez konfliktów między katalogami `backend/`, `frontend/` i `data/`.

- **Wdrożenie z poziomu CLI (API + zbudowany frontend SPA oraz zbiór `data/PL.geojson` dzięki `.fastapicloudignore`)**:
```bash
cd frontend && npm run build && cd ..
backend/.venv/bin/fastapi cloud login
backend/.venv/bin/fastapi deploy
```
- **Wdrożenie przez integrację GitHub**: FastAPI Cloud automatycznie instaluje pakiet `app` z `pyproject.toml` i uruchamia `app.main:app` (przy pierwszym starcie baza danych jest automatycznie zasilana danymi z `data/PL.geojson` oraz `dane.gov.pl`).

### Punkty końcowe REST API i harvestera `dane.gov.pl`

| Punkt końcowy | Opis i standard | Nagłówki otwartych danych |
| :--- | :--- | :--- |
| `GET /api/v1/aeds` | Lista AED z filtrowaniem (`city`, `q`, `access_type`, `indoor`, `is_24_7`, `open_now`, `min_completeness`, `bbox`, `lat`, `lng`, `radius`) | `application/json` |
| `GET /api/v1/aeds/nearest` | Wyszukiwanie przestrzenne najbliższych AED z dystansem w metrach i czasem dojścia pieszo | `application/json` |
| `GET /api/v1/aeds/{id}` | Karta ewidencyjna AED, historia pochodzenia, metadane OSM oraz geokodowanie odwrotne Nominatim | `application/json` |
| `POST /api/v1/aeds` | Zgłoszenie nowego punktu AED z automatyczną deduplikacją przestrzenną w promieniu 25 m | `application/json` |
| `POST /api/v1/aeds/{id}/verify` | Weryfikacja terenowa statusu urządzenia oraz aktualizacja dokładnego opisu lokalizacji | `application/json` |
| `POST /api/v1/ingest/run` | Uruchomienie synchronizacji wybranego źródła (`dane_gov_municipal`, `pl_geojson`, `osm_overpass`) | `application/json` |
| `POST /api/v1/ingest/upload` | Import i harmonizacja zewnętrznego zbioru JSON lub GeoJSON | `application/json` |
| `GET /api/v1/stats` | Statystyki krajowego rejestru i tabela uzgadniania źródeł danych | `application/json` |
| `GET /api/v1/export.geojson` | Krajowy eksport GeoJSON (`FeatureCollection`, RFC 7946, EPSG:4326) | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |
| `GET /api/v1/export.csv` | Krajowy eksport tabelaryczny CSV (UTF-8 z BOM, RFC 4180) | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |
| `GET /api/v1/export.jsonld` | Katalog powiązanych danych semantycznych DCAT-AP + `schema.org` JSON-LD | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |

---

## English version

**Krajowy Rejestr AED** (National AED Open Data Hub) is a national civic-tech platform created for Poland's Ministry of Digitization (`Ministerstwo Cyfryzacji` / `dane.gov.pl`). It unifies fragmented municipal open data feeds, OpenStreetMap defibrillator nodes, and institutional/citizen submissions into a single canonical Polish Open Data standard served via a public REST API and an institutional `gov.pl` emergency-grade web portal.

### System Architecture

- **Backend & Validation Engine (`backend/`)**:
  - Python 3.11+, **FastAPI**, **Pydantic v2** (strict canonical AED schema validation and live OpenAPI 3.1 documentation at `/docs`).
  - **PostgreSQL + PostGIS** (`SQLAlchemy 2.0` + `GeoAlchemy2`, `GIST` spatial indexes, `ST_DWithin`, `ST_Distance`, `ST_AsGeoJSON`), with automatic zero-dependency async SQLite fallback (`backend/aed_registry.db`) for local development.
  - **25 m Spatial Deduplication (`backend/app/services/deduplication.py`)**: Merges duplicate defibrillator records within a 25-meter radius while preserving multi-source provenance in `aed_source_records`.
  - **Deterministic 0 to 100 Completeness Rubric (`backend/app/services/completeness.py`)**: Evaluates 10 weighted quality criteria per record (60% minimum harvestable threshold, 80% full standard compliance).
  - **OSM Metadata Extraction & Live Reverse Geocoding (`backend/app/services/metadata.py`, `backend/app/services/reverse_geocode.py`)**: Surfaces raw OSM tags (`operator`, `level`, `phone`, `wheelchair`, `manufacturer`, `model`, `image_url`, `osm_url`) and resolves missing street addresses, postal codes, cities, and building names on demand via rate-limited, DB-cached OpenStreetMap Nominatim lookups.
- **Real Data Sources (Zero Mock Data)**:
  - `pl_geojson` (`data/PL.geojson`): 18,291 real Polish AED GeoJSON Point features across Poland.
  - `dane_gov_municipal`: Live official municipal registries harvested from `dane.gov.pl` (UM Legionowo CSV, UM Krosno CSV, UM Marki CSV, UM Przemyśl GeoJSON).
  - `osm_overpass`: Live OpenStreetMap Overpass API (`emergency=defibrillator`) and OpenAEDMap bounding-box synchronization.
  - `POST /api/v1/ingest/upload`: Direct JSON / GeoJSON dataset upload endpoint for municipal and institutional files.
  - `POST /api/v1/aeds` and `POST /api/v1/aeds/{id}/verify`: Validated AED submission and field verification with inline placement description enrichment.
- **Frontend (`frontend/`)**:
  - **React 19**, **TypeScript**, **Vite**, **Tailwind CSS v4**, and **MapLibre GL JS** (monochrome Carto Positron tiles).
  - Official Polish government institutional design (`gov.pl` / `Ministerstwo Cyfryzacji`), **WCAG 2.1 AA/AAA** high-contrast mode and text-size scaling (`A / A+`), Polish primary interface with live `PL | EN` language switcher, official Polish Coat of Arms (`/godlo-polski.svg`) browser tab favicon, and AED-inspired Add-to-Home-Screen PWA icons (`/apple-touch-icon.png`, `/aed-icon-192.png`, `/aed-icon-512.png`, `/manifest.webmanifest`).

### Quickstart (Local Dev without Docker)

#### 1. Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/seed.py
cd ..
backend/.venv/bin/uvicorn main:app --reload --port 8000
```
- Unified App & API: `http://127.0.0.1:8000`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

#### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
- Vite Dev Server: `http://127.0.0.1:5173`
- Build production SPA into `frontend/dist`:
```bash
cd frontend
npm run build
```

#### 3. Automated Tests
```bash
backend/.venv/bin/pytest backend/tests -v
```

### Quickstart (Docker Compose + PostGIS)
```bash
docker compose up --build
```
To apply the PostGIS schema manually in Supabase or PostgreSQL, execute `backend/sql/postgis_schema.sql`.

### FastAPI Cloud Deployment

The root `pyproject.toml` configures explicit setuptools package discovery (`package-dir = {"" = "backend"}`, `where = ["backend"]`, `include = ["app*"]`) and `[tool.fastapi] entrypoint = "app.main:app"`, preventing flat-layout discovery conflicts between `backend/`, `frontend/`, and `data/`.

- **CLI Deployment (bundles compiled `frontend/dist` and `data/PL.geojson` via `.fastapicloudignore`)**:
```bash
cd frontend && npm run build && cd ..
backend/.venv/bin/fastapi cloud login
backend/.venv/bin/fastapi deploy
```
- **GitHub Integration Deployment**: FastAPI Cloud builds the `app` package from the root `pyproject.toml` and starts `app.main:app`, automatically seeding an empty database from `data/PL.geojson` and `dane.gov.pl` municipal feeds on startup.
