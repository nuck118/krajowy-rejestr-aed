"""
dane.gov.pl (MCOD v2.63.0) Middleware, Slow SQL Profiler, Metrics & Counter Engine.

Implements:
- SlowSQLMiddleware (OTD-3073): Logs SQL queries exceeding SLOW_SQL_THRESHOLD_SECONDS
  as structured JSON events (`event_type: "slow_sql"`, `duration`, `operation`,
  `sql_hash`, `sql`, `request_succeeded`, `user_authenticated`).
- PrometheusMiddleware (OTD-3073): Co-operates with SlowSQLMiddleware to record
  `http_requests_total`, `http_request_duration_seconds`, `http_errors_total`,
  and `falcon_db_query_duration_seconds` / `api_db_query_duration_seconds`.
- ApiVersionMiddleware: Enforces X-API-Version negotiation (1.0, 1.4) and sets
  `X-API-Version` response header.
- LocaleMiddleware: Negotiates `pl` / `en` from `?lang=` or `Accept-Language`
  and sets `Content-Language` response header.
- CounterMiddleware: Tracks view and download counters across datasets, resources,
  and AED records (`views_count`, `downloads_count`).
- DebugMiddleware: Optional `?debug=yes` diagnostic envelope.
"""

from collections import defaultdict, deque
from contextvars import ContextVar
import hashlib
import json
import logging
import re
import time
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine
from sqlalchemy import event
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings

logger = logging.getLogger("mcod-api")
slow_sql_logger = logging.getLogger("slow-sql")

SUPPORTED_LANGUAGES = ("pl", "en")
LANG_CODE_RE = re.compile(r"^[a-zA-Z]{2}(?:-[a-zA-Z]{2})?$")

_request_queries_ctx: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "mcod_request_queries", default=None
)


@event.listens_for(Engine, "before_cursor_execute")
def _before_cursor_execute(
    _conn: Any,
    _cursor: Any,
    _statement: str,
    _parameters: Any,
    context: Any,
    _executemany: bool,
) -> None:
    if context is not None:
        context._mcod_query_start_time = time.perf_counter()


@event.listens_for(Engine, "after_cursor_execute")
def _after_cursor_execute(
    _conn: Any,
    _cursor: Any,
    statement: str,
    _parameters: Any,
    context: Any,
    _executemany: bool,
) -> None:
    queries = _request_queries_ctx.get()
    if queries is None:
        return
    start = getattr(context, "_mcod_query_start_time", None)
    duration = (time.perf_counter() - start) if start is not None else 0.0
    queries.append({"sql": statement, "duration": duration})


def record_simulated_query(sql: str, duration_seconds: float) -> None:
    """Helper for testing or manual query timing injection."""
    queries = _request_queries_ctx.get()
    if queries is not None:
        queries.append({"sql": sql, "duration": float(duration_seconds)})


