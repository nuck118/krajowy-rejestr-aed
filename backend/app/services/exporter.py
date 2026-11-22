import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.core.config import settings
from app.db.models import AED
from app.services.completeness import completeness_tier, ensure_utc


def _build_export_clauses(city: str | None, min_completeness: int | None) -> list[Any]:
    clauses: list[Any] = []
    if city:
        clauses.append(func.lower(AED.city) == city.strip().lower())
    if min_completeness is not None:
        clauses.append(AED.completeness_score >= min_completeness)
    return clauses


async def compute_export_etag(
    session: AsyncSession,
    *,
    fmt: str,
    city: str | None = None,
    min_completeness: int | None = None,
    limit: int | None = None,
) -> str:
    clauses = _build_export_clauses(city, min_completeness)
    stmt = select(func.count(AED.id), func.max(AED.updated_at)).where(*clauses)
    count_val, max_updated = (await session.execute(stmt)).one()
    raw = f"{fmt}:{count_val}:{max_updated}:{city or ''}:{min_completeness or ''}:{limit or ''}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f'W/"{digest}"'


async def _fetch_export_rows(
    session: AsyncSession,
    *,
    city: str | None = None,
    min_completeness: int | None = None,
    limit: int | None = None,
) -> list[AED]:
    clauses = _build_export_clauses(city, min_completeness)
    stmt = (
        select(AED)
        .options(lazyload(AED.source_records))
        .where(*clauses)
        .order_by(AED.completeness_score.desc(), AED.id.asc())
    )
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def generate_geojson_bytes(
    session: AsyncSession,
    *,
    city: str | None = None,
    min_completeness: int | None = None,
    limit: int | None = None,
) -> bytes:
    clauses = _build_export_clauses(city, min_completeness)

    features: list[dict[str, Any]] = []
    if settings.use_postgis:
        stmt = (
            select(AED, func.ST_AsGeoJSON(AED.geom))
            .options(lazyload(AED.source_records))
            .where(*clauses)
            .order_by(AED.completeness_score.desc(), AED.id.asc())
        )
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).all()
        for aed, geom_json in rows:
            geometry = json.loads(geom_json)
            features.append(_aed_to_geojson_feature(aed, geometry))
    else:
        aeds = await _fetch_export_rows(
            session, city=city, min_completeness=min_completeness, limit=limit
        )
        for aed in aeds:
            geometry = {"type": "Point", "coordinates": [aed.longitude, aed.latitude]}
            features.append(_aed_to_geojson_feature(aed, geometry))

    collection = {
        "type": "FeatureCollection",
        "name": "Krajowy Rejestr AED (dane.gov.pl)",
        "license": "CC0-1.0",
        "standard": "dane.gov.pl-4-star",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_features": len(features),
        "features": features,
    }
    return json.dumps(collection, ensure_ascii=False).encode("utf-8")


def _aed_to_geojson_feature(aed: AED, geometry: dict[str, Any]) -> dict[str, Any]:
    verified = ensure_utc(aed.last_verified_at)
    updated = ensure_utc(aed.updated_at)
    return {
        "type": "Feature",
        "id": str(aed.id),
        "geometry": geometry,
        "properties": {
            "id": str(aed.id),
            "street_address": aed.street_address,
            "city": aed.city,
            "postal_code": aed.postal_code,
            "teryt_code": aed.teryt_code,
            "location_description": aed.location_description,
            "access_type": aed.access_type,
            "opening_hours": aed.opening_hours,
            "is_24_7": aed.is_24_7,
            "indoor": aed.indoor,
            "status": aed.status,
            "completeness_score": aed.completeness_score,
            "completeness_tier": completeness_tier(aed.completeness_score),
            "primary_source": aed.primary_source,
            "last_verified_at": verified.isoformat() if verified else None,
            "updated_at": updated.isoformat() if updated else None,
        },
    }


