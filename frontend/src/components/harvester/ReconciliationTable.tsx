import { useRef, useState, type ChangeEvent } from "react";
import { triggerIngestionSync, uploadDatasetPayload } from "../../api/client";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import type { IngestionRunResponse, SourceReconciliationRow } from "../../types/aed";
import { RefreshIcon } from "../icons/Icons";

interface ReconciliationTableProps {
  locale: Locale;
  sources: SourceReconciliationRow[];
  onIngestionComplete: () => Promise<void>;
}

const SYNCABLE_SOURCES = new Set(["dane_gov_municipal", "pl_geojson", "osm_overpass"]);

export function ReconciliationTable({
  locale,
  sources,
  onIngestionComplete,
}: ReconciliationTableProps) {
  const [overpassBbox, setOverpassBbox] = useState("53.08,17.92,53.17,18.12");
  const [uploadSourceName, setUploadSourceName] = useState("municipal_upload");
  const [runningSource, setRunningSource] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<IngestionRunResponse | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const t = TRANSLATIONS[locale].harvester;

  const handleSync = async (
    sourceName: "dane_gov_municipal" | "pl_geojson" | "osm_overpass"
  ) => {
    setRunningSource(sourceName);
    setActionError(null);
    try {
      const res = await triggerIngestionSync(
        sourceName,
        sourceName === "osm_overpass" ? overpassBbox.trim() : undefined
      );
      setLastRun(res);
      await onIngestionComplete();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setRunningSource(null);
    }
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setRunningSource("upload");
    setActionError(null);
    try {
      const rawText = await file.text();
      const parsed = JSON.parse(rawText) as unknown;
      const sourceId = uploadSourceName.trim() || file.name.replace(/\.[^.]+$/, "");
      const res = await uploadDatasetPayload(sourceId, parsed);
      setLastRun(res);
      await onIngestionComplete();
    } catch (err) {
      setActionError(
        err instanceof Error
          ? err.message
          : "Failed to parse or ingest uploaded JSON/GeoJSON file."
      );
    } finally {
      setRunningSource(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  return (
    <section className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-[var(--ink-primary)]">
            {t.tableHeading}
          </h2>
          <p className="text-sm text-[var(--ink-secondary)] mt-1">{t.tableIntro}</p>
        </div>

        <div className="flex items-center border border-[var(--border-input)] rounded-[3px] bg-[var(--bg-canvas)] h-9 overflow-hidden self-start md:self-auto">
          <span className="px-2.5 text-xs font-medium text-[var(--ink-secondary)] border-r border-[var(--border-hairline)] bg-[var(--bg-surface)] h-full flex items-center">
            {t.regionLabel}
          </span>
          <input
            type="text"
            value={overpassBbox}
            onChange={(e) => setOverpassBbox(e.target.value)}
            aria-label={t.regionLabel}
            className="w-44 px-2.5 font-mono text-xs text-[var(--ink-primary)] bg-transparent focus:outline-none"
          />
          <button
            type="button"
            onClick={() => setOverpassBbox("53.08,17.92,53.17,18.12")}
            className="px-2 h-full text-xs font-medium text-[var(--gov-blue)] hover:bg-[var(--bg-callout)] border-l border-[var(--border-hairline)] cursor-pointer"
          >
            Bydgoszcz
          </button>
          <button
            type="button"
            onClick={() => setOverpassBbox("52.16,20.92,52.28,21.08")}
            className="px-2 h-full text-xs font-medium text-[var(--gov-blue)] hover:bg-[var(--bg-callout)] border-l border-[var(--border-hairline)] cursor-pointer"
          >
            Warszawa
          </button>
        </div>
      </div>

      {lastRun && (
        <div className="p-3.5 border border-[var(--status-emerald)] rounded-[3px] bg-[var(--bg-surface)] flex flex-wrap items-center justify-between gap-2 text-sm">
          <div className="text-[var(--ink-primary)]">
            {t.syncSuccessPrefix}{" "}
            <strong className="font-mono text-xs">{lastRun.source_name}</strong>:{" "}
            {t.fetched} <strong>{lastRun.records_fetched}</strong>, {t.valid}{" "}
            <strong>{lastRun.records_valid}</strong>, {t.inserted}{" "}
            <strong>{lastRun.records_inserted}</strong>, {t.merged}{" "}
            <strong className="text-[var(--status-emerald)]">
              {lastRun.duplicates_merged}
            </strong>{" "}
            ({lastRun.duration_ms} ms).
          </div>
          <button
            type="button"
            onClick={() => setLastRun(null)}
            className="text-xs font-medium text-[var(--gov-blue)] hover:underline cursor-pointer"
          >
            {t.dismiss}
          </button>
        </div>
      )}

      {actionError && (
        <div className="p-3 border border-[var(--aed-red)] rounded-[3px] bg-[var(--bg-urgent)] text-sm text-[var(--aed-red)]">
          {actionError}
        </div>
      )}

      <div className="border border-[var(--border-hairline)] rounded-[3px] overflow-x-auto bg-[var(--bg-canvas)]">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="border-b border-[var(--border-hairline)] bg-[var(--bg-surface)] text-xs font-semibold text-[var(--ink-secondary)]">
              <th className="py-3 px-4">{t.colSource}</th>
              <th className="py-3 px-4">{t.colTrust}</th>
              <th className="py-3 px-4 text-right">{t.colFetched}</th>
              <th className="py-3 px-4 text-right">{t.colValid}</th>
              <th className="py-3 px-4 text-right">{t.colPassRate}</th>
              <th className="py-3 px-4 text-right">{t.colMerged}</th>
              <th className="py-3 px-4">{t.colLastSync}</th>
              <th className="py-3 px-4">{t.colStatus}</th>
              <th className="py-3 px-4 text-right">{t.colAction}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-hairline)]">
            {sources.map((row) => {
              const canSync = SYNCABLE_SOURCES.has(row.source_name);
              const isBusy = runningSource === row.source_name;
              const labelInfo =
                t.sourceLabels[row.source_name as keyof typeof t.sourceLabels];
              return (
                <tr key={row.source_name} className="hover:bg-[var(--bg-surface)]">
                  <td className="py-3 px-4">
                    <div className="font-semibold text-[var(--ink-primary)]">
                      {labelInfo ? labelInfo.title : row.source_name}
                    </div>
                    <div className="text-xs text-[var(--ink-secondary)] mt-0.5">
                      {labelInfo ? `${labelInfo.subtitle} (` : "("}
                      <code className="font-mono text-[11px]">{row.source_name}</code>)
                    </div>
                  </td>
                  <td className="py-3 px-4 text-xs font-medium text-[var(--ink-secondary)]">
                    Tier {row.trust_tier}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-right text-[var(--ink-primary)]">
                    {row.raw_records.toLocaleString("en-US")}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-right text-[var(--ink-primary)]">
                    {row.valid_records.toLocaleString("en-US")}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-right text-[var(--ink-primary)]">
                    {row.raw_records > 0 ? `${row.pass_rate_pct.toFixed(1)}%` : "N/A"}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-right text-[var(--status-emerald)] font-semibold">
                    {row.duplicates_merged.toLocaleString("en-US")}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-[var(--ink-secondary)] whitespace-nowrap">
                    {row.last_sync_at
                      ? new Date(row.last_sync_at).toISOString().replace("T", " ").slice(0, 19)
                      : t.notSynced}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className="px-2 py-0.5 text-xs font-medium rounded-[2px] border inline-block"
                      style={{
                        borderColor:
                          row.status === "completed"
                            ? "var(--status-emerald)"
                            : row.status === "failed"
                              ? "var(--aed-red)"
                              : "var(--border-hairline)",
                        color:
                          row.status === "completed"
                            ? "var(--status-emerald)"
                            : row.status === "failed"
                              ? "var(--aed-red)"
                              : "var(--ink-secondary)",
                      }}
                    >
                      {row.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right whitespace-nowrap">
                    {canSync ? (
                      <button
                        type="button"
                        disabled={runningSource !== null}
                        onClick={() =>
                          void handleSync(
                            row.source_name as
                              | "dane_gov_municipal"
                              | "pl_geojson"
                              | "osm_overpass"
                          )
                        }
                        className="inline-flex items-center gap-1.5 h-8 px-3 rounded-[3px] border border-[var(--gov-blue)] bg-[var(--bg-canvas)] hover:bg-[var(--bg-callout)] text-xs font-semibold text-[var(--gov-blue)] cursor-pointer disabled:opacity-50"
                      >
                        <RefreshIcon className="w-3.5 h-3.5" />
                        <span>{isBusy ? t.syncingBtn : t.syncBtn}</span>
                      </button>
                    ) : (
                      <span className="text-xs text-[var(--ink-secondary)]">
                        {t.apiUploadLabel}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="border border-[var(--border-hairline)] rounded-[3px] bg-[var(--bg-surface)] p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <h3 className="text-sm font-bold text-[var(--ink-primary)]">{t.uploadTitle}</h3>
          <p className="text-xs text-[var(--ink-secondary)]">{t.uploadDesc}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <input
            type="text"
            value={uploadSourceName}
            onChange={(e) => setUploadSourceName(e.target.value)}
            placeholder="source_identifier"
            aria-label="Uploaded source identifier"
            className="h-9 w-40 px-3 rounded-[3px] font-mono text-xs bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
          />
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,.geojson,application/json,application/geo+json"
            onChange={(e) => void handleFileChange(e)}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={runningSource !== null}
            className="h-9 px-4 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] disabled:opacity-50 text-[var(--gov-blue-ink)] text-xs font-semibold cursor-pointer transition-colors"
          >
            {runningSource === "upload" ? t.uploadingBtn : t.uploadBtn}
          </button>
        </div>
      </div>
    </section>
  );
}
