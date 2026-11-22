"""
dane.gov.pl (MCOD v2.63.0) Essential Endpoints Router.

Implements core endpoints from `mcod/routes.py` and `CHANGELOG.md` (v2.63.0):
- DCAT-AP / DCAT-AP-PL RDF Catalog (`/catalog`, `/catalog.{rdf_format}`, `/catalog/dcat_ap/spec`, `/catalog/dcat_ap_pl/spec`)
- Controlled SKOS Vocabularies (`/vocab/openness-score`, `/vocab/openness-score/{entry_name}`, `/vocab/special-sign`, `/vocab/special-sign/{entry_name}`)
- JSON:API v1.4 Datasets & Likes (`/datasets`, `/datasets/{dataset_id}`, `/datasets/{dataset_id}/resources`, `/datasets/{dataset_id}/likes`)
- User Likes & Dashboard (`/auth/user/likes`, `/auth/user/dashboard` - OTD-3155)
- Broken Links Report (`/reports/brokenlinks`, `/reports/brokenlinks/data`)
- Data Governance Act Aggregated Report (`/dga-aggregated`)
- Cluster Health & Slow SQL Diagnostics (`/cluster/health` - OTD-3073)
- Prometheus Metrics (`/metrics` - OTD-3073)
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.dane_gov_municipal import CANONICAL_DANE_GOV_RESOURCES
from app.core.config import settings
from app.core.mcod_middleware import mcod_metrics, resolve_user_ident
from app.db.models import AED, AEDLike, AEDSourceRecord, DatasetLike, IngestionRun
from app.db.session import get_db
from app.services.completeness import ensure_utc
from app.services.exporter import generate_dcat_ap_pl_catalog_rdf

router = APIRouter(tags=["dane.gov.pl MCOD v2.63.0 Compatibility"])

CANONICAL_DATASET_EXT_IDENT = "krajowy-rejestr-aed-polska"
CANONICAL_DATASET_INT_ID = "1"

OPENNESS_SCORE_VOCAB: dict[str, dict[str, Any]] = {
    "1-star": {
        "id": "1-star",
        "notation": "*",
        "openness_score": 1,
        "name_pl": "1 gwiazdka",
        "name_en": "1 star",
        "description_pl": (
            "Pierwszy poziom otwartości danych. Dane w dowolnym formacie, udostępniane bez ograniczeń licencyjnych."
        ),
    },
    "2-stars": {
        "id": "2-stars",
        "notation": "**",
        "openness_score": 2,
        "name_pl": "2 gwiazdki",
        "name_en": "2 stars",
        "description_pl": (
            "Drugi poziom otwartości danych. Dane mają określoną strukturę odczytywalną komputerowo w formacie własnościowym."
        ),
    },
    "3-stars": {
        "id": "3-stars",
        "notation": "***",
        "openness_score": 3,
        "name_pl": "3 gwiazdki",
        "name_en": "3 stars",
        "description_pl": (
            "Trzeci poziom otwartości danych. Dane ustrukturyzowane w otwartym, niezastrzeżonym formacie (np. CSV, GeoJSON)."
        ),
    },
    "4-stars": {
        "id": "4-stars",
        "notation": "****",
        "openness_score": 4,
        "name_pl": "4 gwiazdki",
        "name_en": "4 stars",
        "description_pl": (
            "Czwarty poziom otwartości danych. Dane publikowane w formacie RDF/JSON-LD z jednoznaczną identyfikacją URI."
        ),
    },
    "5-stars": {
        "id": "5-stars",
        "notation": "*****",
        "openness_score": 5,
        "name_pl": "5 gwiazdek",
        "name_en": "5 stars",
        "description_pl": (
            "Piąty poziom otwartości danych. Dane spełniają czwarty poziom oraz zawierają połączenia strukturalne (Linked Open Data) do zewnętrznych słowników URI."
        ),
    },
}

SPECIAL_SIGN_VOCAB: dict[str, dict[str, str]] = {
    "-": {
        "id": "dash",
        "symbol": "-",
        "name_pl": "Kreska",
        "name_en": "Dash",
        "description_pl": "Zjawisko nie wystąpiło.",
    },
    ".": {
        "id": "dot",
        "symbol": ".",
        "name_pl": "Kropka",
        "name_en": "Dot",
        "description_pl": "Zupełny brak informacji albo brak informacji wiarygodnych.",
    },
    "X": {
        "id": "x",
        "symbol": "X",
        "name_pl": "Iks",
        "name_en": "Cross",
        "description_pl": "Wypełnienie pozycji jest niemożliwe lub niecelowe.",
    },
    ":": {
        "id": "colon",
        "symbol": ":",
        "name_pl": "Dwukropek",
        "name_en": "Colon",
        "description_pl": "Zupełny brak informacji albo brak informacji wiarygodnych (Eurostat).",
    },
    "#": {
        "id": "hash",
        "symbol": "#",
        "name_pl": "Hash",
        "name_en": "Hash",
        "description_pl": "Dane nie mogą być opublikowane ze względu na tajemnicę statystyczną.",
    },
}


def _normalize_dataset_ident(dataset_id: str) -> str:
    cleaned = dataset_id.split(",")[0].strip()
    if cleaned in ("1", CANONICAL_DATASET_EXT_IDENT, "krajowy-rejestr-aed"):
        return CANONICAL_DATASET_EXT_IDENT
    return cleaned


async def _dataset_like_stats(
    session: AsyncSession,
    ext_ident: str,
    user_ident: str,
) -> tuple[int, bool]:
    total = int(
        (
            await session.execute(
                select(func.count(DatasetLike.id)).where(DatasetLike.dataset_ext_ident == ext_ident)
            )
        ).scalar_one()
        or 0
    )
    liked = (
        await session.execute(
            select(DatasetLike.id).where(
                DatasetLike.dataset_ext_ident == ext_ident,
                DatasetLike.user_ident == user_ident,
            )
        )
    ).scalar_one_or_none() is not None
    return total, liked


async def _build_dataset_jsonapi_node(
    request: Request,
    session: AsyncSession,
    user_ident: str,
) -> dict[str, Any]:
    row = (
        await session.execute(select(func.count(AED.id), func.max(AED.updated_at)))
    ).one()
    total_records = int(row[0] or 0)
    max_dt = ensure_utc(row[1]) or datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    base_url = str(request.base_url).rstrip("/")

    ds_likes, is_liked = await _dataset_like_stats(
        session, CANONICAL_DATASET_EXT_IDENT, user_ident
    )
    aed_likes_total = int(
        (await session.execute(select(func.count(AEDLike.id)))).scalar_one() or 0
    )
    combined_likes = ds_likes + aed_likes_total

    views_count = mcod_metrics.dataset_views[CANONICAL_DATASET_EXT_IDENT]
    downloads_count = mcod_metrics.dataset_downloads[CANONICAL_DATASET_EXT_IDENT]

    return {
        "id": CANONICAL_DATASET_INT_ID,
        "type": "dataset",
        "attributes": {
            "ext_ident": CANONICAL_DATASET_EXT_IDENT,
            "slug": "krajowy-rejestr-aed-polska",
            "title": "Krajowy Rejestr AED — Ogólnopolski Wykaz Automatycznych Defibrylatorów Zewnętrznych",
            "notes": (
                f"Ujednolicony, ogólnopolski zbiór danych o lokalizacji i dostępności defibrylatorów AED "
                f"({total_records} zweryfikowanych punktów z deduplikacją przestrzenną 25 m)."
            ),
            "license_chosen": "CC0 1.0",
            "license_name": "CC0 1.0 Universal",
            "update_frequency": "Codziennie",
            "has_dynamic_data": True,
            "has_high_value_data": True,
            "has_high_value_data_from_ec_list": True,
            "has_research_data": False,
            "openness_score": 4,
            "views_count": views_count,
            "downloads_count": downloads_count,
            "likes_count": combined_likes,
            "dataset_likes_count": ds_likes,
            "aed_likes_count": aed_likes_total,
            "is_liked_by_current_user": is_liked,
            "records_count": total_records,
            "modified": max_dt.isoformat(),
            "categories": [
                {"id": "HEAL", "code": "HEAL", "title": "Zdrowie"},
                {"id": "GOVE", "code": "GOVE", "title": "Rząd i sektor publiczny"},
                {"id": "REGI", "code": "REGI", "title": "Regiony i miasta"},
            ],
        },
        "relationships": {
            "institution": {
                "data": {"id": "1", "type": "institution"},
                "links": {"related": f"{base_url}/api/v1/institutions/1"},
            },
            "resources": {
                "meta": {"count": 4},
                "links": {"related": f"{base_url}/api/v1/datasets/1/resources"},
            },
        },
        "links": {
            "self": f"{base_url}/api/v1/datasets/1,krajowy-rejestr-aed-polska",
        },
    }


def _build_resources_jsonapi_list(base_url: str, updated_iso: str) -> list[dict[str, Any]]:
    specs = [
        (
            "1",
            "krajowy-rejestr-aed-geojson",
            "Krajowy wykaz geoprzestrzenny AED (GeoJSON RFC 7946)",
            "GeoJSON",
            3,
            f"{base_url}/api/v1/export.geojson",
            ["map", "table"],
        ),
        (
            "2",
            "krajowy-rejestr-aed-csv",
            "Tabela krajowego rejestru AED (CSV UTF-8 z BOM)",
            "CSV",
            3,
            f"{base_url}/api/v1/export.csv",
            ["table", "chart"],
        ),
        (
            "3",
            "krajowy-rejestr-aed-jsonld",
            "Katalog semantyczny Linked Open Data AED (DCAT-AP-PL / JSON-LD)",
            "JSON-LD",
            4,
            f"{base_url}/api/v1/export.jsonld",
            ["table"],
        ),
        (
            "4",
            "wzorcowy-zakres-danych-aed-xlsx",
            "Wzorcowy zakres danych o defibrylatorach AED i szablon dla dysponentów (XLSX)",
            "XLSX",
            3,
            f"{base_url}/api/v1/standard.xlsx",
            ["table"],
        ),
    ]
    nodes: list[dict[str, Any]] = []
    for res_id, ext_id, title, fmt, stars, url, viz in specs:
        nodes.append(
            {
                "id": res_id,
                "type": "resource",
                "attributes": {
                    "ext_ident": ext_id,
                    "title": title,
                    "format": fmt,
                    "openness_score": stars,
                    "download_url": url,
                    "access_url": url,
                    "link": url,
                    "has_dynamic_data": fmt != "XLSX",
                    "has_high_value_data": True,
                    "has_high_value_data_from_ec_list": True,
                    "contains_protected_data": False,
                    "visualization_types": viz,
                    "views_count": mcod_metrics.resource_views[ext_id],
                    "downloads_count": mcod_metrics.resource_downloads[ext_id],
                    "data_date": updated_iso[:10],
                    "modified": updated_iso,
                },
                "links": {"self": url},
            }
        )
    return nodes


@router.get("/datasets")
async def list_mcod_datasets(
    request: Request,
    sort: str | None = Query(
        default=None,
        description="MCOD v2.63.0 sort parameter (e.g. -likes_count, likes_count, -views_count)",
    ),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    dane.gov.pl JSON:API v1.4 `/datasets` endpoint with `likes_count`,
    `is_liked_by_current_user`, and `sort=likes_count` support (OTD-3098..OTD-3183).
    """
    user_ident = resolve_user_ident(request)
    node = await _build_dataset_jsonapi_node(request, session, user_ident)
    items = [node]
    if sort in ("likes_count", "-likes_count"):
        items.sort(
            key=lambda d: int(d["attributes"]["likes_count"]),
            reverse=sort.startswith("-"),
        )
    return {
        "jsonapi": {"version": "1.0"},
        "meta": {
            "count": len(items),
            "api_version": settings.MCOD_API_VERSION,
            "language": getattr(request.state, "language", "pl"),
        },
        "data": items,
    }


