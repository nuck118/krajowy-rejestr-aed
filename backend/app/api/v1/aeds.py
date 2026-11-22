from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import (
    POLAND_LAT_MAX,
    POLAND_LAT_MIN,
    POLAND_LNG_MAX,
    POLAND_LNG_MIN,
)
from app.core.mcod_middleware import resolve_user_ident
from app.connectors.direct_submission import build_direct_submission_record
from app.db.models import AED, AEDLike, AEDVerification
from app.db.session import get_db
from app.db.spatial import filter_bbox_clause, find_nearest_aeds, walking_minutes
from app.schemas.aed import (
    AccessType,
    AEDCreate,
    AEDDetailRead,
    AEDExtraMetadata,
    AEDNearestRead,
    AEDRead,
    AEDSubmitResponse,
    AEDVerifyRequest,
    GeocodeResponse,
    LikeStatusResponse,
    NearestAEDResponse,
    PaginatedAEDResponse,
    SourceRecordSummary,
)
from app.services.completeness import (
    POSTAL_RE,
    completeness_tier,
    compute_completeness_for_obj,
    ensure_utc,
)
from app.services.deduplication import upsert_single_candidate
from app.services.metadata import extract_source_metadata
from app.services.opening_hours import is_open_now
from app.services.reverse_geocode import (
    compose_factual_placement,
    format_geocode_label,
    forward_geocode_poland,
    reverse_geocode_poland,
)

router = APIRouter(prefix="/aeds", tags=["AEDs"])


def _ordered_sources(aed: AED) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    if aed.primary_source:
        seen.add(aed.primary_source)
        ordered.append(aed.primary_source)
    for sr in getattr(aed, "source_records", []) or []:
        if sr.source_name not in seen:
            seen.add(sr.source_name)
            ordered.append(sr.source_name)
    return ordered


def serialize_aed(
    aed: AED,
    *,
    likes_count: int = 0,
    is_liked_by_current_user: bool = False,
) -> AEDRead:
    return AEDRead(
        id=aed.id,
        latitude=aed.latitude,
        longitude=aed.longitude,
        street_address=aed.street_address,
        city=aed.city,
        postal_code=aed.postal_code,
        teryt_code=aed.teryt_code,
        location_description=aed.location_description,
        access_type=aed.access_type,
        opening_hours=aed.opening_hours,
        is_24_7=aed.is_24_7,
        indoor=aed.indoor,
        status=aed.status,
        last_verified_at=ensure_utc(aed.last_verified_at),
        completeness_score=aed.completeness_score,
        completeness_tier=completeness_tier(aed.completeness_score),
        primary_source=aed.primary_source,
        sources=_ordered_sources(aed),
        open_now=is_open_now(aed.opening_hours, aed.is_24_7),
        likes_count=likes_count,
        is_liked_by_current_user=is_liked_by_current_user,
        created_at=ensure_utc(aed.created_at) or datetime.now(timezone.utc),
        updated_at=ensure_utc(aed.updated_at) or datetime.now(timezone.utc),
    )


async def _fetch_likes_maps(
    session: AsyncSession,
    aed_ids: list[UUID],
    user_ident: str | None = None,
) -> tuple[dict[UUID, int], set[UUID]]:
    if not aed_ids:
        return {}, set()
    counts_rows = (
        await session.execute(
            select(AEDLike.aed_id, func.count(AEDLike.id))
            .where(AEDLike.aed_id.in_(aed_ids))
            .group_by(AEDLike.aed_id)
        )
    ).all()
    counts_map: dict[UUID, int] = {row[0]: int(row[1]) for row in counts_rows}

    liked_set: set[UUID] = set()
    if user_ident:
        liked_rows = (
            await session.execute(
                select(AEDLike.aed_id).where(
                    AEDLike.aed_id.in_(aed_ids),
                    AEDLike.user_ident == user_ident,
                )
            )
        ).scalars().all()
        liked_set = set(liked_rows)
    return counts_map, liked_set