async def generate_csv_bytes(
    session: AsyncSession,
    *,
    city: str | None = None,
    min_completeness: int | None = None,
    limit: int | None = None,
) -> bytes:
    aeds = await _fetch_export_rows(
        session, city=city, min_completeness=min_completeness, limit=limit
    )
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "id",
            "latitude",
            "longitude",
            "street_address",
            "city",
            "postal_code",
            "teryt_code",
            "location_description",
            "access_type",
            "opening_hours",
            "is_24_7",
            "indoor",
            "status",
            "completeness_score",
            "primary_source",
            "last_verified_at",
            "updated_at",
        ]
    )
    for aed in aeds:
        verified = ensure_utc(aed.last_verified_at)
        updated = ensure_utc(aed.updated_at)
        writer.writerow(
            [
                str(aed.id),
                aed.latitude,
                aed.longitude,
                aed.street_address or "",
                aed.city or "",
                aed.postal_code or "",
                aed.teryt_code or "",
                aed.location_description or "",
                aed.access_type,
                aed.opening_hours or "",
                str(aed.is_24_7).lower(),
                "" if aed.indoor is None else str(aed.indoor).lower(),
                aed.status,
                aed.completeness_score,
                aed.primary_source,
                verified.isoformat() if verified else "",
                updated.isoformat() if updated else "",
            ]
        )

    # UTF-8 with BOM for Excel & Polish administrative tooling compatibility
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