class MCODMetricsAndCounters:
    """In-memory Prometheus metrics & MCOD view/download counter store."""

    def __init__(self) -> None:
        self.request_count: dict[tuple[str, str, str], int] = defaultdict(int)
        self.error_count: dict[tuple[str, str, str], int] = defaultdict(int)
        self.latency_sum: dict[tuple[str, str], float] = defaultdict(float)
        self.latency_count: dict[tuple[str, str], int] = defaultdict(int)
        self.db_query_time_sum: dict[str, float] = defaultdict(float)
        self.db_query_time_count: dict[str, int] = defaultdict(int)
        self.slow_sql_events: deque[dict[str, Any]] = deque(maxlen=100)
        self.slow_sql_total: int = 0

        # MCOD CounterMiddleware state
        self.dataset_views: dict[str, int] = defaultdict(int)
        self.dataset_downloads: dict[str, int] = defaultdict(int)
        self.resource_views: dict[str, int] = defaultdict(int)
        self.resource_downloads: dict[str, int] = defaultdict(int)
        self.aed_views: dict[str, int] = defaultdict(int)

    def incr_dataset_view(self, ext_ident: str = "krajowy-rejestr-aed-polska") -> None:
        self.dataset_views[ext_ident] += 1

    def incr_resource_download(
        self,
        resource_ident: str,
        dataset_ext_ident: str = "krajowy-rejestr-aed-polska",
    ) -> None:
        self.resource_downloads[resource_ident] += 1
        self.resource_views[resource_ident] += 1
        self.dataset_downloads[dataset_ext_ident] += 1

    def render_prometheus_text(
        self,
        *,
        total_aeds: int = 0,
        total_likes: int = 0,
        active_sources: int = 0,
    ) -> str:
        lines: list[str] = [
            "# HELP http_requests_total Total HTTP requests",
            "# TYPE http_requests_total counter",
        ]
        for (method, endpoint, status_code), val in sorted(self.request_count.items()):
            lines.append(
                f'http_requests_total{{method="{method}",endpoint="{endpoint}",http_status="{status_code}"}} {val}'
            )

        lines.extend(
            [
                "# HELP http_request_duration_seconds Request latency",
                "# TYPE http_request_duration_seconds summary",
            ]
        )
        for (method, endpoint), total_lat in sorted(self.latency_sum.items()):
            cnt = self.latency_count[(method, endpoint)]
            lines.append(
                f'http_request_duration_seconds_sum{{method="{method}",endpoint="{endpoint}"}} {total_lat:.6f}'
            )
            lines.append(
                f'http_request_duration_seconds_count{{method="{method}",endpoint="{endpoint}"}} {cnt}'
            )

        lines.extend(
            [
                "# HELP http_errors_total Total HTTP 5xx errors",
                "# TYPE http_errors_total counter",
            ]
        )
        for (method, endpoint, status_code), val in sorted(self.error_count.items()):
            lines.append(
                f'http_errors_total{{method="{method}",endpoint="{endpoint}",status_code="{status_code}"}} {val}'
            )

        lines.extend(
            [
                "# HELP falcon_db_query_duration_seconds DB query duration for API requests",
                "# TYPE falcon_db_query_duration_seconds summary",
            ]
        )
        for path, total_db in sorted(self.db_query_time_sum.items()):
            cnt = self.db_query_time_count[path]
            lines.append(f'falcon_db_query_duration_seconds_sum{{path="{path}"}} {total_db:.6f}')
            lines.append(f'falcon_db_query_duration_seconds_count{{path="{path}"}} {cnt}')

        lines.extend(
            [
                "# HELP slow_sql_queries_total Total slow SQL queries exceeding threshold (OTD-3073)",
                "# TYPE slow_sql_queries_total counter",
                f"slow_sql_queries_total {self.slow_sql_total}",
                "# HELP resources_total Current number of unified AED resources",
                "# TYPE resources_total gauge",
                f'resources_total{{source="krajowy_rejestr_aed"}} {total_aeds}',
                "# HELP dataset_likes_total Current number of likes across datasets and AEDs (OTD-3096)",
                "# TYPE dataset_likes_total gauge",
                f"dataset_likes_total {total_likes}",
                "# HELP organization_total Total number of active data source organizations",
                "# TYPE organization_total gauge",
                f"organization_total {active_sources}",
            ]
        )
        return "\n".join(lines) + "\n"


mcod_metrics = MCODMetricsAndCounters()


def negotiate_language(request: Request) -> str:
    query_lang = request.query_params.get("lang")
    if query_lang and query_lang.lower() in SUPPORTED_LANGUAGES:
        return query_lang.lower()

    accept_header = request.headers.get("accept-language", "")
    for part in accept_header.split(","):
        token = part.split(";")[0].strip().lower()
        if not token or token == "*":
            continue
        if not LANG_CODE_RE.match(token):
            continue
        primary = token.split("-")[0]
        if primary in SUPPORTED_LANGUAGES:
            return primary
    return "pl"


def resolve_user_ident(request: Request) -> str:
    """Derives a deterministic user identifier from X-User-Id header, Authorization, or client IP."""
    explicit = request.headers.get("x-user-id") or request.cookies.get("mcod_user_id")
    if explicit and explicit.strip():
        return explicit.strip()[:128]
    auth = request.headers.get("authorization")
    if auth and auth.strip():
        digest = hashlib.sha256(auth.strip().encode("utf-8")).hexdigest()[:24]
        return f"auth:{digest}"
    client_host = request.client.host if request.client else "anonymous"
    return f"anon:{client_host}"[:128]


