import { useCallback, useEffect, useState } from "react";
import { fetchStats } from "../../api/client";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import type { StatsResponse } from "../../types/aed";
import type { AppTab } from "../layout/TopBar";
import { ExportPanel } from "./ExportPanel";
import { MetricStrip } from "./MetricStrip";
import { ReconciliationTable } from "./ReconciliationTable";

interface HarvesterViewProps {
  locale: Locale;
  onNavigate?: (tab: AppTab) => void;
}

export function HarvesterView({ locale, onNavigate }: HarvesterViewProps) {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const t = TRANSLATIONS[locale].harvester;

  const loadStats = useCallback(async () => {
    setError(null);
    try {
      const res = await fetchStats();
      setStats(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load registry statistics.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  return (
    <div className="max-w-[1440px] mx-auto px-3 sm:px-4 py-5">
      <div className="bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-[4px] p-4 sm:p-6 space-y-7">
        <div className="space-y-3 pb-6 border-b border-[var(--border-hairline)]">
          <nav
            aria-label="Breadcrumb"
            className="text-xs text-[var(--ink-secondary)] flex flex-wrap items-center gap-1.5"
          >
            <button
              type="button"
              onClick={() => onNavigate?.("map")}
              className="text-[var(--gov-blue)] hover:underline cursor-pointer"
            >
              {t.breadcrumbHome}
            </button>
            <span aria-hidden="true">/</span>
            <span>{t.breadcrumbSection}</span>
            <span aria-hidden="true">/</span>
            <span className="text-[var(--ink-primary)] font-semibold">
              {t.breadcrumbCurrent}
            </span>
          </nav>

          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div className="space-y-1.5">
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--ink-primary)]">
                {t.heading}
              </h1>
              <p className="text-sm sm:text-base text-[var(--ink-secondary)] max-w-3xl leading-relaxed">
                {t.intro}
              </p>
            </div>
            <button
              type="button"
              onClick={() => void loadStats()}
              className="h-9 px-3.5 rounded-[3px] border border-[var(--border-input)] hover:border-[var(--gov-blue)] bg-[var(--bg-canvas)] text-xs font-semibold text-[var(--gov-blue)] cursor-pointer self-start sm:self-auto shrink-0"
            >
              {t.refresh}
            </button>
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="border border-[var(--aed-red)] rounded-[3px] bg-[var(--bg-urgent)] p-4 flex items-center justify-between gap-4"
          >
            <div className="text-sm text-[var(--aed-red)]">{error}</div>
            <button
              type="button"
              onClick={() => void loadStats()}
              className="px-3.5 py-1.5 rounded-[3px] border border-[var(--gov-blue)] bg-[var(--bg-canvas)] text-xs font-semibold text-[var(--gov-blue)] cursor-pointer"
            >
              {t.retry}
            </button>
          </div>
        )}

        {loading && !stats && (
          <div
            role="status"
            aria-live="polite"
            className="border border-[var(--border-hairline)] rounded-[3px] bg-[var(--bg-surface)] p-8 text-center text-sm text-[var(--ink-secondary)]"
          >
            {t.loading}
          </div>
        )}

        {stats && (
          <>
            <MetricStrip locale={locale} stats={stats} />
            <ExportPanel locale={locale} />
            <section
              aria-label={t.standardCalloutTitle}
              className="border border-[var(--border-hairline)] rounded-[3px] bg-[var(--bg-callout)] p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <h2 className="text-sm font-bold text-[var(--ink-primary)]">
                  {t.standardCalloutTitle}
                </h2>
                <p className="text-xs text-[var(--ink-secondary)] max-w-3xl leading-relaxed">
                  {t.standardCalloutBody}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onNavigate?.("campaign")}
                className="h-9 px-4 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-[var(--gov-blue-ink)] text-xs font-semibold cursor-pointer shrink-0 self-start sm:self-center"
              >
                {t.standardCalloutBtn}
              </button>
            </section>
            <ReconciliationTable
              locale={locale}
              sources={stats.sources}
              onIngestionComplete={loadStats}
            />
          </>
        )}
      </div>
    </div>
  );
}