async def generate_jsonld_bytes(
    session: AsyncSession,
    *,
    base_url: str,
    city: str | None = None,
    min_completeness: int | None = None,
    limit: int | None = None,
) -> bytes:
    aeds = await _fetch_export_rows(
        session, city=city, min_completeness=min_completeness, limit=limit
    )
    clean_base = base_url.rstrip("/")
    generated_iso = datetime.now(timezone.utc).isoformat()
    vocab_base = f"{clean_base}/api/v1/vocab/openness-score"

    def _openness_concept(stars: int, label_pl: str, label_en: str) -> dict[str, Any]:
        ident = "1-star" if stars == 1 else f"{stars}-stars"
        return {
            "@id": f"{vocab_base}/{ident}",
            "@type": "skos:Concept",
            "skos:inScheme": {
                "@id": vocab_base,
                "dct:title": [
                    {"@value": "Poziom otwartości", "@language": "pl"},
                    {"@value": "Openness score", "@language": "en"},
                ],
            },
            "skos:prefLabel": [
                {"@value": label_pl, "@language": "pl"},
                {"@value": label_en, "@language": "en"},
            ],
            "skos:notation": "*" * stars,
        }

    graph: list[dict[str, Any]] = [
        {
            "@id": f"{clean_base}/api/v1/export.jsonld#dataset",
            "@type": "dcat:Dataset",
            "dct:identifier": "krajowy-rejestr-aed-polska",
            "dct:title": "Krajowy Rejestr AED — National Automated External Defibrillator Registry",
            "dct:description": (
                "Unified Polish national registry of Automated External Defibrillators (AED) "
                "harmonized from municipal registries, OpenStreetMap, and verified institutional submissions."
            ),
            "dct:license": "https://creativecommons.org/publicdomain/zero/1.0/",
            "dct:issued": generated_iso,
            "dct:modified": generated_iso,
            "dct:language": "http://publications.europa.eu/resource/authority/language/POL",
            "dct:accrualPeriodicity": "http://publications.europa.eu/resource/authority/frequency/DAILY",
            "dct:spatial": "http://publications.europa.eu/resource/authority/country/POL",
            "dcat:theme": [
                "http://publications.europa.eu/resource/authority/data-theme/HEAL",
                "http://publications.europa.eu/resource/authority/data-theme/GOVE",
                "http://publications.europa.eu/resource/authority/data-theme/REGI",
            ],
            "dct:publisher": {
                "@type": "foaf:Organization",
                "foaf:name": "Ministry of Digitization — dane.gov.pl Open Data Hub",
                "dcatappl:regon": settings.INSTITUTION_REGON,
            },
            "dcat:distribution": [
                {
                    "@type": "dcat:Distribution",
                    "dcat:accessURL": f"{clean_base}/api/v1/export.geojson",
                    "dcat:downloadURL": f"{clean_base}/api/v1/export.geojson",
                    "dct:format": "http://publications.europa.eu/resource/authority/file-type/GEOJSON",
                    "dcat:mediaType": "application/geo+json",
                    "dct:license": "https://creativecommons.org/publicdomain/zero/1.0/",
                    "dcatappl:opennessScore": _openness_concept(3, "3 gwiazdki", "3 stars"),
                },
                {
                    "@type": "dcat:Distribution",
                    "dcat:accessURL": f"{clean_base}/api/v1/export.csv",
                    "dcat:downloadURL": f"{clean_base}/api/v1/export.csv",
                    "dct:format": "http://publications.europa.eu/resource/authority/file-type/CSV",
                    "dcat:mediaType": "text/csv",
                    "dct:license": "https://creativecommons.org/publicdomain/zero/1.0/",
                    "dcatappl:opennessScore": _openness_concept(3, "3 gwiazdki", "3 stars"),
                },
                {
                    "@type": "dcat:Distribution",
                    "dcat:accessURL": f"{clean_base}/api/v1/export.jsonld",
                    "dcat:downloadURL": f"{clean_base}/api/v1/export.jsonld",
                    "dct:format": "http://publications.europa.eu/resource/authority/file-type/JSON_LD",
                    "dcat:mediaType": "application/ld+json",
                    "dct:license": "https://creativecommons.org/publicdomain/zero/1.0/",
                    "dcatappl:opennessScore": _openness_concept(4, "4 gwiazdki", "4 stars"),
                },
                {
                    "@type": "dcat:Distribution",
                    "dcat:accessURL": f"{clean_base}/api/v1/standard.xlsx",
                    "dcat:downloadURL": f"{clean_base}/api/v1/standard.xlsx",
                    "dct:format": "http://publications.europa.eu/resource/authority/file-type/XLSX",
                    "dcat:mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "dct:license": "https://creativecommons.org/publicdomain/zero/1.0/",
                    "dcatappl:opennessScore": _openness_concept(3, "3 gwiazdki", "3 stars"),
                },
            ],
        }
    ]

    for aed in aeds:
        verified = ensure_utc(aed.last_verified_at)
        node: dict[str, Any] = {
            "@id": f"{clean_base}/api/v1/aeds/{aed.id}",
            "@type": ["schema:Place", "schema:EmergencyService"],
            "schema:identifier": str(aed.id),
            "schema:name": aed.location_description or "Automated External Defibrillator (AED)",
            "schema:description": aed.location_description,
            "schema:geo": {
                "@type": "schema:GeoCoordinates",
                "schema:latitude": aed.latitude,
                "schema:longitude": aed.longitude,
            },
            "locn:geometry": {
                "@type": "gsp:Geometry",
                "gsp:asWKT": f"POINT({aed.longitude} {aed.latitude})",
            },
            "schema:address": {
                "@type": "schema:PostalAddress",
                "schema:streetAddress": aed.street_address,
                "schema:addressLocality": aed.city,
                "schema:postalCode": aed.postal_code,
                "schema:addressCountry": "PL",
            },
            "schema:openingHours": aed.opening_hours,
            "aed:accessType": aed.access_type,
            "aed:is24x7": aed.is_24_7,
            "aed:indoor": aed.indoor,
            "aed:status": aed.status,
            "aed:completenessScore": aed.completeness_score,
            "aed:primarySource": aed.primary_source,
            "aed:terytCode": aed.teryt_code,
            "aed:lastVerifiedAt": verified.isoformat() if verified else None,
        }
        graph.append(node)

    doc = {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
            "foaf": "http://xmlns.com/foaf/0.1/",
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "vcard": "http://www.w3.org/2006/vcard/ns#",
            "locn": "http://www.w3.org/ns/locn#",
            "gsp": "http://www.opengis.net/ont/geosparql#",
            "dcatappl": "https://api.dane.gov.pl/ns/dcatappl#",
            "schema": "https://schema.org/",
            "aed": "https://dane.gov.pl/vocab/aed#",
        },
        "@graph": graph,
    }
    return json.dumps(doc, ensure_ascii=False).encode("utf-8")


