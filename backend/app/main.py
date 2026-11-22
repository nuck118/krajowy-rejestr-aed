from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.mcod_middleware import MCODCoreMiddleware, mcod_metrics
from app.db.models import AED, AEDLike, AEDSourceRecord, DatasetLike
from app.db.session import async_session_factory, get_db, init_db_schema
from app.services.ingestion_runner import execute_ingestion_run

logger = logging.getLogger(__name__)


def _default_frontend_dist() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "frontend" / "dist"
        if candidate.is_dir():
            return candidate
    return Path.cwd() / "frontend" / "dist"


FRONTEND_DIST = _default_frontend_dist()


async def _auto_seed_if_empty() -> None:
    if not settings.AUTO_SEED_ON_EMPTY:
        return
    async with async_session_factory() as session:
        count = int((await session.execute(select(func.count(AED.id)))).scalar_one() or 0)
        if count > 0:
            return
        pl_path = settings.DATA_DIR / "PL.geojson"
        if pl_path.is_file():
            try:
                await execute_ingestion_run(session, source="pl_geojson")
            except Exception as exc:
                logger.warning("Auto-seed pl_geojson skipped: %s", exc)
        try:
            await execute_ingestion_run(session, source="dane_gov_municipal")
        except Exception as exc:
            logger.warning("Auto-seed dane_gov_municipal skipped: %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db_schema()
    await _auto_seed_if_empty()
    yield


app = FastAPI(
    title="Krajowy Rejestr AED — National Open Data Hub API",
    version=settings.APP_VERSION,
    description=(
        "Canonical Polish AED defibrillator registry API and automated dane.gov.pl harvester bridge "
        "(GeoJSON, CSV, DCAT-AP JSON-LD, 25m spatial deduplication, and PostGIS proximity search)."
    ),
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

_cors_origins = settings.cors_origin_list or ["*"]
_is_wildcard_cors = "*" in _cors_origins

app.add_middleware(MCODCoreMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _is_wildcard_cors else _cors_origins,
    allow_origin_regex=None if _is_wildcard_cors else r"https://.*\.vercel\.app",
    allow_credentials=not _is_wildcard_cors,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag", "X-API-Version", "X-Total-Count", "Content-Disposition"],
)

app.include_router(api_router)


@app.get("/ping", tags=["System"])
async def mcod_ping() -> dict[str, None]:
    """Mirrors dane.gov.pl's `mcod/api.py` `/ping` health sink."""
    return {"data": None}


@app.get("/metrics", tags=["System"])
async def prometheus_metrics_root(session: AsyncSession = Depends(get_db)) -> Response:
    """Mirrors dane.gov.pl's `MetricsResource` (`/metrics`, OTD-3073)."""
    total_aeds = int((await session.execute(select(func.count(AED.id)))).scalar_one() or 0)
    aed_likes = int((await session.execute(select(func.count(AEDLike.id)))).scalar_one() or 0)
    ds_likes = int((await session.execute(select(func.count(DatasetLike.id)))).scalar_one() or 0)
    active_sources = int(
        (
            await session.execute(select(func.count(func.distinct(AEDSourceRecord.source_name))))
        ).scalar_one()
        or 0
    )
    payload = mcod_metrics.render_prometheus_text(
        total_aeds=total_aeds,
        total_likes=aed_likes + ds_likes,
        active_sources=active_sources,
    )
    return Response(
        content=payload.encode("utf-8"),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/health", tags=["System"])
async def health_check(session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    await session.execute(text("SELECT 1"))
    postgis_active = False
    if settings.use_postgis:
        try:
            ver = (await session.execute(text("SELECT PostGIS_Version()"))).scalar_one_or_none()
            postgis_active = bool(ver)
        except Exception:
            postgis_active = False
    return {
        "status": "ok",
        "database_dialect": settings.database_dialect,
        "postgis": postgis_active,
        "mcod_api_version": settings.MCOD_API_VERSION,
        "slow_sql_logging_enabled": settings.SLOW_SQL_LOGGING_ENABLED,
    }


if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    dist_root = FRONTEND_DIST.resolve()
    index_file = dist_root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in {
            "api",
            "docs",
            "redoc",
            "openapi.json",
            "health",
            "ping",
            "metrics",
        }:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        if full_path:
            candidate = (dist_root / full_path).resolve()
            if candidate.is_relative_to(dist_root) and candidate.is_file():
                return FileResponse(candidate)

        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frontend build missing")