def _build_filter_clauses(
    *,
    city: str | None = None,
    q: str | None = None,
    access_type: AccessType | None = None,
    indoor: bool | None = None,
    is_24_7: bool | None = None,
    min_completeness: int | None = None,
    bbox: str | None = None,
) -> list[Any]:
    clauses: list[Any] = []
    if city:
        clauses.append(func.lower(AED.city) == city.strip().lower())
    if q:
        pattern = f"%{q.strip()}%"
        clauses.append(
            or_(
                AED.location_description.ilike(pattern),
                AED.street_address.ilike(pattern),
                AED.city.ilike(pattern),
            )
        )
    if access_type is not None:
        clauses.append(AED.access_type == access_type)
    if indoor is not None:
        clauses.append(AED.indoor.is_(indoor))
    if is_24_7 is not None:
        clauses.append(AED.is_24_7.is_(is_24_7))
    if min_completeness is not None:
        clauses.append(AED.completeness_score >= min_completeness)
    if bbox:
        parts = [p.strip() for p in bbox.split(",")]
        if len(parts) != 4:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="bbox must be formatted as minLng,minLat,maxLng,maxLat",
            )
        try:
            min_lng, min_lat, max_lng, max_lat = (float(p) for p in parts)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="bbox coordinates must be numeric",
            ) from exc
        clauses.append(filter_bbox_clause(min_lng, min_lat, max_lng, max_lat, settings.use_postgis))
    return clauses