@router.get("/datasets/{dataset_id}")
async def get_mcod_dataset_detail(
    request: Request,
    dataset_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ext_ident = _normalize_dataset_ident(dataset_id)
    if ext_ident != CANONICAL_DATASET_EXT_IDENT:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    user_ident = resolve_user_ident(request)
    node = await _build_dataset_jsonapi_node(request, session, user_ident)
    return {
        "jsonapi": {"version": "1.0"},
        "data": node,
    }


@router.get("/datasets/{dataset_id}/resources")
async def get_mcod_dataset_resources(
    request: Request,
    dataset_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ext_ident = _normalize_dataset_ident(dataset_id)
    if ext_ident != CANONICAL_DATASET_EXT_IDENT:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    max_dt = ensure_utc(
        (await session.execute(select(func.max(AED.updated_at)))).scalar_one_or_none()
    ) or datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    base_url = str(request.base_url).rstrip("/")
    resources = _build_resources_jsonapi_list(base_url, max_dt.isoformat())
    return {
        "jsonapi": {"version": "1.0"},
        "meta": {"count": len(resources)},
        "data": resources,
    }


@router.post("/datasets/{dataset_id}/likes", status_code=status.HTTP_201_CREATED)
async def add_mcod_dataset_like(
    request: Request,
    dataset_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Adds a like to a dataset (MCOD v2.63.0 OTD-3100)."""
    ext_ident = _normalize_dataset_ident(dataset_id)
    if ext_ident != CANONICAL_DATASET_EXT_IDENT:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    user_ident = resolve_user_ident(request)
    existing = (
        await session.execute(
            select(DatasetLike).where(
                DatasetLike.dataset_ext_ident == ext_ident,
                DatasetLike.user_ident == user_ident,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(DatasetLike(dataset_ext_ident=ext_ident, user_ident=user_ident))
        await session.commit()

    likes_count, is_liked = await _dataset_like_stats(session, ext_ident, user_ident)
    return {
        "data": {
            "id": CANONICAL_DATASET_INT_ID,
            "type": "dataset_like",
            "attributes": {
                "ext_ident": ext_ident,
                "likes_count": likes_count,
                "is_liked_by_current_user": is_liked,
            },
        }
    }


@router.delete("/datasets/{dataset_id}/likes", status_code=status.HTTP_204_NO_CONTENT)
async def remove_mcod_dataset_like(
    request: Request,
    dataset_id: str,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Removes a like from a dataset (MCOD v2.63.0 OTD-3101)."""
    ext_ident = _normalize_dataset_ident(dataset_id)
    if ext_ident != CANONICAL_DATASET_EXT_IDENT:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    user_ident = resolve_user_ident(request)
    await session.execute(
        delete(DatasetLike).where(
            DatasetLike.dataset_ext_ident == ext_ident,
            DatasetLike.user_ident == user_ident,
        )
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/user/likes")
async def get_user_liked_datasets(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Returns datasets and AED records liked by the current user (MCOD v2.63.0 OTD-3155)."""
    user_ident = resolve_user_ident(request)
    liked_datasets = list(
        (
            await session.execute(
                select(DatasetLike.dataset_ext_ident).where(DatasetLike.user_ident == user_ident)
            )
        ).scalars().all()
    )
    liked_aeds = [
        str(uid)
        for uid in (
            await session.execute(
                select(AEDLike.aed_id).where(AEDLike.user_ident == user_ident)
            )
        ).scalars().all()
    ]
    return {
        "user_ident": user_ident,
        "likes_count": len(liked_datasets) + len(liked_aeds),
        "liked_datasets_ids": liked_datasets,
        "liked_aeds_ids": liked_aeds,
    }


@router.get("/auth/user/dashboard")
async def get_user_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Returns user dashboard summary with likes_count and liked_datasets_ids (MCOD v2.63.0 OTD-3155)."""
    likes_data = await get_user_liked_datasets(request, session)
    total_aeds = int((await session.execute(select(func.count(AED.id)))).scalar_one() or 0)
    return {
        "data": {
            "type": "dashboard",
            "attributes": {
                **likes_data,
                "followed_datasets_count": len(likes_data["liked_datasets_ids"]),
                "total_national_aeds": total_aeds,
            },
        }
    }


@router.get("/catalog.{rdf_format}")
async def get_dcat_catalog_with_format(
    request: Request,
    rdf_format: str,
    session: AsyncSession = Depends(get_db),
) -> Response:
    row = (
        await session.execute(select(func.count(AED.id), func.max(AED.updated_at)))
    ).one()
    total_records = int(row[0] or 0)
    max_dt = ensure_utc(row[1]) or datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    base_url = str(request.base_url).rstrip("/")

    fmt = rdf_format.lower().strip(".")
    if fmt not in ("jsonld", "ttl", "turtle", "xml", "rdf", "nt", "ntriples"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported RDF format: {rdf_format}. Use jsonld, ttl, xml, or nt.",
        )

    body, media_type = generate_dcat_ap_pl_catalog_rdf(
        base_url=base_url,
        total_records=total_records,
        updated_iso=max_dt.isoformat(),
        rdf_format=fmt,
    )
    return Response(content=body, media_type=media_type)


@router.get("/catalog")
async def get_dcat_catalog(
    request: Request,
    format: str | None = Query(default=None, description="Optional RDF format: jsonld, ttl, xml, nt"),
    session: AsyncSession = Depends(get_db),
) -> Response:
    fmt = format
    if not fmt:
        accept = request.headers.get("accept", "").lower()
        if "text/turtle" in accept or "application/x-turtle" in accept:
            fmt = "ttl"
        elif "application/rdf+xml" in accept:
            fmt = "xml"
        elif "application/n-triples" in accept:
            fmt = "nt"
        else:
            fmt = "jsonld"
    return await get_dcat_catalog_with_format(request, fmt, session)


@router.get("/catalog/dcat_ap/spec")
async def get_dcat_ap_spec(request: Request) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    return {
        "profile": "DCAT-AP 2.1.0",
        "shacl_shapes_version": "2.1.0",
        "namespaces": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
            "foaf": "http://xmlns.com/foaf/0.1/",
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "locn": "http://www.w3.org/ns/locn#",
            "gsp": "http://www.opengis.net/ont/geosparql#",
        },
        "endpoints": [
            f"{base_url}/api/v1/catalog",
            f"{base_url}/api/v1/catalog.ttl",
            f"{base_url}/api/v1/catalog.xml",
            f"{base_url}/api/v1/catalog.jsonld",
            f"{base_url}/api/v1/export.jsonld",
        ],
    }


@router.get("/catalog/dcat_ap_pl/spec")
async def get_dcat_ap_pl_spec(request: Request) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    spec = await get_dcat_ap_spec(request)
    spec["profile"] = "DCAT-AP-PL (Polski Profil DCAT-AP dane.gov.pl)"
    spec["namespaces"]["dcatappl"] = "https://api.dane.gov.pl/ns/dcatappl#"
    spec["vocabularies"] = {
        "openness-score": f"{base_url}/api/v1/vocab/openness-score",
        "special-sign": f"{base_url}/api/v1/vocab/special-sign",
    }
    return spec


@router.get("/vocab/openness-score")
async def get_vocab_openness_score(request: Request) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    vocab_url = f"{base_url}/api/v1/vocab/openness-score"
    return {
        "@context": {
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "dct": "http://purl.org/dc/terms/",
        },
        "@id": vocab_url,
        "@type": "skos:ConceptScheme",
        "version": "2022.05.01-0",
        "label_pl": "Poziom otwartości",
        "label_en": "Openness score",
        "entries": {
            k: {**v, "url": f"{vocab_url}/{k}"} for k, v in OPENNESS_SCORE_VOCAB.items()
        },
    }


@router.get("/vocab/openness-score/{entry_name}")
async def get_vocab_entry_openness_score(request: Request, entry_name: str) -> dict[str, Any]:
    entry = OPENNESS_SCORE_VOCAB.get(entry_name)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"openness-score doesn't have '{entry_name}' entry.",
        )
    base_url = str(request.base_url).rstrip("/")
    vocab_url = f"{base_url}/api/v1/vocab/openness-score"
    return {
        "@context": {"skos": "http://www.w3.org/2004/02/skos/core#"},
        "@id": f"{vocab_url}/{entry_name}",
        "@type": "skos:Concept",
        "skos:inScheme": vocab_url,
        **entry,
        "url": f"{vocab_url}/{entry_name}",
    }


@router.get("/vocab/special-sign")
async def get_vocab_special_sign(request: Request) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    vocab_url = f"{base_url}/api/v1/vocab/special-sign"
    return {
        "@context": {"skos": "http://www.w3.org/2004/02/skos/core#"},
        "@id": vocab_url,
        "@type": "skos:ConceptScheme",
        "label_pl": "Znaki umowne",
        "label_en": "Special signs",
        "entries": SPECIAL_SIGN_VOCAB,
    }


@router.get("/vocab/special-sign/{entry_name}")
async def get_vocab_entry_special_sign(entry_name: str) -> dict[str, Any]:
    for sign, data in SPECIAL_SIGN_VOCAB.items():
        if entry_name in (sign, data["id"]):
            return {"@type": "skos:Concept", **data}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"special-sign doesn't have '{entry_name}' entry.",
    )


@router.get("/reports/brokenlinks")
async def get_broken_links_report_summary(
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Mirrors dane.gov.pl's `/reports/brokenlinks` endpoint (`mcod/reports/`),
    reporting link & ingestion health across all external and municipal AED sources.
    """
    data = await get_broken_links_report_data(session)
    rows = data["data"]
    broken_count = sum(1 for r in rows if r["attributes"]["is_broken"])
    return {
        "meta": {
            "total_checked_resources": len(rows),
            "healthy_resources": len(rows) - broken_count,
            "broken_resources": broken_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "data": rows,
    }


@router.get("/reports/brokenlinks/data")
async def get_broken_links_report_data(
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    runs = (
        await session.execute(select(IngestionRun).order_by(IngestionRun.started_at.desc()))
    ).scalars().all()
    latest_by_source: dict[str, IngestionRun] = {}
    for r in runs:
        if r.source_name not in latest_by_source:
            latest_by_source[r.source_name] = r

    report_rows: list[dict[str, Any]] = []
    for item in CANONICAL_DANE_GOV_RESOURCES:
        muni_run = latest_by_source.get("dane_gov_municipal")
        is_broken = bool(muni_run and muni_run.status == "failed")
        report_rows.append(
            {
                "id": item["id"],
                "type": "brokenlinks_report_item",
                "attributes": {
                    "title": item["title"],
                    "institution": item["institution"],
                    "url": item["download_url"],
                    "format": item["format"],
                    "http_status": 502 if is_broken else 200,
                    "is_broken": is_broken,
                    "last_checked_at": (
                        ensure_utc(muni_run.finished_at or muni_run.started_at).isoformat()
                        if muni_run
                        else datetime.now(timezone.utc).isoformat()
                    ),
                },
            }
        )
    return {"data": report_rows}


@router.get("/dga-aggregated")
async def get_dga_aggregated_info(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Mirrors dane.gov.pl's `/dga-aggregated` (Data Governance Act Information Point)
    confirming public domain / non-protected status of the AED registry.
    """
    total_aeds = int((await session.execute(select(func.count(AED.id)))).scalar_one() or 0)
    base_url = str(request.base_url).rstrip("/")
    return {
        "data": {
            "id": "dga-krajowy-rejestr-aed",
            "type": "dga_aggregated",
            "attributes": {
                "contains_protected_data": False,
                "license": "CC0 1.0",
                "high_value_dataset_category": "Mobility / Geospatial / Health & Emergency",
                "total_records": total_aeds,
                "harvester_xml_url": f"{base_url}/api/v1/harvester/dane-gov.xml",
                "harvester_md5_url": f"{base_url}/api/v1/harvester/dane-gov.md5",
                "dcat_ap_pl_catalog_url": f"{base_url}/api/v1/catalog",
            },
        }
    }


@router.get("/cluster/health")
async def get_mcod_cluster_health(
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Mirrors dane.gov.pl's `/cluster/health` with SlowSQLMiddleware (OTD-3073) diagnostics.
    """
    await session.execute(select(func.count(AED.id)))
    return {
        "status": "green",
        "api_version": settings.MCOD_API_VERSION,
        "database_dialect": "postgresql+postgis" if settings.is_postgres else "sqlite+spatial",
        "slow_sql_logging_enabled": settings.SLOW_SQL_LOGGING_ENABLED,
        "slow_sql_threshold_seconds": settings.SLOW_SQL_THRESHOLD_SECONDS,
        "slow_sql_total_detected": mcod_metrics.slow_sql_total,
        "recent_slow_sql_events": list(mcod_metrics.slow_sql_events),
    }


@router.get("/metrics")
async def get_prometheus_metrics_v1(
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Prometheus `/api/v1/metrics` endpoint (MCOD v2.63.0 OTD-3073)."""
    total_aeds = int((await session.execute(select(func.count(AED.id)))).scalar_one() or 0)
    aed_likes = int((await session.execute(select(func.count(AEDLike.id)))).scalar_one() or 0)
    ds_likes = int((await session.execute(select(func.count(DatasetLike.id)))).scalar_one() or 0)
    active_sources = int(
        (
            await session.execute(select(func.count(func.distinct(AEDSourceRecord.source_name))))
        ).scalar_one()
        or 0
    )
    text_payload = mcod_metrics.render_prometheus_text(
        total_aeds=total_aeds,
        total_likes=aed_likes + ds_likes,
        active_sources=active_sources,
    )
    return Response(
        content=text_payload.encode("utf-8"),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
