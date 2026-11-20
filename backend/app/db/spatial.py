import math
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AED


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    earth_radius_m = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2.0) ** 2)
    )
    return 2.0 * earth_radius_m * math.asin(min(1.0, math.sqrt(a)))


def walking_minutes(distance_m: float) -> int:
    return max(1, math.ceil(distance_m / 80.0))


def lat_lng_delta_for_radius(lat: float, radius_m: float) -> tuple[float, float]:
    # 1 deg latitude ~= 111,320 m; guard cos(lat) near poles
    dlat = (radius_m / 111_320.0) * 1.1
    cos_lat = max(0.1, math.cos(math.radians(lat)))
    dlng = (radius_m / (111_320.0 * cos_lat)) * 1.1
    return dlat, dlng


def filter_bbox_clause(
    min_lng: float,
    min_lat: float,
    max_lng: float,
    max_lat: float,
    is_postgres: bool,
) -> Any:
    if is_postgres:
        return func.ST_Intersects(
            AED.geom,
            func.ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326),
        )
    return (
        (AED.latitude >= min_lat)
        & (AED.latitude <= max_lat)
        & (AED.longitude >= min_lng)
        & (AED.longitude <= max_lng)
    )


async def find_dedup_candidates(
    session: AsyncSession,
    lat: float,
    lng: float,
    radius_m: float,
    is_postgres: bool,
) -> list[tuple[AED, float]]:
    if is_postgres:
        stmt = text(
            """
            SELECT id,
                   ST_Distance(
                       geom::geography,
                       ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                   ) AS dist_m
            FROM aeds
            WHERE ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius_m
            )
            ORDER BY dist_m ASC
            LIMIT 10
            FOR UPDATE
            """
        )
        rows = (await session.execute(stmt, {"lat": lat, "lng": lng, "radius_m": radius_m})).all()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        dist_map = {r[0]: float(r[1]) for r in rows}
        aeds = (await session.execute(select(AED).where(AED.id.in_(ids)))).scalars().all()
        aed_map = {a.id: a for a in aeds}
        return [(aed_map[aid], dist_map[aid]) for aid in ids if aid in aed_map]

    dlat, dlng = lat_lng_delta_for_radius(lat, radius_m)
    stmt = select(AED).where(
        AED.latitude.between(lat - dlat, lat + dlat),
        AED.longitude.between(lng - dlng, lng + dlng),
    )
    candidates = (await session.execute(stmt)).scalars().all()
    matched: list[tuple[AED, float]] = []
    for cand in candidates:
        dist = haversine_m(lat, lng, cand.latitude, cand.longitude)
        if dist <= radius_m:
            matched.append((cand, dist))
    matched.sort(key=lambda item: item[1])
    return matched[:10]


async def find_nearest_aeds(
    session: AsyncSession,
    lat: float,
    lng: float,
    radius_m: float,
    limit: int,
    is_postgres: bool,
    extra_clauses: list[Any] | None = None,
) -> list[tuple[AED, float]]:
    clauses = list(extra_clauses or [])

    if is_postgres:
        dist_expr = func.ST_Distance(
            text("aeds.geom::geography"),
            text("ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"),
        ).label("dist_m")
        dwithin_expr = func.ST_DWithin(
            text("aeds.geom::geography"),
            text("ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"),
            radius_m,
        )
        stmt = (
            select(AED, dist_expr)
            .where(dwithin_expr, *clauses)
            .params(lat=lat, lng=lng)
            .order_by(dist_expr.asc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return [(row[0], round(float(row[1]), 1)) for row in rows]

    dlat, dlng = lat_lng_delta_for_radius(lat, radius_m)
    stmt = select(AED).where(
        AED.latitude.between(lat - dlat, lat + dlat),
        AED.longitude.between(lng - dlng, lng + dlng),
        *clauses,
    )
    candidates = (await session.execute(stmt)).scalars().all()
    results: list[tuple[AED, float]] = []
    for cand in candidates:
        dist = haversine_m(lat, lng, cand.latitude, cand.longitude)
        if dist <= radius_m:
            results.append((cand, round(dist, 1)))
    results.sort(key=lambda item: item[1])
    return results[:limit]
