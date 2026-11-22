from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import OPEN_DATA_HEADERS
from app.db.models import AED
from app.db.session import get_db
from app.services.completeness import ensure_utc
from app.services.exporter import (
    compute_export_etag,
    generate_csv_bytes,
    generate_geojson_bytes,
    generate_jsonld_bytes,
)
from app.services.standard_xlsx import (
    compute_dane_gov_harvester_md5,
    compute_standard_xlsx_etag,
    generate_dane_gov_harvester_xml,
    generate_standard_xlsx_bytes,
    validate_dane_gov_harvester_xml,
)

router = APIRouter(tags=["dane.gov.pl Harvester Exports"])


def _etag_matches(if_none_match: str | None, current_etag: str) -> bool:
    if not if_none_match:
        return False
    candidates = [tag.strip() for tag in if_none_match.split(",")]
    return "*" in candidates or current_etag in candidates


def _build_export_headers(filename: str, etag: str) -> dict[str, str]:
    return {
        **OPEN_DATA_HEADERS,
        "Content-Disposition": f'attachment; filename="{filename}"',
        "ETag": etag,
    }


@router.get("/export.geojson")
async def export_geojson(
    city: str | None = Query(default=None),
    min_completeness: int | None = Query(default=None, ge=0, le=100),
    limit: int | None = Query(default=None, ge=1, le=50000),
    if_none_match: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> Response:
    etag = await compute_export_etag(
        session, fmt="geojson", city=city, min_completeness=min_completeness, limit=limit
    )
    headers = _build_export_headers("krajowy-rejestr-aed.geojson", etag)
    if _etag_matches(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    content = await generate_geojson_bytes(
        session, city=city, min_completeness=min_completeness, limit=limit
    )
    return Response(
        content=content,
        media_type="application/geo+json; charset=utf-8",
        headers=headers,
    )


@router.get("/export.csv")
async def export_csv(
    city: str | None = Query(default=None),
    min_completeness: int | None = Query(default=None, ge=0, le=100),
    limit: int | None = Query(default=None, ge=1, le=50000),
    if_none_match: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> Response:
    etag = await compute_export_etag(
        session, fmt="csv", city=city, min_completeness=min_completeness, limit=limit
    )
    headers = _build_export_headers("krajowy-rejestr-aed.csv", etag)
    if _etag_matches(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    content = await generate_csv_bytes(
        session, city=city, min_completeness=min_completeness, limit=limit
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.get("/export.jsonld")
async def export_jsonld(
    request: Request,
    city: str | None = Query(default=None),
    min_completeness: int | None = Query(default=None, ge=0, le=100),
    limit: int | None = Query(default=None, ge=1, le=50000),
    if_none_match: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> Response:
    etag = await compute_export_etag(
        session, fmt="jsonld", city=city, min_completeness=min_completeness, limit=limit
    )
    headers = _build_export_headers("krajowy-rejestr-aed.jsonld", etag)
    if _etag_matches(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    base_url = str(request.base_url).rstrip("/")
    content = await generate_jsonld_bytes(
        session,
        base_url=base_url,
        city=city,
        min_completeness=min_completeness,
        limit=limit,
    )
    return Response(
        content=content,
        media_type="application/ld+json; charset=utf-8",
        headers=headers,
    )


@router.get("/standard.xlsx")
async def export_standard_xlsx(
    if_none_match: str | None = Header(default=None),
) -> Response:
    content = generate_standard_xlsx_bytes()
    etag = compute_standard_xlsx_etag(content)
    headers = _build_export_headers("Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx", etag)
    if _etag_matches(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


async def _build_harvester_xml_payload(
    request: Request,
    session: AsyncSession,
) -> bytes:
    row = (
        await session.execute(select(func.count(AED.id), func.max(AED.updated_at)))
    ).one()
    total_records = int(row[0] or 0)
    max_dt = ensure_utc(row[1]) or datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    base_url = str(request.base_url).rstrip("/")
    return generate_dane_gov_harvester_xml(
        base_url=base_url,
        total_records=total_records,
        updated_iso=max_dt.isoformat(),
    )


@router.api_route("/harvester/dane-gov.xml", methods=["GET", "HEAD"])
async def export_dane_gov_harvester_xml(
    request: Request,
    if_none_match: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> Response:
    etag = await compute_export_etag(
        session, fmt="xml", city=None, min_completeness=None, limit=None
    )
    headers = _build_export_headers("krajowy-rejestr-aed-harvester.xml", etag)
    if _etag_matches(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    content = await _build_harvester_xml_payload(request, session)
    headers["X-Harvester-MD5"] = compute_dane_gov_harvester_md5(content)
    headers["X-Harvester-Schema-Version"] = "1.13"
    if request.method == "HEAD":
        return Response(
            content=b"",
            media_type="application/xml; charset=utf-8",
            headers=headers,
        )
    return Response(
        content=content,
        media_type="application/xml; charset=utf-8",
        headers=headers,
    )


@router.api_route("/harvester/dane-gov.md5", methods=["GET", "HEAD"])
async def export_dane_gov_harvester_md5(
    request: Request,
    if_none_match: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """
    Companion MD5 checksum endpoint required by dane.gov.pl's XML harvester
    (`mcod/harvester/utils.py:get_remote_xml_hash()` & `validate_md5()`).
    """
    etag = await compute_export_etag(
        session, fmt="xml-md5", city=None, min_completeness=None, limit=None
    )
    headers = _build_export_headers("krajowy-rejestr-aed-harvester.md5", etag)
    if _etag_matches(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    xml_bytes = await _build_harvester_xml_payload(request, session)
    md5_digest = compute_dane_gov_harvester_md5(xml_bytes)
    body = f"{md5_digest}\n".encode("utf-8")
    if request.method == "HEAD":
        return Response(
            content=b"",
            media_type="text/plain; charset=utf-8",
            headers=headers,
        )
    return Response(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers=headers,
    )


@router.get("/harvester/validate")
async def validate_dane_gov_harvester_feed(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """
    Validates our live XML and MD5 endpoints against the 5-step verification
    pipeline in dane.gov.pl's `mcod/harvester/utils.py:validate_xml_url()`
    and `xml_import_otwarte_dane_1_13.xsd`.
    """
    xml_bytes = await _build_harvester_xml_payload(request, session)
    md5_digest = compute_dane_gov_harvester_md5(xml_bytes)
    base_url = str(request.base_url).rstrip("/")
    return validate_dane_gov_harvester_xml(
        xml_bytes=xml_bytes,
        md5_text=md5_digest,
        content_type="application/xml; charset=utf-8",
        xml_url=f"{base_url}/api/v1/harvester/dane-gov.xml",
    )
