import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import type { AEDNearestRecord } from "../../types/aed";
import { formatDistance } from "../../utils/geo";
import { PinIcon } from "../icons/Icons";

interface FinderRailProps {
  locale: Locale;
  nearestItems: AEDNearestRecord[];
  selectedId: string | null;
  originLabel: string;
  isLoading: boolean;
  error: string | null;
  onSelectAed: (id: string) => void;
  onRetry: () => void;
}

export function FinderRail({
  locale,
  nearestItems,
  selectedId,
  originLabel,
  isLoading,
  error,
  onSelectAed,
  onRetry,
}: FinderRailProps) {
  const t = TRANSLATIONS[locale].mapView;

  return (
    <section
      aria-label={t.railTitlePrefix}
      className="border border-[var(--border-hairline)] rounded-[4px] bg-[var(--bg-canvas)] overflow-hidden"
    >
      <div className="px-4 py-3 border-b border-[var(--border-hairline)] bg-[var(--bg-surface)] flex items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-bold text-[var(--ink-primary)]">
            {t.railTitlePrefix} {originLabel}
          </h2>
          <p className="text-xs text-[var(--ink-secondary)]">{t.railSubtitle}</p>
        </div>
        <span className="px-2.5 py-1 rounded-[3px] bg-[var(--bg-canvas)] border border-[var(--border-hairline)] text-xs font-bold text-[var(--ink-primary)] shrink-0">
          {nearestItems.length} {t.foundSuffix}
        </span>
      </div>

      <div className="max-h-[500px] overflow-y-auto divide-y divide-[var(--border-hairline)]">
        {error && (
          <div className="p-4 bg-[var(--bg-urgent)] space-y-2">
            <p className="text-sm font-semibold text-[var(--aed-red)]">{t.loadError}</p>
            <p className="text-xs text-[var(--ink-secondary)]">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="px-3 py-1.5 rounded-[3px] text-xs font-semibold border border-[var(--gov-blue)] bg-[var(--bg-canvas)] text-[var(--gov-blue)] hover:bg-[var(--bg-callout)] cursor-pointer"
            >
              {t.tryAgain}
            </button>
          </div>
        )}

        {isLoading && nearestItems.length === 0 && (
          <div className="p-4 space-y-3">
            {[1, 2, 3, 4].map((row) => (
              <div
                key={row}
                className="p-4 border border-[var(--border-hairline)] bg-[var(--bg-surface)] rounded-[3px] space-y-2"
              >
                <div className="h-3.5 w-28 bg-[var(--border-hairline)]" />
                <div className="h-4 w-4/5 bg-[var(--border-hairline)]" />
                <div className="h-3 w-1/2 bg-[var(--border-hairline)]" />
              </div>
            ))}
          </div>
        )}

        {!isLoading && !error && nearestItems.length === 0 && (
          <div className="p-6 text-center space-y-1.5">
            <p className="text-sm font-semibold text-[var(--ink-primary)]">
              {t.noResultsTitle}
            </p>
            <p className="text-xs text-[var(--ink-secondary)]">{t.noResultsDesc}</p>
          </div>
        )}

        {nearestItems.map((aed) => {
          const isSelected = aed.id === selectedId;
          const isOutOfService = aed.status === "out_of_service";
          return (
            <button
              key={aed.id}
              type="button"
              onClick={() => onSelectAed(aed.id)}
              className={`w-full text-left p-4 transition-colors cursor-pointer block ${
                isSelected
                  ? "bg-[var(--bg-callout)]"
                  : "bg-[var(--bg-canvas)] hover:bg-[var(--bg-surface)]"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[var(--ink-primary)]">
                  <span>{formatDistance(aed.distance_m)}</span>
                  <span className="text-[var(--ink-secondary)] font-normal">
                    ({aed.walking_minutes} {t.minWalk})
                  </span>
                </span>

                <span
                  className="inline-flex items-center gap-1.5 text-xs font-semibold"
                  style={{
                    color: isOutOfService ? "var(--aed-red)" : "var(--status-emerald)",
                  }}
                >
                  <span
                    className="w-2 h-2 rounded-full inline-block"
                    style={{
                      backgroundColor: isOutOfService
                        ? "var(--aed-red)"
                        : "var(--status-emerald)",
                    }}
                  />
                  <span>
                    {isOutOfService
                      ? t.statusOutOfService
                      : aed.is_24_7
                        ? t.status247
                        : aed.status === "operational"
                          ? t.statusOperational
                          : t.statusRecorded}
                  </span>
                </span>
              </div>

              <p
                className={`text-sm font-semibold leading-snug line-clamp-2 ${
                  isSelected ? "text-[var(--gov-blue)]" : "text-[var(--ink-primary)]"
                }`}
              >
                {aed.location_description || t.defaultAedTitle}
              </p>

              <div className="mt-2 flex items-center justify-between gap-2 text-xs text-[var(--ink-secondary)]">
                <span className="flex items-center gap-1.5 truncate">
                  <PinIcon className="w-3.5 h-3.5 shrink-0 text-[var(--ink-secondary)]" />
                  <span className="truncate">
                    {[aed.street_address, aed.city].filter(Boolean).join(", ") ||
                      `${aed.latitude.toFixed(5)}, ${aed.longitude.toFixed(5)}`}
                  </span>
                </span>
                <span className="shrink-0">
                  {t.qualityLabel}{" "}
                  <strong className="text-[var(--ink-primary)]">{aed.completeness_score}%</strong>
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