@router.get("", response_model=PaginatedAEDResponse)
async def list_aeds(
    request: Request,
    city: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Substring search in placement, street, or city"),
    access_type: AccessType | None = Query(default=None),
    indoor: bool | None = Query(default=None),
    is_24_7: bool | None = Query(default=None),
    open_now: bool | None = Query(default=None),
    min_completeness: int | None = Query(default=None, ge=0, le=100),
    bbox: str | None = Query(default=None, description="minLng,minLat,maxLng,maxLat"),
    lat: float | None = Query(default=None, ge=-90.0, le=90.0),
    lng: float | None = Query(default=None, ge=-180.0, le=180.0),
    radius: float | None = Query(default=None, ge=10, le=100_000, description="Radius in meters (alias)"),
    radius_m: float | None = Query(default=None, ge=10, le=100_000, description="Radius in meters"),
    sort: str | None = Query(
        default=None,
        description="Sort field (e.g. -likes_count, likes_count, -completeness_score, completeness_score)",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> PaginatedAEDResponse:
    user_ident = resolve_user_ident(request)
    clauses = _build_filter_clauses(
        city=city,
        q=q,
        access_type=access_type,
        indoor=indoor,
        is_24_7=is_24_7,
        min_completeness=min_completeness,
        bbox=bbox,
    )

    if lat is not None and lng is not None:
        effective_radius = radius_m or radius or 1000.0
        nearest = await find_nearest_aeds(
            session,
            lat=lat,
            lng=lng,
            radius_m=effective_radius,
            limit=max(limit + offset, 500),
            is_postgres=settings.use_postgis,
            extra_clauses=clauses,
        )
        aed_objs = [aed for aed, _dist in nearest]
        counts_map, liked_set = await _fetch_likes_maps(
            session, [a.id for a in aed_objs], user_ident
        )
        serialized = [
            serialize_aed(
                aed,
                likes_count=counts_map.get(aed.id, 0),
                is_liked_by_current_user=aed.id in liked_set,
            )
            for aed in aed_objs
        ]
        if open_now is not None:
            serialized = [item for item in serialized if item.open_now is open_now]
        if sort in ("likes_count", "-likes_count"):
            serialized.sort(key=lambda x: x.likes_count, reverse=sort.startswith("-"))
        total = len(serialized)
        return PaginatedAEDResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=serialized[offset : offset + limit],
        )

    if open_now is not None or sort in ("likes_count", "-likes_count"):
        if open_now is True:
            clauses.append(or_(AED.is_24_7.is_(True), AED.opening_hours.is_not(None)))
        stmt = (
            select(AED)
            .where(*clauses)
            .order_by(AED.completeness_score.desc(), AED.updated_at.desc())
        )
        rows = list((await session.execute(stmt)).scalars().all())
        counts_map, liked_set = await _fetch_likes_maps(
            session, [a.id for a in rows], user_ident
        )
        filtered = [
            serialize_aed(
                a,
                likes_count=counts_map.get(a.id, 0),
                is_liked_by_current_user=a.id in liked_set,
            )
            for a in rows
        ]
        if open_now is not None:
            filtered = [s for s in filtered if s.open_now is open_now]
        if sort in ("likes_count", "-likes_count"):
            filtered.sort(
                key=lambda x: (x.likes_count, x.completeness_score),
                reverse=sort.startswith("-"),
            )
        return PaginatedAEDResponse(
            total=len(filtered),
            limit=limit,
            offset=offset,
            items=filtered[offset : offset + limit],
        )

    total_stmt = select(func.count(AED.id)).where(*clauses)
    total = int((await session.execute(total_stmt)).scalar_one())

    order_col = AED.completeness_score.asc() if sort == "completeness_score" else AED.completeness_score.desc()
    stmt = (
        select(AED)
        .where(*clauses)
        .order_by(order_col, AED.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    counts_map, liked_set = await _fetch_likes_maps(
        session, [a.id for a in rows], user_ident
    )
    return PaginatedAEDResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            serialize_aed(
                a,
                likes_count=counts_map.get(a.id, 0),
                is_liked_by_current_user=a.id in liked_set,
            )
            for a in rows
        ],
    )


@router.get("/nearest", response_model=NearestAEDResponse)
async def get_nearest_aeds(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lng: float = Query(..., ge=-180.0, le=180.0),
    radius_m: float = Query(default=5000.0, ge=10, le=50000),
    limit: int = Query(default=25, ge=1, le=200),
    open_now: bool | None = Query(default=None),
    is_24_7: bool | None = Query(default=None),
    access_type: AccessType | None = Query(default=None),
    indoor: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> NearestAEDResponse:
    clauses = _build_filter_clauses(
        access_type=access_type,
        indoor=indoor,
        is_24_7=is_24_7,
    )
    fetch_limit = min(limit * 4, 500) if open_now is not None else limit
    candidates = await find_nearest_aeds(
        session,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        limit=fetch_limit,
        is_postgres=settings.use_postgis,
        extra_clauses=clauses,
    )

    items: list[AEDNearestRead] = []
    for aed, dist_m in candidates:
        base = serialize_aed(aed)
        if open_now is not None and base.open_now is not open_now:
            continue
        items.append(
            AEDNearestRead(
                **base.model_dump(),
                distance_m=dist_m,
                walking_minutes=walking_minutes(dist_m),
            )
        )
        if len(items) >= limit:
            break

    return NearestAEDResponse(
        origin={"lat": round(lat, 6), "lng": round(lng, 6)},
        radius_m=radius_m,
        count=len(items),
        items=items,
    )


@router.get("/geocode", response_model=GeocodeResponse)
async def geocode_polish_query(
    q: str = Query(..., min_length=2, max_length=250, description="Polish address, street, city, or coordinates"),
) -> GeocodeResponse:
    res = await forward_geocode_poland(q)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching Polish location found",
        )
    return GeocodeResponse(
        latitude=res.latitude,
        longitude=res.longitude,
        label=res.label,
        street_address=res.street_address,
        city=res.city,
        postal_code=res.postal_code,
        place_name=res.place_name,
    )


@router.get("/reverse-geocode", response_model=GeocodeResponse)
async def reverse_geocode_point(
    lat: float = Query(..., ge=POLAND_LAT_MIN, le=POLAND_LAT_MAX),
    lng: float = Query(..., ge=POLAND_LNG_MIN, le=POLAND_LNG_MAX),
) -> GeocodeResponse:
    geo = await reverse_geocode_poland(lat, lng)
    label = format_geocode_label(
        place_name=geo.place_name if geo else None,
        street_address=geo.street_address if geo else None,
        postal_code=geo.postal_code if geo else None,
        city=geo.city if geo else None,
        lat=lat,
        lng=lng,
    )
    return GeocodeResponse(
        latitude=round(lat, 6),
        longitude=round(lng, 6),
        label=label,
        street_address=geo.street_address if geo else None,
        city=geo.city if geo else None,
        postal_code=geo.postal_code if geo else None,
        place_name=geo.place_name if geo else None,
    )


@router.get("/{aed_id}", response_model=AEDDetailRead)
async def get_aed_detail(
    request: Request,
    aed_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> AEDDetailRead:
    aed = (await session.execute(select(AED).where(AED.id == aed_id))).scalar_one_or_none()
    if aed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AED record not found")

    meta_dict = extract_source_metadata(aed.source_records)

    if settings.ENABLE_REVERSE_GEOCODING and (
        aed.street_address is None or aed.city is None or aed.location_description is None
    ):
        geo = await reverse_geocode_poland(aed.latitude, aed.longitude)
        if geo is not None:
            changed = False
            if aed.street_address is None and geo.street_address:
                aed.street_address = geo.street_address[:255]
                changed = True
            if aed.city is None and geo.city:
                aed.city = geo.city[:120]
                changed = True
            if aed.postal_code is None and geo.postal_code and POSTAL_RE.match(geo.postal_code):
                aed.postal_code = geo.postal_code
                changed = True
            if aed.location_description is None:
                composed = compose_factual_placement(
                    geo,
                    indoor=aed.indoor,
                    level=meta_dict.get("level"),
                    operator=meta_dict.get("operator"),
                )
                if composed:
                    aed.location_description = composed
                    changed = True
            if changed:
                aed.updated_at = datetime.now(timezone.utc)
                aed.completeness_score = compute_completeness_for_obj(aed)
                await session.commit()
                await session.refresh(aed, attribute_names=["source_records"])

    user_ident = resolve_user_ident(request)
    counts_map, liked_set = await _fetch_likes_maps(session, [aed.id], user_ident)
    base = serialize_aed(
        aed,
        likes_count=counts_map.get(aed.id, 0),
        is_liked_by_current_user=aed.id in liked_set,
    )
    provenance = [
        SourceRecordSummary(
            id=sr.id,
            source_name=sr.source_name,
            source_trust_tier=sr.source_trust_tier,
            external_id=sr.external_id,
            ingested_at=ensure_utc(sr.ingested_at) or datetime.now(timezone.utc),
        )
        for sr in sorted(
            aed.source_records,
            key=lambda r: ensure_utc(r.ingested_at) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
    ]
    return AEDDetailRead(
        **base.model_dump(),
        provenance=provenance,
        extra_metadata=AEDExtraMetadata(**meta_dict),
    )


@router.post("/{aed_id}/likes", response_model=LikeStatusResponse, status_code=status.HTTP_201_CREATED)
async def add_aed_like(
    request: Request,
    aed_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> LikeStatusResponse:
    """Adds a user like for an AED record (MCOD v2.63.0 OTD-3100)."""
    aed = (await session.execute(select(AED).where(AED.id == aed_id))).scalar_one_or_none()
    if aed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AED record not found")

    user_ident = resolve_user_ident(request)
    existing = (
        await session.execute(
            select(AEDLike).where(AEDLike.aed_id == aed.id, AEDLike.user_ident == user_ident)
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(AEDLike(aed_id=aed.id, user_ident=user_ident))
        await session.commit()

    counts_map, liked_set = await _fetch_likes_maps(session, [aed.id], user_ident)
    return LikeStatusResponse(
        id=str(aed.id),
        likes_count=counts_map.get(aed.id, 0),
        is_liked_by_current_user=aed.id in liked_set,
    )


@router.delete("/{aed_id}/likes", status_code=status.HTTP_204_NO_CONTENT)
async def remove_aed_like(
    request: Request,
    aed_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Removes a user like for an AED record (MCOD v2.63.0 OTD-3101)."""
    aed = (await session.execute(select(AED).where(AED.id == aed_id))).scalar_one_or_none()
    if aed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AED record not found")

    user_ident = resolve_user_ident(request)
    await session.execute(
        delete(AEDLike).where(AEDLike.aed_id == aed.id, AEDLike.user_ident == user_ident)
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "",
    response_model=AEDSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_aed(
    payload: AEDCreate,
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    raw_record = build_direct_submission_record(payload)
    action, aed, dist_m = await upsert_single_candidate(
        session,
        raw_record,
        radius_m=settings.DEDUP_RADIUS_M,
        is_postgres=settings.use_postgis,
    )
    await session.commit()
    await session.refresh(aed, attribute_names=["source_records"])

    normalized_action = "created" if action == "created" else "merged"
    http_status = status.HTTP_201_CREATED if normalized_action == "created" else status.HTTP_200_OK
    body = AEDSubmitResponse(
        action=normalized_action,
        merged_distance_m=dist_m,
        aed=serialize_aed(aed),
    )
    return JSONResponse(status_code=http_status, content=jsonable_encoder(body))


@router.post("/{aed_id}/verify", response_model=AEDRead)
async def verify_aed(
    aed_id: UUID,
    payload: AEDVerifyRequest,
    session: AsyncSession = Depends(get_db),
) -> AEDRead:
    aed = (await session.execute(select(AED).where(AED.id == aed_id))).scalar_one_or_none()
    if aed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AED record not found")

    now = datetime.now(timezone.utc)
    verification = AEDVerification(
        aed_id=aed.id,
        action=payload.action,
        reporter_org=payload.reporter_org,
        notes=payload.notes,
        created_at=now,
    )
    session.add(verification)

    if payload.action == "confirm_operational":
        aed.status = "operational"
    else:
        aed.status = "out_of_service"

    if payload.location_description and len(payload.location_description) >= 3:
        aed.location_description = payload.location_description

    aed.last_verified_at = now
    aed.updated_at = now
    aed.completeness_score = compute_completeness_for_obj(aed, now=now)

    await session.commit()
    await session.refresh(aed, attribute_names=["source_records"])
    return serialize_aed(aed)
