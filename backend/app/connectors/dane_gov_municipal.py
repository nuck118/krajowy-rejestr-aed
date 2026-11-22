import asyncio
import csv
import io
import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from app.connectors.base import BaseConnector, FetchResult
from app.core.constants import (
    POLAND_LAT_MAX,
    POLAND_LAT_MIN,
    POLAND_LNG_MAX,
    POLAND_LNG_MIN,
)
from app.schemas.aed import AEDIngestCandidate
from app.services.deduplication import RawRecord

POSTCODE_RE = re.compile(r"\b(\d{2}-\d{3})\b")

LEGIONOWO_CSV_URL = "https://api.dane.gov.pl/media/resources/20260914/aed.csv"
KROSNO_CSV_URL = "https://api.dane.gov.pl/media/resources/20240219/Defibrylator_jAmxQcp.csv"
MARKI_CSV_URL = "https://api.dane.gov.pl/media/resources/20250710/Defibrylator_GminaMiastoMarki_1.csv"
PRZEMYSL_GEOJSON_URL = "https://przemysl.skycms.com.pl/open-data/20/1730818801_b50R6UVxPgoVdBbq/geojson"

CANONICAL_DANE_GOV_RESOURCES: list[dict[str, Any]] = [
    {
        "id": "legionowo-aed-csv",
        "title": "Lokalizacja urządzeń AED na terenie Gminy Miejskiej Legionowo",
        "institution": "Urząd Miasta Legionowo",
        "format": "CSV",
        "openness_score": 3,
        "download_url": LEGIONOWO_CSV_URL,
        "teryt_code": "1408011",
    },
    {
        "id": "krosno-aed-csv",
        "title": "Wykaz lokalizacji defibrylatorów AED w Mieście Krosno",
        "institution": "Urząd Miasta Krosna",
        "format": "CSV",
        "openness_score": 3,
        "download_url": KROSNO_CSV_URL,
        "teryt_code": "1861011",
    },
    {
        "id": "marki-aed-csv",
        "title": "Lokalizacja defibrylatorów AED - Gmina Miasto Marki",
        "institution": "Urząd Miasta Marki",
        "format": "CSV",
        "openness_score": 3,
        "download_url": MARKI_CSV_URL,
        "teryt_code": "1434021",
    },
    {
        "id": "przemysl-aed-geojson",
        "title": "Rozmieszczenie defibrylatorów AED w Przemyślu (GeoJSON)",
        "institution": "Urząd Miejski w Przemyślu",
        "format": "GeoJSON",
        "openness_score": 3,
        "download_url": PRZEMYSL_GEOJSON_URL,
        "teryt_code": "1862011",
    },
]


async def discover_dane_gov_aed_resources(
    *,
    api_base_url: str = "https://api.dane.gov.pl/1.4",
    query: str = "AED",
    live_probe: bool = False,
) -> dict[str, Any]:
    """
    Queries the dane.gov.pl Falcon JSON:API v1.4 (`/1.4/search` / `/1.4/datasets`)
    to dynamically discover municipal AED datasets and resources, merging any newly
    published CSV/GeoJSON feeds with the canonical municipal baseline.
    """
    discovered: list[dict[str, Any]] = [dict(item) for item in CANONICAL_DANE_GOV_RESOURCES]
    known_urls = {item["download_url"] for item in discovered}
    live_queried = False
    live_added = 0

    if live_probe:
        headers = {
            "User-Agent": "KrajowyRejestrAED/1.0 (dane.gov.pl)",
            "Accept": "application/vnd.api+json",
            "X-API-Version": "1.4",
        }
        search_url = f"{api_base_url.rstrip('/')}/search"
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(
                    search_url,
                    params={"q": query, "model[terms]": "resource", "per_page": 25},
                )
                if resp.status_code == 200:
                    live_queried = True
                    payload = resp.json()
                    for node in payload.get("data") or []:
                        attrs = node.get("attributes") or {}
                        dl_url = (
                            attrs.get("csv_file_url")
                            or attrs.get("file_url")
                            or attrs.get("download_url")
                            or attrs.get("link")
                        )
                        fmt = str(attrs.get("format") or "").upper()
                        if dl_url and dl_url not in known_urls and fmt in ("CSV", "GEOJSON", "JSON"):
                            known_urls.add(dl_url)
                            discovered.append(
                                {
                                    "id": str(node.get("id") or f"dane-gov-{len(discovered)+1}"),
                                    "title": str(attrs.get("title") or "Zasób AED dane.gov.pl"),
                                    "institution": "Portal Otwartych Danych dane.gov.pl",
                                    "format": fmt,
                                    "openness_score": int(attrs.get("openness_score") or 3),
                                    "download_url": dl_url,
                                    "teryt_code": None,
                                }
                            )
                            live_added += 1
        except Exception:
            live_queried = False

    return {
        "api_version": "1.4",
        "query": query,
        "live_api_queried": live_queried,
        "live_resources_added": live_added,
        "total_resources": len(discovered),
        "resources": discovered,
    }