class MCODCoreMiddleware(BaseHTTPMiddleware):
    """
    Unified FastAPI middleware implementing dane.gov.pl (MCOD v2.63.0):
    - ApiVersionMiddleware (`X-API-Version` validation & header)
    - LocaleMiddleware (`Content-Language` negotiation)
    - SlowSQLMiddleware (`OTD-3073` slow query JSON logging)
    - PrometheusMiddleware (`OTD-3073` request latency, status & DB duration metrics)
    - CounterMiddleware (view & download counters)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. ApiVersionMiddleware
        supported_versions = set(settings.MCOD_SUPPORTED_API_VERSIONS)
        default_version = settings.MCOD_API_VERSION
        requested_version = request.headers.get("x-api-version", default_version).strip()
        if requested_version not in supported_versions:
            return JSONResponse(
                status_code=400,
                content={
                    "title": "Unsupported version",
                    "description": "Version provided in X-API-VERSION header is invalid.",
                },
            )

        # 2. LocaleMiddleware
        lang = negotiate_language(request)
        request.state.language = lang
        request.state.api_version = requested_version

        # 3. Start Prometheus & SlowSQL query tracking context
        start_time = time.perf_counter()
        queries: list[dict[str, Any]] = []
        token = _request_queries_ctx.set(queries)

        # Optional synthetic slow query hook for integration testing of OTD-3073
        sim_slow = request.headers.get("x-simulate-slow-sql-ms")
        if sim_slow:
            try:
                sim_sec = float(sim_slow) / 1000.0
                queries.append({"sql": "SELECT /* simulated_slow_query */ 1", "duration": sim_sec})
            except ValueError:
                pass

        req_succeeded = True
        response: Response
        try:
            response = await call_next(request)
            if response.status_code >= 500:
                req_succeeded = False
        except Exception:
            req_succeeded = False
            _request_queries_ctx.reset(token)
            elapsed = time.perf_counter() - start_time
            self._record_metrics_and_slow_sql(
                request=request,
                status_code=500,
                elapsed=elapsed,
                queries=queries,
                req_succeeded=False,
            )
            raise

        _request_queries_ctx.reset(token)
        elapsed = time.perf_counter() - start_time

        # 4. Record SlowSQLMiddleware + PrometheusMiddleware
        self._record_metrics_and_slow_sql(
            request=request,
            status_code=response.status_code,
            elapsed=elapsed,
            queries=queries,
            req_succeeded=req_succeeded,
        )

        # 5. Update CounterMiddleware view/download counters
        self._update_counters(request.url.path, response.status_code)

        # 6. Attach standard MCOD response headers
        response.headers["X-API-Version"] = requested_version
        response.headers["Content-Language"] = lang
        return response

    def _record_metrics_and_slow_sql(
        self,
        *,
        request: Request,
        status_code: int,
        elapsed: float,
        queries: list[dict[str, Any]],
        req_succeeded: bool,
    ) -> None:
        method = request.method
        path = request.url.path
        status_str = str(status_code)

        mcod_metrics.request_count[(method, path, status_str)] += 1
        mcod_metrics.latency_sum[(method, path)] += elapsed
        mcod_metrics.latency_count[(method, path)] += 1
        if not req_succeeded or status_code >= 500:
            mcod_metrics.error_count[(method, path, status_str)] += 1

        total_db_duration = sum(float(q.get("duration", 0.0)) for q in queries)
        mcod_metrics.db_query_time_sum[path] += total_db_duration
        mcod_metrics.db_query_time_count[path] += 1

        if settings.SLOW_SQL_LOGGING_ENABLED:
            threshold = float(settings.SLOW_SQL_THRESHOLD_SECONDS)
            operation = f"{method} {path}"
            user_auth = bool(
                request.headers.get("authorization") or request.headers.get("x-user-id")
            )
            for q in queries:
                duration = float(q.get("duration", 0.0))
                if duration > threshold:
                    sql_text = str(q.get("sql", ""))
                    event_payload = {
                        "event_type": "slow_sql",
                        "duration": round(duration, 3),
                        "operation": operation,
                        "sql_hash": hashlib.sha256(sql_text.encode("utf-8")).hexdigest()[:16],
                        "sql": sql_text,
                        "request_succeeded": req_succeeded,
                        "user_authenticated": user_auth,
                    }
                    mcod_metrics.slow_sql_total += 1
                    mcod_metrics.slow_sql_events.append(event_payload)
                    slow_sql_logger.warning(json.dumps(event_payload, default=str))

    def _update_counters(self, path: str, status_code: int) -> None:
        if status_code not in (200, 304):
            return
        if path.endswith("/export.geojson"):
            mcod_metrics.incr_resource_download("krajowy-rejestr-aed-geojson")
        elif path.endswith("/export.csv"):
            mcod_metrics.incr_resource_download("krajowy-rejestr-aed-csv")
        elif path.endswith("/export.jsonld"):
            mcod_metrics.incr_resource_download("krajowy-rejestr-aed-jsonld")
        elif path.endswith("/standard.xlsx"):
            mcod_metrics.incr_resource_download("wzorcowy-zakres-danych-aed-xlsx")
        elif path.startswith("/api/v1/datasets"):
            mcod_metrics.incr_dataset_view("krajowy-rejestr-aed-polska")
        elif path.startswith("/api/v1/aeds/") and path.count("/") == 4:
            aed_id = path.rsplit("/", 1)[-1]
            if aed_id not in ("nearest", "geocode", "reverse-geocode"):
                mcod_metrics.aed_views[aed_id] += 1
                mcod_metrics.incr_dataset_view("krajowy-rejestr-aed-polska")
