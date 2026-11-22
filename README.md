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
  - `dane_gov_municipal`: Oficjalne rejestry miejskie pobierane na żywo z portalu `dane.gov.pl` (UM Legionowo CSV, UM Krosno CSV, UM Marki CSV, UM Przemyśl GeoJSON) oraz dynamiczne odkrywanie nowych zasobów poprzez `api.dane.gov.pl/1.4` (`GET /api/v1/ingest/discover-dane-gov`).
  - `osm_overpass`: Synchronizacja na żywo z OpenStreetMap Overpass API (`emergency=defibrillator`) oraz OpenAEDMap dla wybranego obszaru.
  - `POST /api/v1/ingest/upload`: Endpoint do importu lokalnych plików JSON lub GeoJSON z rejestrów samorządowych i instytucjonalnych.
  - `POST /api/v1/aeds` oraz `POST /api/v1/aeds/{id}/verify`: Bezpośrednie zgłaszanie nowych defibrylatorów oraz terenowa weryfikacja sprawności i uzupełnianie dokładnego opisu miejsca montażu.
- **Zgodność z kodem źródłowym `dane.gov.pl` (MCOD v2.63.0)**:
  - **Harvester XML `1.13` (`urn:otwarte-dane:harvester:1.13`) + suma kontrolna `.md5` (`backend/app/services/standard_xlsx.py`)**: Pełna zgodność z 5-etapowym potokiem walidacji `mcod/harvester/utils.py:validate_xml_url()` oraz schematem `xml_import_otwarte_dane_1_13.xsd` (obsługa zapytań `HEAD`, towarzyszący endpoint sumy kontrolnej `GET/HEAD /api/v1/harvester/dane-gov.md5` oraz endpoint diagnostyczny `GET /api/v1/harvester/validate`).
  - **Polski Profil `DCAT-AP-PL` (`https://api.dane.gov.pl/ns/dcatappl#`) i słowniki SKOS (`backend/app/api/v1/mcod.py`)**: Eksport katalogu RDF (`dcat:Catalog` -> `dcat:Dataset` -> `dcat:Distribution`) w 4 formatach (`JSON-LD`, `Turtle .ttl`, `RDF/XML .xml`, `N-Triples .nt`), atrybuty `dcatappl:opennessScore`, `dcatappl:regon`, słowniki URI Urzędu Publikacji UE (MDR), geometrie GeoSPARQL WKT (`gsp:asWKT`) oraz słowniki kontrolowane `/api/v1/vocab/openness-score` (`1-star`..`5-stars`) i `/api/v1/vocab/special-sign`.
  - **System polubień zbiorów i rekordów AED (`OTD-3096`..`OTD-3184`)**: Pola `likes_count` oraz `is_liked_by_current_user`, sortowanie `sort=-likes_count` / `sort=likes_count`, endpointy `POST/DELETE /api/v1/aeds/{id}/likes`, `POST/DELETE /api/v1/datasets/{id}/likes`, `/api/v1/auth/user/likes` oraz `/api/v1/auth/user/dashboard`.
  - **Potok Middleware MCOD v2.63.0, `SlowSQLMiddleware` i Prometheus (`OTD-3073`, `backend/app/core/mcod_middleware.py`)**: Automatyczne profilowanie zapytań SQL z logowaniem wolnych zapytań przekraczających `SLOW_SQL_THRESHOLD_SECONDS` (domyślnie `1.0 s`) w formacie JSON (`event_type: "slow_sql"`), metryki Prometheus (`GET /metrics`, `GET /api/v1/metrics`), negocjacja wersji API (`X-API-Version: 1.4`), negocjacja języka (`Content-Language: pl|en`), zliczanie wyświetleń i pobrań (`CounterMiddleware`), raport uszkodzonych linków (`GET /api/v1/reports/brokenlinks`) oraz punkt informacyjny DGA (`GET /api/v1/dga-aggregated`).
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

### Punkty końcowe REST API, MCOD v2.63.0 i harvestera `dane.gov.pl`

