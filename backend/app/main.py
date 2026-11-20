from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.models import AED
from app.db.session import async_session_factory, get_db, init_db_schema
from app.services.ingestion_runner import execute_ingestion_run

logger = logging.getLogger(__name__)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["System"])
async def health_check(session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    await session.execute(text("SELECT 1"))
    postgis_active = False
    if settings.is_postgres:
        ver = (await session.execute(text("SELECT PostGIS_Version()"))).scalar_one_or_none()
        postgis_active = bool(ver)
    return {
        "status": "ok",
        "database_dialect": "postgresql+postgis" if settings.is_postgres else "sqlite+spatial",
        "postgis": postgis_active,
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
        }:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        if full_path:
            candidate = (dist_root / full_path).resolve()
            if candidate.is_relative_to(dist_root) and candidate.is_file():
                return FileResponse(candidate)

        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frontend build missing")
