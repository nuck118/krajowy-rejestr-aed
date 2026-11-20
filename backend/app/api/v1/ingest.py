import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.ingestion import (
    IngestionRunRequest,
    IngestionRunResponse,
    IngestionUploadRequest,
)
from app.services.ingestion_runner import execute_ingestion_run, execute_payload_ingestion

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.post("/run", response_model=IngestionRunResponse)
async def run_ingestion(
    payload: IngestionRunRequest,
    session: AsyncSession = Depends(get_db),
) -> IngestionRunResponse:
    try:
        return await execute_ingestion_run(
            session=session,
            source=payload.source,
            bbox=payload.bbox,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source dataset file missing: {exc}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream Overpass API error: {exc}",
        ) from exc


@router.post("/upload", response_model=IngestionRunResponse)
async def upload_dataset_ingestion(
    body: IngestionUploadRequest,
    session: AsyncSession = Depends(get_db),
) -> IngestionRunResponse:
    return await execute_payload_ingestion(
        session=session,
        source_name=body.source_name,
        payload=body.payload,
    )