def _orient_poland_lat_lng(val_a: float, val_b: float) -> tuple[float, float] | None:
    if (
        POLAND_LAT_MIN <= val_a <= POLAND_LAT_MAX
        and POLAND_LNG_MIN <= val_b <= POLAND_LNG_MAX
    ):
        return val_a, val_b
    if (
        POLAND_LAT_MIN <= val_b <= POLAND_LAT_MAX
        and POLAND_LNG_MIN <= val_a <= POLAND_LNG_MAX
    ):
        return val_b, val_a
    return None


def _extract_postcode(text: str | None) -> str | None:
    if not text:
        return None
    m = POSTCODE_RE.search(text)
    return m.group(1) if m else None


def _clean_address_without_city_postcode(raw_addr: str | None, city: str) -> str | None:
    if not raw_addr:
        return None
    cleaned = POSTCODE_RE.sub("", raw_addr)
    cleaned = re.sub(rf"\b{re.escape(city)}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("..", ".").strip(" ,")
    return cleaned or None


class DaneGovMunicipalConnector(BaseConnector):
    source_name = "dane_gov_municipal"

    async def fetch(self) -> FetchResult:
        headers = {"User-Agent": "KrajowyRejestrAED/1.0 (dane.gov.pl)"}
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            responses = await asyncio.gather(
                client.get(LEGIONOWO_CSV_URL),
                client.get(KROSNO_CSV_URL),
                client.get(MARKI_CSV_URL),
                client.get(PRZEMYSL_GEOJSON_URL),
                return_exceptions=True,
            )

        parsers = [
            self._parse_legionowo,
            self._parse_krosno,
            self._parse_marki,
            self._parse_przemysl,
        ]

        all_records: list[RawRecord] = []
        total_fetched = 0
        total_rejected = 0
        success_count = 0
        last_error: Exception | None = None

        for resp, parser in zip(responses, parsers, strict=True):
            if isinstance(resp, BaseException):
                last_error = resp if isinstance(resp, Exception) else Exception(str(resp))
                continue
            try:
                resp.raise_for_status()
                fetched, rejected, recs = parser(resp.content)
                total_fetched += fetched
                total_rejected += rejected
                all_records.extend(recs)
                success_count += 1
            except Exception as exc:
                last_error = exc

        if success_count == 0 and last_error is not None:
            raise last_error

        return FetchResult(
            fetched_count=total_fetched,
            rejected_count=total_rejected,
            records=all_records,
        )

    def _parse_legionowo(self, raw_bytes: bytes) -> tuple[int, int, list[RawRecord]]:
        text = raw_bytes.decode("utf-8-sig", errors="replace")
        rows = list(csv.DictReader(io.StringIO(text)))
        records: list[RawRecord] = []
        rejected = 0
        now = datetime.now(timezone.utc)

        for idx, row in enumerate(rows):
            try:
                lat = float(str(row.get("szerokosc_geograficzna", "")).strip())
                lng = float(str(row.get("dlugosc_geograficzna", "")).strip())
                oriented = _orient_poland_lat_lng(lat, lng)
                if oriented is None:
                    rejected += 1
                    continue
                lat, lng = oriented

                street_part = " ".join(
                    p for p in [
                        "ul." if (row.get("cecha_ulicy") or "").strip().lower() == "ulica" else (row.get("cecha_ulicy") or "").strip(),
                        (row.get("nazwa_ulicy") or "").strip(),
                        (row.get("nr_budynku") or "").strip(),
                    ] if p
                ).strip() or None

                simc = (row.get("kod_simc") or "").strip()
                teryt_code = simc if re.match(r"^\d{7}$", simc) else None
                postcode = (row.get("kod_pocztowy") or "").strip() or None

                candidate = AEDIngestCandidate(
                    latitude=lat,
                    longitude=lng,
                    street_address=street_part,
                    city=(row.get("miejscowosc") or "Legionowo").strip(),
                    postal_code=postcode,
                    teryt_code=teryt_code,
                    location_description=(row.get("nazwa") or "").strip() or None,
                    access_type="public",
                    status="operational",
                    last_verified_at=now,
                )
                records.append(
                    RawRecord(
                        source_name=self.source_name,
                        external_id=f"dane-gov:legionowo:{idx + 1}",
                        candidate=candidate,
                        raw_payload=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError):
                rejected += 1

        return len(rows), rejected, records

    def _parse_krosno(self, raw_bytes: bytes) -> tuple[int, int, list[RawRecord]]:
        text = raw_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = [
            {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k}
            for r in reader
        ]
        records: list[RawRecord] = []
        rejected = 0
        now = datetime.now(timezone.utc)

        for idx, row in enumerate(rows):
            try:
                raw_x = float(str(row.get("Długość geograficzna", "")).strip())
                raw_y = float(str(row.get("Szerokość geograficzna", "")).strip())
                oriented = _orient_poland_lat_lng(raw_y, raw_x)
                if oriented is None:
                    rejected += 1
                    continue
                lat, lng = oriented

                raw_addr = row.get("Adres")
                postcode = _extract_postcode(raw_addr)
                street = _clean_address_without_city_postcode(raw_addr, "Krosno")
                loc = row.get("Lokalizacja") or row.get("Nazwa")
                ext_num = row.get("Numer Id") or str(idx + 1)

                candidate = AEDIngestCandidate(
                    latitude=lat,
                    longitude=lng,
                    street_address=street,
                    city="Krosno",
                    postal_code=postcode,
                    location_description=loc,
                    access_type="public",
                    status="operational",
                    last_verified_at=now,
                )
                records.append(
                    RawRecord(
                        source_name=self.source_name,
                        external_id=f"dane-gov:krosno:{ext_num}",
                        candidate=candidate,
                        raw_payload=row,
                    )
                )
            except (TypeError, ValueError, ValidationError):
                rejected += 1

        return len(rows), rejected, records

    def _parse_marki(self, raw_bytes: bytes) -> tuple[int, int, list[RawRecord]]:
        text = raw_bytes.decode("utf-8-sig", errors="replace")
        unwrapped_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
                stripped = stripped[1:-1].replace('""', '"')
            unwrapped_lines.append(stripped)

        reader = csv.DictReader(io.StringIO("\n".join(unwrapped_lines)))
        rows = [
            {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k}
            for r in reader
        ]
        records: list[RawRecord] = []
        rejected = 0
        now = datetime.now(timezone.utc)

        for idx, row in enumerate(rows):
            try:
                raw_a = float(str(row.get("Długość geograficzna", "")).strip())
                raw_b = float(str(row.get("Szerokość geograficzna", "")).strip())
                oriented = _orient_poland_lat_lng(raw_a, raw_b)
                if oriented is None:
                    rejected += 1
                    continue
                lat, lng = oriented

                raw_addr = row.get("Adres")
                postcode = _extract_postcode(raw_addr)
                street = _clean_address_without_city_postcode(raw_addr, "Marki")
                loc = row.get("Lokalizacja") or row.get("Nazwa")
                ext_num = row.get("Numer Id") or str(idx + 1)

                candidate = AEDIngestCandidate(
                    latitude=lat,
                    longitude=lng,
                    street_address=street,
                    city="Marki",
                    postal_code=postcode,
                    location_description=loc,
                    access_type="public",
                    status="operational",
                    last_verified_at=now,
                )
                records.append(
                    RawRecord(
                        source_name=self.source_name,
                        external_id=f"dane-gov:marki:{ext_num}",
                        candidate=candidate,
                        raw_payload=row,
                    )
                )
            except (TypeError, ValueError, ValidationError):
                rejected += 1

        return len(rows), rejected, records

    def _parse_przemysl(self, raw_bytes: bytes) -> tuple[int, int, list[RawRecord]]:
        payload: dict[str, Any] = json.loads(raw_bytes.decode("utf-8-sig", errors="replace"))
        features = payload.get("features") or []
        records: list[RawRecord] = []
        rejected = 0
        now = datetime.now(timezone.utc)

        for idx, ft in enumerate(features):
            try:
                geom = ft.get("geometry") or {}
                coords = geom.get("coordinates") or []
                if geom.get("type") != "Point" or len(coords) < 2:
                    rejected += 1
                    continue
                oriented = _orient_poland_lat_lng(float(coords[1]), float(coords[0]))
                if oriented is None:
                    rejected += 1
                    continue
                lat, lng = oriented

                props = ft.get("properties") or {}
                street = " ".join(
                    p for p in [
                        str(props.get("street") or "").strip(),
                        str(props.get("home_number") or "").strip(),
                    ] if p
                ).strip() or None
                postcode = _extract_postcode(str(props.get("postcode") or ""))
                loc = str(props.get("name") or "").strip() or None
                ext_id = str(props.get("id") or (idx + 1))

                candidate = AEDIngestCandidate(
                    latitude=lat,
                    longitude=lng,
                    street_address=street,
                    city=str(props.get("city") or "Przemyśl").strip(),
                    postal_code=postcode,
                    location_description=loc,
                    access_type="public",
                    status="operational",
                    last_verified_at=now,
                )
                records.append(
                    RawRecord(
                        source_name=self.source_name,
                        external_id=f"dane-gov:przemysl:{ext_id}",
                        candidate=candidate,
                        raw_payload=ft,
                    )
                )
            except (TypeError, ValueError, ValidationError):
                rejected += 1

        return len(features), rejected, records
