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
    if settings.is_postgres:
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

    graph: list[dict[str, Any]] = [
        {
            "@id": f"{clean_base}/api/v1/export.jsonld#dataset",
            "@type": "dcat:Dataset",
            "dct:title": "Krajowy Rejestr AED — National Automated External Defibrillator Registry",
            "dct:description": (
                "Unified Polish national registry of Automated External Defibrillators (AED) "
                "harmonized from municipal registries, OpenStreetMap, and verified institutional submissions."
            ),
            "dct:license": "https://creativecommons.org/publicdomain/zero/1.0/",
            "dct:issued": generated_iso,
            "dct:modified": generated_iso,
            "dct:language": "pl",
            "dct:spatial": "http://publications.europa.eu/resource/authority/country/POL",
            "dct:publisher": {
                "@type": "foaf:Organization",
                "foaf:name": "Ministry of Digitization — dane.gov.pl Open Data Hub",
            },
            "dcat:distribution": [
                {
                    "@type": "dcat:Distribution",
                    "dcat:accessURL": f"{clean_base}/api/v1/export.geojson",
                    "dct:format": "GeoJSON",
                    "dcat:mediaType": "application/geo+json",
                },
                {
                    "@type": "dcat:Distribution",
                    "dcat:accessURL": f"{clean_base}/api/v1/export.csv",
                    "dct:format": "CSV",
                    "dcat:mediaType": "text/csv",
                },
                {
                    "@type": "dcat:Distribution",
                    "dcat:accessURL": f"{clean_base}/api/v1/export.jsonld",
                    "dct:format": "JSON-LD",
                    "dcat:mediaType": "application/ld+json",
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
            "schema": "https://schema.org/",
            "aed": "https://dane.gov.pl/vocab/aed#",
        },
        "@graph": graph,
    }
    return json.dumps(doc, ensure_ascii=False).encode("utf-8")
