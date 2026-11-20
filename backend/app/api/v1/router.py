from fastapi import APIRouter

from app.api.v1 import aeds, exports, ingest, stats

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(aeds.router)
api_router.include_router(ingest.router)
api_router.include_router(stats.router)
api_router.include_router(exports.router)
