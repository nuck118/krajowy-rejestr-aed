import type {
  AEDCreatePayload,
  AEDDetailRecord,
  AEDRecord,
  AEDSubmitResponse,
  AEDVerifyPayload,
  IngestionRunResponse,
  NearestAEDResponse,
  PaginatedAEDResponse,
  StatsResponse,
} from "../types/aed";

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${normalized}`;
}

export function docsUrl(): string {
  return API_BASE ? `${API_BASE}/docs` : "/docs";
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(apiUrl(path), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    throw new ApiError(
      0,
      err instanceof Error
        ? `Cannot reach backend API (${err.message}). Ensure FastAPI is running on port 8000.`
        : "Cannot reach backend API."
    );
  }

  if (!resp.ok) {
    const text = await resp.text();
    let detail = text || `HTTP ${resp.status}`;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        detail = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        detail = parsed.detail
          .map((d: { loc?: unknown[]; msg?: string }) =>
            `${Array.isArray(d.loc) ? d.loc.slice(1).join(".") : "field"}: ${d.msg ?? "invalid"}`
          )
          .join("; ");
      }
    } catch {
      // Keep raw text error
    }
    throw new ApiError(resp.status, detail);
  }

  return (await resp.json()) as T;
}

export async function fetchAeds(params: {
  city?: string;
  q?: string;
  access_type?: string;
  indoor?: boolean;
  is_24_7?: boolean;
  open_now?: boolean;
  min_completeness?: number;
  bbox?: string;
  lat?: number;
  lng?: number;
  radius?: number;
  limit?: number;
  offset?: number;
}): Promise<PaginatedAEDResponse> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      qs.set(k, String(v));
    }
  });
  return fetchJson<PaginatedAEDResponse>(`/api/v1/aeds?${qs.toString()}`);
}

export async function fetchNearestAeds(params: {
  lat: number;
  lng: number;
  radius_m?: number;
  limit?: number;
  open_now?: boolean;
  is_24_7?: boolean;
  access_type?: string;
  indoor?: boolean;
}): Promise<NearestAEDResponse> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      qs.set(k, String(v));
    }
  });
  return fetchJson<NearestAEDResponse>(`/api/v1/aeds/nearest?${qs.toString()}`);
}

export async function fetchAedDetail(id: string): Promise<AEDDetailRecord> {
  return fetchJson<AEDDetailRecord>(`/api/v1/aeds/${id}`);
}

export async function submitAed(payload: AEDCreatePayload): Promise<AEDSubmitResponse> {
  return fetchJson<AEDSubmitResponse>("/api/v1/aeds", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function verifyAed(
  aedId: string,
  payload: AEDVerifyPayload
): Promise<AEDRecord> {
  return fetchJson<AEDRecord>(`/api/v1/aeds/${aedId}/verify`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchStats(): Promise<StatsResponse> {
  return fetchJson<StatsResponse>("/api/v1/stats");
}

export async function triggerIngestionSync(
  source: "dane_gov_municipal" | "pl_geojson" | "osm_overpass",
  bbox?: string
): Promise<IngestionRunResponse> {
  return fetchJson<IngestionRunResponse>("/api/v1/ingest/run", {
    method: "POST",
    body: JSON.stringify({ source, bbox: bbox || undefined }),
  });
}

export async function uploadDatasetPayload(
  sourceName: string,
  payload: unknown
): Promise<IngestionRunResponse> {
  return fetchJson<IngestionRunResponse>("/api/v1/ingest/upload", {
    method: "POST",
    body: JSON.stringify({ source_name: sourceName, payload }),
  });
}

export async function downloadOpenDataExport(
  format: "geojson" | "csv" | "jsonld" | "xlsx" | "xml"
): Promise<void> {
  const endpointMap: Record<typeof format, { path: string; filename: string }> = {
    geojson: {
      path: "/api/v1/export.geojson",
      filename: "krajowy-rejestr-aed.geojson",
    },
    csv: {
      path: "/api/v1/export.csv",
      filename: "krajowy-rejestr-aed.csv",
    },
    jsonld: {
      path: "/api/v1/export.jsonld",
      filename: "krajowy-rejestr-aed.jsonld",
    },
    xlsx: {
      path: "/api/v1/standard.xlsx",
      filename: "Wzorcowy_Zakres_Danych_AED_dane_gov_pl.xlsx",
    },
    xml: {
      path: "/api/v1/harvester/dane-gov.xml",
      filename: "krajowy-rejestr-aed-harvester.xml",
    },
  };
  const { path, filename } = endpointMap[format];
  const resp = await fetch(apiUrl(path));
  if (!resp.ok) {
    throw new ApiError(resp.status, `Export failed with HTTP ${resp.status}`);
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function executeApiPreview(endpointPath: string): Promise<{
  status: number;
  latencyMs: number;
  headers: {
    contentType: string | null;
    etag: string | null;
    license: string | null;
  };
  body: string;
}> {
  const started = performance.now();
  const normalized = endpointPath.startsWith("/") ? endpointPath : `/${endpointPath}`;
  const resp = await fetch(apiUrl(normalized));
  const latencyMs = Math.round(performance.now() - started);
  const text = await resp.text();
  let formatted = text;
  try {
    formatted = JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    // Keep non-JSON text (e.g., CSV)
  }
  if (!resp.ok) {
    throw new ApiError(resp.status, `HTTP ${resp.status}: ${formatted}`);
  }
  return {
    status: resp.status,
    latencyMs,
    headers: {
      contentType: resp.headers.get("content-type"),
      etag: resp.headers.get("etag"),
      license: resp.headers.get("x-open-data-license"),
    },
    body: formatted,
  };
}