def generate_dcat_ap_pl_catalog_rdf(
    *,
    base_url: str,
    total_records: int,
    updated_iso: str,
    rdf_format: str = "jsonld",
) -> tuple[bytes, str]:
    """
    Serializes the DCAT-AP-PL Catalog (`dcat:Catalog` -> `dcat:Dataset` -> `dcat:Distribution`)
    into JSON-LD, Turtle (`ttl`), RDF/XML (`xml`), or N-Triples (`nt`), matching
    dane.gov.pl's `mcod/core/api/rdf/profiles/dcat_ap_pl.py` & `CatalogRDFView`.
    """
    clean_base = base_url.rstrip("/")
    catalog_uri = f"{clean_base}/api/v1/catalog"
    dataset_uri = f"{clean_base}/api/v1/catalog/dataset/1"
    vocab_uri = f"{clean_base}/api/v1/vocab/openness-score"
    fmt = rdf_format.lower().strip(".")

    if fmt in ("ttl", "turtle"):
        ttl = f"""@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcatappl: <https://api.dane.gov.pl/ns/dcatappl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<{catalog_uri}> a dcat:Catalog ;
    dct:title "Krajowy Rejestr AED - Katalog Otwartych Danych"@pl,
        "National AED Registry - Open Data Catalog"@en ;
    dct:description "Katalog DCAT-AP-PL defibrylatorów AED ({total_records} rekordów)"@pl ;
    dct:modified "{updated_iso}"^^xsd:dateTime ;
    foaf:homepage <{clean_base}> ;
    dct:language <http://publications.europa.eu/resource/authority/language/POL> ;
    dct:spatial <http://publications.europa.eu/resource/authority/country/POL> ;
    dct:publisher [ a foaf:Organization ;
        foaf:name "Ministerstwo Cyfryzacji - dane.gov.pl"@pl ;
        dcatappl:regon "{settings.INSTITUTION_REGON}"
    ] ;
    dcat:dataset <{dataset_uri}> .

<{dataset_uri}> a dcat:Dataset ;
    dct:identifier "krajowy-rejestr-aed-polska" ;
    dct:title "Krajowy Rejestr AED - Ogólnopolski Wykaz Automatycznych Defibrylatorów Zewnętrznych"@pl,
        "National AED Registry - Unified Polish Automated External Defibrillator Open Data Hub"@en ;
    dct:description "Zharmonizowany rejestr {total_records} punktów AED z deduplikacją przestrzenną 25 m"@pl ;
    dct:modified "{updated_iso}"^^xsd:dateTime ;
    dct:accrualPeriodicity <http://publications.europa.eu/resource/authority/frequency/DAILY> ;
    dct:language <http://publications.europa.eu/resource/authority/language/POL> ;
    dct:spatial <http://publications.europa.eu/resource/authority/country/POL> ;
    dcat:theme <http://publications.europa.eu/resource/authority/data-theme/HEAL>,
        <http://publications.europa.eu/resource/authority/data-theme/GOVE>,
        <http://publications.europa.eu/resource/authority/data-theme/REGI> ;
    dcat:distribution <{dataset_uri}/resource/geojson>,
        <{dataset_uri}/resource/csv>,
        <{dataset_uri}/resource/jsonld>,
        <{dataset_uri}/resource/xlsx> .

<{dataset_uri}/resource/geojson> a dcat:Distribution ;
    dct:title "Krajowy wykaz geoprzestrzenny AED (GeoJSON)"@pl ;
    dcat:accessURL <{clean_base}/api/v1/export.geojson> ;
    dcat:downloadURL <{clean_base}/api/v1/export.geojson> ;
    dct:format <http://publications.europa.eu/resource/authority/file-type/GEOJSON> ;
    dcat:mediaType "application/geo+json" ;
    dct:license <https://creativecommons.org/publicdomain/zero/1.0/> ;
    dcatappl:opennessScore <{vocab_uri}/3-stars> .

<{dataset_uri}/resource/csv> a dcat:Distribution ;
    dct:title "Tabela krajowego rejestru AED (CSV)"@pl ;
    dcat:accessURL <{clean_base}/api/v1/export.csv> ;
    dcat:downloadURL <{clean_base}/api/v1/export.csv> ;
    dct:format <http://publications.europa.eu/resource/authority/file-type/CSV> ;
    dcat:mediaType "text/csv" ;
    dct:license <https://creativecommons.org/publicdomain/zero/1.0/> ;
    dcatappl:opennessScore <{vocab_uri}/3-stars> .

<{dataset_uri}/resource/jsonld> a dcat:Distribution ;
    dct:title "Katalog semantyczny Linked Open Data AED (DCAT-AP-PL JSON-LD)"@pl ;
    dcat:accessURL <{clean_base}/api/v1/export.jsonld> ;
    dcat:downloadURL <{clean_base}/api/v1/export.jsonld> ;
    dct:format <http://publications.europa.eu/resource/authority/file-type/JSON_LD> ;
    dcat:mediaType "application/ld+json" ;
    dct:license <https://creativecommons.org/publicdomain/zero/1.0/> ;
    dcatappl:opennessScore <{vocab_uri}/4-stars> .

<{dataset_uri}/resource/xlsx> a dcat:Distribution ;
    dct:title "Wzorcowy zakres danych AED (XLSX)"@pl ;
    dcat:accessURL <{clean_base}/api/v1/standard.xlsx> ;
    dcat:downloadURL <{clean_base}/api/v1/standard.xlsx> ;
    dct:format <http://publications.europa.eu/resource/authority/file-type/XLSX> ;
    dcat:mediaType "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ;
    dct:license <https://creativecommons.org/publicdomain/zero/1.0/> ;
    dcatappl:opennessScore <{vocab_uri}/3-stars> .
"""
        return ttl.encode("utf-8"), "text/turtle; charset=utf-8"

    if fmt in ("xml", "rdf"):
        rdf_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcat="http://www.w3.org/ns/dcat#"
  xmlns:dct="http://purl.org/dc/terms/"
  xmlns:foaf="http://xmlns.com/foaf/0.1/"
  xmlns:skos="http://www.w3.org/2004/02/skos/core#"
  xmlns:dcatappl="https://api.dane.gov.pl/ns/dcatappl#">
  <dcat:Catalog rdf:about="{catalog_uri}">
    <dct:title xml:lang="pl">Krajowy Rejestr AED - Katalog Otwartych Danych</dct:title>
    <dct:title xml:lang="en">National AED Registry - Open Data Catalog</dct:title>
    <dct:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">{updated_iso}</dct:modified>
    <dct:language rdf:resource="http://publications.europa.eu/resource/authority/language/POL"/>
    <dct:spatial rdf:resource="http://publications.europa.eu/resource/authority/country/POL"/>
    <dct:publisher>
      <foaf:Organization>
        <foaf:name xml:lang="pl">Ministerstwo Cyfryzacji - dane.gov.pl</foaf:name>
        <dcatappl:regon>{settings.INSTITUTION_REGON}</dcatappl:regon>
      </foaf:Organization>
    </dct:publisher>
    <dcat:dataset>
      <dcat:Dataset rdf:about="{dataset_uri}">
        <dct:identifier>krajowy-rejestr-aed-polska</dct:identifier>
        <dct:title xml:lang="pl">Krajowy Rejestr AED - Ogólnopolski Wykaz Automatycznych Defibrylatorów Zewnętrznych</dct:title>
        <dct:title xml:lang="en">National AED Registry - Unified Polish Automated External Defibrillator Open Data Hub</dct:title>
        <dct:accrualPeriodicity rdf:resource="http://publications.europa.eu/resource/authority/frequency/DAILY"/>
        <dcat:theme rdf:resource="http://publications.europa.eu/resource/authority/data-theme/HEAL"/>
        <dcat:theme rdf:resource="http://publications.europa.eu/resource/authority/data-theme/GOVE"/>
        <dcat:theme rdf:resource="http://publications.europa.eu/resource/authority/data-theme/REGI"/>
        <dcat:distribution>
          <dcat:Distribution rdf:about="{dataset_uri}/resource/geojson">
            <dct:title xml:lang="pl">Krajowy wykaz geoprzestrzenny AED (GeoJSON)</dct:title>
            <dcat:accessURL rdf:resource="{clean_base}/api/v1/export.geojson"/>
            <dct:format rdf:resource="http://publications.europa.eu/resource/authority/file-type/GEOJSON"/>
            <dcatappl:opennessScore rdf:resource="{vocab_uri}/3-stars"/>
          </dcat:Distribution>
        </dcat:distribution>
        <dcat:distribution>
          <dcat:Distribution rdf:about="{dataset_uri}/resource/csv">
            <dct:title xml:lang="pl">Tabela krajowego rejestru AED (CSV)</dct:title>
            <dcat:accessURL rdf:resource="{clean_base}/api/v1/export.csv"/>
            <dct:format rdf:resource="http://publications.europa.eu/resource/authority/file-type/CSV"/>
            <dcatappl:opennessScore rdf:resource="{vocab_uri}/3-stars"/>
          </dcat:Distribution>
        </dcat:distribution>
        <dcat:distribution>
          <dcat:Distribution rdf:about="{dataset_uri}/resource/jsonld">
            <dct:title xml:lang="pl">Katalog semantyczny Linked Open Data AED (DCAT-AP-PL JSON-LD)</dct:title>
            <dcat:accessURL rdf:resource="{clean_base}/api/v1/export.jsonld"/>
            <dct:format rdf:resource="http://publications.europa.eu/resource/authority/file-type/JSON_LD"/>
            <dcatappl:opennessScore rdf:resource="{vocab_uri}/4-stars"/>
          </dcat:Distribution>
        </dcat:distribution>
      </dcat:Dataset>
    </dcat:dataset>
  </dcat:Catalog>
