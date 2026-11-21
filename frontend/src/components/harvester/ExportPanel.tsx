import { useEffect, useState, type FormEvent } from "react";
import {
  apiUrl,
  docsUrl,
  downloadOpenDataExport,
  executeApiPreview,
} from "../../api/client";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import {
  CheckIcon,
  CopyIcon,
  DownloadIcon,
  ExternalLinkIcon,
} from "../icons/Icons";

interface ExportPanelProps {
  locale: Locale;
}

interface ExportFormatItem {
  id: "geojson" | "csv" | "jsonld" | "xlsx" | "xml";
  badge: string;
  label: string;
  description: string;
  standard: string;
  path: string;
}

export function ExportPanel({ locale }: ExportPanelProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const t = TRANSLATIONS[locale].harvester;

  const exportFormats: ExportFormatItem[] = [
    {
      id: "geojson",
      badge: "GEOJSON",
      label: t.formats.geojson.label,
      description: t.formats.geojson.desc,
      standard: t.formats.geojson.std,
      path: "/api/v1/export.geojson",
    },
    {
      id: "csv",
      badge: "CSV",
      label: t.formats.csv.label,
      description: t.formats.csv.desc,
      standard: t.formats.csv.std,
      path: "/api/v1/export.csv",
    },
    {
      id: "jsonld",
      badge: "JSON-LD",
      label: t.formats.jsonld.label,
      description: t.formats.jsonld.desc,
      standard: t.formats.jsonld.std,
      path: "/api/v1/export.jsonld",
    },
    {
      id: "xlsx",
      badge: "XLSX",
      label: t.formats.xlsx.label,
      description: t.formats.xlsx.desc,
      standard: t.formats.xlsx.std,
      path: "/api/v1/standard.xlsx",
    },
    {
      id: "xml",
      badge: "XML",
      label: t.formats.xml.label,
      description: t.formats.xml.desc,
      standard: t.formats.xml.std,
      path: "/api/v1/harvester/dane-gov.xml",
    },
  ];

  const quickEndpoints = [
    {
      label: t.presets.radius,
      path: "/api/v1/aeds?lat=53.1235&lng=18.0084&radius=500",
    },
    {
      label: t.presets.nearest,
      path: "/api/v1/aeds/nearest?lat=53.1235&lng=18.0084&radius_m=2000&limit=5",
    },
    {
      label: t.presets.stats,
      path: "/api/v1/stats",
    },
    {
      label: t.presets.jsonld,
      path: "/api/v1/export.jsonld?limit=3",
    },
  ];

  const [endpointInput, setEndpointInput] = useState(
    "/api/v1/aeds?lat=53.1235&lng=18.0084&radius=500"
  );
  const [previewState, setPreviewState] = useState<{
    status: number | null;
    latencyMs: number | null;
    headers: {
      contentType: string | null;
      etag: string | null;
      license: string | null;
    } | null;
    body: string;
    error: string | null;
    loading: boolean;
  }>({
    status: null,
    latencyMs: null,
    headers: null,
    body: "",
    error: null,
    loading: false,
  });

  const runPreview = async (targetPath: string) => {
    setPreviewState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const res = await executeApiPreview(targetPath);
      setPreviewState({
        status: res.status,
        latencyMs: res.latencyMs,
        headers: res.headers,
        body: res.body,
        error: null,
        loading: false,
      });
    } catch (err) {
      setPreviewState({
        status: null,
        latencyMs: null,
        headers: null,
        body: "",
        error: err instanceof Error ? err.message : "Request failed",
        loading: false,
      });
    }
  };

  useEffect(() => {
    void runPreview("/api/v1/aeds?lat=53.1235&lng=18.0084&radius=500");
  }, []);

  const handleCopyUrl = async (item: ExportFormatItem) => {
    const absoluteUrl = new URL(apiUrl(item.path), window.location.origin).toString();
    try {
      await navigator.clipboard.writeText(absoluteUrl);
      setCopiedId(item.id);
      window.setTimeout(() => setCopiedId(null), 1800);
    } catch {
      setDownloadError("Clipboard access denied.");
    }
  };

  const handleDownload = async (item: ExportFormatItem) => {
    setDownloadingId(item.id);
    setDownloadError(null);
    try {
      await downloadOpenDataExport(item.id);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloadingId(null);
    }
  };

  const handlePreviewSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (endpointInput.trim()) {
      void runPreview(endpointInput.trim());
    }
  };

  return (
    <section className="space-y-8">
      <div className="space-y-3">
        <div>
          <h2 className="text-xl font-bold text-[var(--ink-primary)]">
            {t.exportsHeading}
          </h2>
          <p className="text-sm text-[var(--ink-secondary)] mt-1">{t.exportsIntro}</p>
        </div>

        {downloadError && (
          <div className="p-3 border border-[var(--aed-red)] rounded-[3px] bg-[var(--bg-urgent)] text-sm text-[var(--aed-red)]">
            {downloadError}
          </div>
        )}

        <div className="border border-[var(--border-hairline)] rounded-[3px] divide-y divide-[var(--border-hairline)] bg-[var(--bg-canvas)]">
          {exportFormats.map((item) => {
            const isCopied = copiedId === item.id;
            const isDownloading = downloadingId === item.id;
            return (
              <div
                key={item.id}
                className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="px-2 py-0.5 rounded-[2px] bg-[var(--bg-callout)] border border-[var(--border-hairline)] font-mono text-xs font-bold text-[var(--gov-blue)]">
                      {item.badge}
                    </span>
                    <h3 className="text-base font-bold text-[var(--ink-primary)]">
                      {item.label}
                    </h3>
                    <span className="text-xs text-[var(--ink-secondary)]">
                      ({item.standard})
                    </span>
                  </div>
                  <p className="text-sm text-[var(--ink-secondary)] leading-relaxed">
                    {item.description}
                  </p>
                  <div className="font-mono text-xs text-[var(--ink-primary)] pt-0.5">
                    GET {item.path}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => void handleDownload(item)}
                    disabled={isDownloading}
                    className="h-10 px-4 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] disabled:opacity-50 text-[var(--gov-blue-ink)] text-sm font-semibold inline-flex items-center gap-2 cursor-pointer transition-colors"
                  >
                    <DownloadIcon className="w-4 h-4" />
                    <span>{isDownloading ? t.downloadingBtn : t.downloadBtn}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleCopyUrl(item)}
                    className="h-10 px-3.5 rounded-[3px] border border-[var(--border-input)] hover:border-[var(--gov-blue)] bg-[var(--bg-canvas)] text-[var(--ink-primary)] text-sm font-medium inline-flex items-center gap-2 cursor-pointer"
                  >
                    {isCopied ? (
                      <>
                        <CheckIcon className="w-4 h-4 text-[var(--status-emerald)]" />
                        <span className="text-[var(--status-emerald)]">{t.copiedBtn}</span>
                      </>
                    ) : (
                      <>
                        <CopyIcon className="w-4 h-4" />
                        <span>{t.copyBtn}</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-[var(--ink-primary)]">
              {t.inspectorHeading}
            </h2>
            <p className="text-sm text-[var(--ink-secondary)] mt-1">{t.inspectorIntro}</p>
          </div>
          <a
            href={docsUrl()}
            target="_blank"
            rel="noopener noreferrer"
            className="h-9 px-3.5 rounded-[3px] border border-[var(--gov-blue)] bg-[var(--bg-canvas)] hover:bg-[var(--bg-callout)] text-sm font-semibold text-[var(--gov-blue)] inline-flex items-center gap-1.5 self-start sm:self-auto shrink-0"
          >
            <span>{t.openSwagger}</span>
            <ExternalLinkIcon className="w-4 h-4" />
          </a>
        </div>

        <div className="border border-[var(--border-hairline)] rounded-[3px] bg-[var(--bg-canvas)] overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--border-hairline)] bg-[var(--bg-surface)] flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-semibold text-[var(--ink-secondary)]">
              {t.sampleQueries}
            </span>
            <div className="flex flex-wrap gap-1.5">
              {quickEndpoints.map((preset) => (
                <button
                  key={preset.path}
                  type="button"
                  onClick={() => {
                    setEndpointInput(preset.path);
                    void runPreview(preset.path);
                  }}
                  className="px-2.5 py-1 text-xs font-medium rounded-[3px] border border-[var(--border-hairline)] bg-[var(--bg-canvas)] hover:border-[var(--gov-blue)] text-[var(--gov-blue)] cursor-pointer"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <form
            onSubmit={handlePreviewSubmit}
            className="p-3.5 border-b border-[var(--border-hairline)] flex items-stretch gap-2"
          >
            <span className="px-3 flex items-center rounded-[3px] bg-[var(--bg-surface)] border border-[var(--border-hairline)] font-mono text-xs font-semibold text-[var(--ink-primary)]">
              GET
            </span>
            <input
              type="text"
              value={endpointInput}
              onChange={(e) => setEndpointInput(e.target.value)}
              aria-label="API endpoint path"
              className="flex-1 h-10 px-3 rounded-[3px] font-mono text-xs bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
            />
            <button
              type="submit"
              disabled={previewState.loading}
              className="h-10 px-5 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] disabled:opacity-50 text-[var(--gov-blue-ink)] text-sm font-semibold cursor-pointer transition-colors"
            >
              {previewState.loading ? t.runningBtn : t.executeBtn}
            </button>
          </form>

          <div className="px-4 py-2 border-b border-[var(--border-hairline)] bg-[var(--bg-surface)] flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--ink-secondary)]">
            <div className="flex items-center gap-4 font-mono">
              <span>
                HTTP:{" "}
                <strong
                  style={{
                    color:
                      previewState.status && previewState.status < 400
                        ? "var(--status-emerald)"
                        : "var(--aed-red)",
                  }}
                >
                  {previewState.status ?? (previewState.loading ? "..." : "ERR")}
                </strong>
              </span>
              {previewState.latencyMs !== null && <span>{previewState.latencyMs} ms</span>}
            </div>
            {previewState.headers && (
              <div className="flex flex-wrap items-center gap-4 font-mono text-[11px]">
                {previewState.headers.license && (
                  <span>License: {previewState.headers.license}</span>
                )}
                {previewState.headers.etag && <span>ETag: {previewState.headers.etag}</span>}
              </div>
            )}
          </div>

          <pre className="p-4 max-h-[340px] overflow-auto bg-[var(--bg-canvas)] font-mono text-xs leading-relaxed text-[var(--ink-primary)] whitespace-pre">
            {previewState.error
              ? previewState.error
              : previewState.body || (previewState.loading ? "..." : "")}
          </pre>
        </div>
      </div>
    </section>
  );
}
