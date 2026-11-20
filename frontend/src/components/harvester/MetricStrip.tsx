import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import type { StatsResponse } from "../../types/aed";

interface MetricStripProps {
  locale: Locale;
  stats: StatsResponse;
}

export function MetricStrip({ locale, stats }: MetricStripProps) {
  const m = TRANSLATIONS[locale].harvester.metrics;
  const cards = [
    {
      label: m.totalTitle,
      value: stats.total_unified_aeds.toLocaleString("en-US"),
      subtext: `${stats.standard_compliant_count.toLocaleString("en-US")} ${m.totalSubSuffix}`,
    },
    {
      label: m.mergedTitle,
      value: stats.duplicates_merged.toLocaleString("en-US"),
      subtext: m.mergedSub,
    },
    {
      label: m.sourcesTitle,
      value: String(stats.active_sources),
      subtext: m.sourcesSub,
    },
    {
      label: m.compTitle,
      value: `${stats.national_completeness_avg.toFixed(1)}%`,
      subtext: `${stats.minimum_harvestable_count.toLocaleString("en-US")} ${m.compSubSuffix}`,
    },
  ];

  return (
    <section
      aria-label={m.totalTitle}
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 border border-[var(--border-hairline)] rounded-[3px] bg-[var(--bg-surface)] divide-y sm:divide-y-0 sm:divide-x divide-[var(--border-hairline)]"
    >
      {cards.map((card) => (
        <div key={card.label} className="p-5 space-y-1.5">
          <div className="text-xs font-semibold text-[var(--ink-secondary)]">
            {card.label}
          </div>
          <div className="text-3xl font-bold tracking-tight text-[var(--ink-primary)]">
            {card.value}
          </div>
          <div className="text-xs text-[var(--ink-secondary)] leading-snug">
            {card.subtext}
          </div>
        </div>
      ))}
    </section>
  );
}
