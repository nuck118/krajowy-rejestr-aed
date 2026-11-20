import uuid

from app.schemas.aed import AEDCreate, AEDIngestCandidate
from app.services.deduplication import RawRecord


def build_direct_submission_record(payload: AEDCreate) -> RawRecord:
    external_id = payload.external_id or f"sub:{uuid.uuid4()}"
    candidate = AEDIngestCandidate(
        latitude=payload.latitude,
        longitude=payload.longitude,
        street_address=payload.street_address,
        city=payload.city,
        postal_code=payload.postal_code,
        teryt_code=payload.teryt_code,
        location_description=payload.location_description,
        access_type=payload.access_type,
        opening_hours=payload.opening_hours,
        is_24_7=payload.is_24_7,
        indoor=payload.indoor,
        status=payload.status,
        last_verified_at=payload.last_verified_at,
    )
    return RawRecord(
        source_name=payload.source_name,
        external_id=external_id,
        candidate=candidate,
        raw_payload=payload.model_dump(mode="json"),
    )