| Punkt końcowy | Opis i standard | Nagłówki otwartych danych / Format |
| :--- | :--- | :--- |
| `GET /api/v1/aeds` | Lista AED z filtrowaniem (`city`, `q`, `access_type`, `indoor`, `is_24_7`, `open_now`, `min_completeness`, `bbox`, `lat`, `lng`, `radius`) oraz sortowaniem (`sort=-likes_count`, `likes_count`) | `application/json`, `X-API-Version: 1.4` |
| `GET /api/v1/aeds/nearest` | Wyszukiwanie przestrzenne najbliższych AED z dystansem w metrach i czasem dojścia pieszo | `application/json` |
| `GET /api/v1/aeds/{id}` | Karta ewidencyjna AED, historia pochodzenia, metadane OSM, `likes_count` oraz geokodowanie odwrotne Nominatim | `application/json` |
| `POST /api/v1/aeds` | Zgłoszenie nowego punktu AED z automatyczną deduplikacją przestrzenną w promieniu 25 m | `application/json` |
| `POST /api/v1/aeds/{id}/verify` | Weryfikacja terenowa statusu urządzenia oraz aktualizacja dokładnego opisu lokalizacji | `application/json` |
| `POST / DELETE /api/v1/aeds/{id}/likes` | Dodanie / usunięcie polubienia punktu AED (`MCOD v2.63.0 OTD-3100..3101`) | `application/json` |
| `POST /api/v1/ingest/run` | Uruchomienie synchronizacji wybranego źródła (`dane_gov_municipal`, `pl_geojson`, `osm_overpass`) | `application/json` |
| `POST /api/v1/ingest/upload` | Import i harmonizacja zewnętrznego zbioru JSON lub GeoJSON | `application/json` |
| `GET /api/v1/ingest/discover-dane-gov` | Dynamiczne odkrywanie zasobów AED w portalu `api.dane.gov.pl/1.4` | `application/json` |
| `GET /api/v1/stats` | Statystyki krajowego rejestru i tabela uzgadniania źródeł danych | `application/json` |
| `GET /api/v1/export.geojson` | Krajowy eksport GeoJSON (`FeatureCollection`, RFC 7946, EPSG:4326) | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |
| `GET /api/v1/export.csv` | Krajowy eksport tabelaryczny CSV (UTF-8 z BOM, RFC 4180) | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |
| `GET /api/v1/export.jsonld` | Katalog powiązanych danych semantycznych `DCAT-AP-PL` + `schema.org` JSON-LD + GeoSPARQL | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |
| `GET /api/v1/standard.xlsx` | Wzorcowy zakres danych AED dla portalu `dane.gov.pl` i szablon dla dysponentów (`.xlsx`) | `ETag`, `X-Open-Data-License: CC0-1.0`, `Content-Disposition` |
| `GET / HEAD /api/v1/harvester/dane-gov.xml` | Katalog XML harvestera `dane.gov.pl` zgodny ze schematem XSD `urn:otwarte-dane:harvester:1.13` | `application/xml`, `ETag`, `X-Harvester-MD5` |
| `GET / HEAD /api/v1/harvester/dane-gov.md5` | Towarzyszący plik sumy kontrolnej MD5 wymagany przez harvester `dane.gov.pl` (`mcod/harvester/utils.py`) | `text/plain`, `ETag` |
| `GET /api/v1/harvester/validate` | 5-etapowa walidacja zgodności pliku XML i sumy MD5 ze schematem XSD `1.13` `dane.gov.pl` | `application/json` |
| `GET /api/v1/catalog` oraz `/api/v1/catalog.{jsonld,ttl,xml,nt}` | Katalog RDF w profilu narodowym `DCAT-AP-PL` (JSON-LD, Turtle, RDF/XML, N-Triples) | `application/ld+json`, `text/turtle`, `application/rdf+xml` |
| `GET /api/v1/vocab/openness-score` oraz `/api/v1/vocab/special-sign` | Słowniki kontrolowane SKOS poziomu otwartości (`1-star`..`5-stars`) i znaków umownych `dane.gov.pl` | `application/json` |
| `GET /api/v1/datasets` oraz `POST / DELETE /api/v1/datasets/{id}/likes` | Endpointy JSON:API v1.4 zbiorów danych, zasobów, liczników wyświetleń/pobrań oraz polubień (`OTD-3096`) | `application/json` |
| `GET /api/v1/auth/user/likes` oraz `/api/v1/auth/user/dashboard` | Lista polubionych zbiorów i urządzeń AED użytkownika (`OTD-3155`) | `application/json` |
| `GET /api/v1/reports/brokenlinks` oraz `/api/v1/dga-aggregated` | Raport dostępności źródeł zewnętrznych oraz punkt informacyjny Data Governance Act (DGA) | `application/json` |
| `GET /metrics`, `GET /api/v1/cluster/health`, `GET /ping` | Metryki Prometheus (`OTD-3073`), diagnostyka `SlowSQLMiddleware` oraz kontrola żywotności | `text/plain; version=0.0.4`, `application/json` |

### Licencje (Kod źródłowy oraz Otwarte Dane)