</rdf:RDF>
"""
        return rdf_xml.encode("utf-8"), "application/rdf+xml; charset=utf-8"

    if fmt in ("nt", "ntriples"):
        nt = (
            f'<{catalog_uri}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/ns/dcat#Catalog> .\n'
            f'<{catalog_uri}> <http://www.w3.org/ns/dcat#dataset> <{dataset_uri}> .\n'
            f'<{dataset_uri}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/ns/dcat#Dataset> .\n'
            f'<{dataset_uri}> <http://purl.org/dc/terms/identifier> "krajowy-rejestr-aed-polska" .\n'
            f'<{dataset_uri}> <http://www.w3.org/ns/dcat#distribution> <{dataset_uri}/resource/geojson> .\n'
            f'<{dataset_uri}/resource/geojson> <https://api.dane.gov.pl/ns/dcatappl#opennessScore> <{vocab_uri}/3-stars> .\n'
        )
        return nt.encode("utf-8"), "application/n-triples; charset=utf-8"

    # Default: JSON-LD DCAT-AP-PL Catalog
    catalog_doc = {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
            "foaf": "http://xmlns.com/foaf/0.1/",
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "dcatappl": "https://api.dane.gov.pl/ns/dcatappl#",
        },
        "@id": catalog_uri,
        "@type": "dcat:Catalog",
        "dct:title": [
            {"@value": "Krajowy Rejestr AED — Katalog Otwartych Danych", "@language": "pl"},
            {"@value": "National AED Registry — Open Data Catalog", "@language": "en"},
        ],
        "dct:description": [
            {
                "@value": f"Katalog DCAT-AP-PL zawierający {total_records} zharmonizowanych punktów AED w Polsce.",
                "@language": "pl",
            }
        ],
        "dct:modified": updated_iso,
        "dct:language": {"@id": "http://publications.europa.eu/resource/authority/language/POL"},
        "dct:spatial": {"@id": "http://publications.europa.eu/resource/authority/country/POL"},
        "dct:publisher": {
            "@type": "foaf:Organization",
            "foaf:name": "Ministerstwo Cyfryzacji — dane.gov.pl",
            "dcatappl:regon": settings.INSTITUTION_REGON,
        },
        "dcat:dataset": [
            {
                "@id": dataset_uri,
                "@type": "dcat:Dataset",
                "dct:identifier": "krajowy-rejestr-aed-polska",
                "dct:title": [
                    {
                        "@value": "Krajowy Rejestr AED — Ogólnopolski Wykaz Automatycznych Defibrylatorów Zewnętrznych",
                        "@language": "pl",
                    },
                    {
                        "@value": "National AED Registry — Unified Polish Automated External Defibrillator Open Data Hub",
                        "@language": "en",
                    },
                ],
                "dct:modified": updated_iso,
                "dct:accrualPeriodicity": {
                    "@id": "http://publications.europa.eu/resource/authority/frequency/DAILY"
                },
                "dcat:theme": [
                    {"@id": "http://publications.europa.eu/resource/authority/data-theme/HEAL"},
                    {"@id": "http://publications.europa.eu/resource/authority/data-theme/GOVE"},
                    {"@id": "http://publications.europa.eu/resource/authority/data-theme/REGI"},
                ],
                "dcat:distribution": [
                    {
                        "@id": f"{dataset_uri}/resource/geojson",
                        "@type": "dcat:Distribution",
                        "dcat:accessURL": {"@id": f"{clean_base}/api/v1/export.geojson"},
                        "dcat:downloadURL": {"@id": f"{clean_base}/api/v1/export.geojson"},
                        "dct:format": {
                            "@id": "http://publications.europa.eu/resource/authority/file-type/GEOJSON"
                        },
                        "dcatappl:opennessScore": {"@id": f"{vocab_uri}/3-stars"},
                    },
                    {
                        "@id": f"{dataset_uri}/resource/csv",
                        "@type": "dcat:Distribution",
                        "dcat:accessURL": {"@id": f"{clean_base}/api/v1/export.csv"},
                        "dcat:downloadURL": {"@id": f"{clean_base}/api/v1/export.csv"},
                        "dct:format": {
                            "@id": "http://publications.europa.eu/resource/authority/file-type/CSV"
                        },
                        "dcatappl:opennessScore": {"@id": f"{vocab_uri}/3-stars"},
                    },
                    {
                        "@id": f"{dataset_uri}/resource/jsonld",
                        "@type": "dcat:Distribution",
                        "dcat:accessURL": {"@id": f"{clean_base}/api/v1/export.jsonld"},
                        "dcat:downloadURL": {"@id": f"{clean_base}/api/v1/export.jsonld"},
                        "dct:format": {
                            "@id": "http://publications.europa.eu/resource/authority/file-type/JSON_LD"
                        },
                        "dcatappl:opennessScore": {"@id": f"{vocab_uri}/4-stars"},
                    },
                ],
            }
        ],
    }
    return json.dumps(catalog_doc, ensure_ascii=False).encode("utf-8"), "application/ld+json; charset=utf-8"