- **Kod źródłowy oprogramowania (`LICENSE` / `LICENCE.txt`)**: Zgodnie z wymogami otwartego kodu źródłowego systemu Otwarte Dane (`https://dane.gov.pl/source-code/`), kod źródłowy platformy udostępniany jest na licencji **GNU General Public License v3.0 (GPL-3.0)** opracowanej/zmodyfikowanej w zgodzie ze standardem KPRM / Ministerstwa Cyfryzacji.
- **Zbiory danych i eksporty API (`CC0 1.0 Universal`)**: Wszystkie ujednolicone dane o lokalizacji i dostępności defibrylatorów AED (`/api/v1/export.geojson`, `/api/v1/export.csv`, `/api/v1/export.jsonld`, `/api/v1/standard.xlsx`, `/api/v1/harvester/dane-gov.xml`) udostępniane są w domenie publicznej na licencji **Creative Commons CC0 1.0 Universal** (z zachowaniem atrybucji danych pochodzących z OpenStreetMap dla surowych rekordów OSM).

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
  - `dane_gov_municipal`: Live official municipal registries harvested from `dane.gov.pl` (UM Legionowo CSV, UM Krosno CSV, UM Marki CSV, UM Przemyśl GeoJSON) plus dynamic JSON:API v1.4 resource discovery (`GET /api/v1/ingest/discover-dane-gov`).
  - `osm_overpass`: Live OpenStreetMap Overpass API (`emergency=defibrillator`) and OpenAEDMap bounding-box synchronization.
  - `POST /api/v1/ingest/upload`: Direct JSON / GeoJSON dataset upload endpoint for municipal and institutional files.
  - `POST /api/v1/aeds` and `POST /api/v1/aeds/{id}/verify`: Validated AED submission and field verification with inline placement description enrichment.
- **`dane.gov.pl` (`MCOD` v2.63.0) Source Code Parity & Interoperability**:
  - **Harvester XML `1.13` (`urn:otwarte-dane:harvester:1.13`) + Companion `.md5` Checksum (`backend/app/services/standard_xlsx.py`)**: Implements all 5 verification steps required by `mcod/harvester/utils.py:validate_xml_url()` and `xml_import_otwarte_dane_1_13.xsd` (`HEAD` request support, `GET/HEAD /api/v1/harvester/dane-gov.md5` hex digest endpoint, and `GET /api/v1/harvester/validate`).
  - **Polish National `DCAT-AP-PL` RDF Profile (`https://api.dane.gov.pl/ns/dcatappl#`) & SKOS Vocabularies (`backend/app/api/v1/mcod.py`)**: Multi-format RDF catalog (`/api/v1/catalog` in JSON-LD, Turtle `.ttl`, RDF/XML `.xml`, and N-Triples `.nt`), `dcatappl:opennessScore`, `dcatappl:regon`, EU MDR authority URIs, GeoSPARQL WKT (`gsp:asWKT`), and SKOS controlled vocabulary endpoints (`/api/v1/vocab/openness-score` and `/api/v1/vocab/special-sign`).
  - **Dataset & AED Likes System (`OTD-3096`..`OTD-3184`)**: `likes_count`, `is_liked_by_current_user`, `sort=-likes_count` / `sort=likes_count`, `POST/DELETE /api/v1/aeds/{id}/likes`, `POST/DELETE /api/v1/datasets/{id}/likes`, `/api/v1/auth/user/likes`, and `/api/v1/auth/user/dashboard`.
  - **MCOD v2.63.0 Middleware Pipeline, `SlowSQLMiddleware` & Prometheus (`OTD-3073`, `backend/app/core/mcod_middleware.py`)**: Automatic SQLAlchemy query execution profiler logging queries above `SLOW_SQL_THRESHOLD_SECONDS` (default `1.0s`) as structured JSON (`event_type: "slow_sql"`), Prometheus metrics (`GET /metrics`, `GET /api/v1/metrics`), `X-API-Version: 1.4` and `Content-Language: pl|en` negotiation, view/download counters (`CounterMiddleware`), Broken Links report (`GET /api/v1/reports/brokenlinks`), and Data Governance Act information point (`GET /api/v1/dga-aggregated`).
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

### Licensing (Source Code & Open Data)

- **Source Code (`LICENSE` / `LICENCE.txt`)**: In accordance with the official Otwarte Dane (`https://dane.gov.pl/source-code/`) licensing policy, the software source code is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.
- **Open Data Feeds & Exports (`CC0 1.0 Universal`)**: All harmonized AED datasets and machine-readable exports (`/api/v1/export.geojson`, `/api/v1/export.csv`, `/api/v1/export.jsonld`, `/api/v1/standard.xlsx`, `/api/v1/harvester/dane-gov.xml`) are published under **Creative Commons CC0 1.0 Universal (Public Domain)**, preserving OpenStreetMap contributor attribution on raw OSM provenance records.
