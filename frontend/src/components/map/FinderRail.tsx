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
        <span
          role="status"
          aria-live="polite"
          className="px-2.5 py-1 rounded-[3px] bg-[var(--bg-canvas)] border border-[var(--border-hairline)] text-xs font-bold text-[var(--ink-primary)] shrink-0"
        >
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
          const isOperational = aed.status === "operational";
          const dotColor = isOutOfService
            ? "var(--aed-red)"
            : isOperational
              ? "var(--status-emerald)"
              : "var(--ink-secondary)";
          const statusLabel = isOutOfService
            ? t.statusOutOfService
            : isOperational
              ? aed.is_24_7
                ? `${t.statusVerified} (24/7)`
                : t.statusVerified
              : aed.is_24_7
                ? `${t.statusUnverified} (24/7)`
                : t.statusUnverified;
          const envShort =
            aed.indoor === true
              ? t.indoorShort
              : aed.indoor === false
                ? t.outdoorShort
                : null;
          const fallbackParts = [envShort, t.accessShort[aed.access_type]].filter(Boolean);
          const displayTitle =
            aed.location_description ||
            [aed.street_address, aed.city].filter(Boolean).join(", ") ||
            (fallbackParts.length > 0 ? `AED (${fallbackParts.join(", ")})` : t.defaultAedTitle);
          const isRestricted = aed.access_type !== "public";
          const reachabilityBadge =
            aed.open_now === true
              ? {
                  text: locale === "pl" ? "Otwarte teraz" : "Open now",
                  color: "var(--status-emerald)",
                  bg: "var(--bg-surface)",
                }
              : aed.open_now === false
                ? {
                    text: locale === "pl" ? "Zamknięte teraz" : "Closed now",
                    color: "var(--aed-red)",
                    bg: "var(--bg-urgent)",
                  }
                : null;
          return (
            <button
              key={aed.id}
              type="button"
              onClick={() => onSelectAed(aed.id)}
              aria-pressed={isSelected}
              aria-current={isSelected ? "true" : undefined}
              className={`w-full text-left p-4 transition-colors cursor-pointer block ${
                isSelected
                  ? "bg-[var(--bg-callout)]"
                  : "bg-[var(--bg-canvas)] hover:bg-[var(--bg-surface)]"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold tabular-nums text-[var(--ink-primary)]">
                  <span>{formatDistance(aed.distance_m)}</span>
                  <span className="text-[var(--ink-secondary)] font-normal">
                    ({aed.walking_minutes} {t.minWalk})
                  </span>
                </span>

                <span
                  className="inline-flex items-center gap-1.5 text-xs font-semibold"
                  style={{ color: dotColor }}
                >
                  <span
                    aria-hidden="true"
                    className="w-2 h-2 rounded-full inline-block"
                    style={{ backgroundColor: dotColor }}
                  />
                  <span>{statusLabel}</span>
                </span>
              </div>

              <p
                className={`text-sm font-semibold leading-snug line-clamp-2 ${
                  isSelected ? "text-[var(--gov-blue)]" : "text-[var(--ink-primary)]"
                }`}
              >
                {displayTitle}
              </p>

              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] font-medium">
                {reachabilityBadge && (
                  <span
                    className="px-1.5 py-0.5 rounded-[2px] border"
                    style={{
                      color: reachabilityBadge.color,
                      borderColor: reachabilityBadge.color,
                      backgroundColor: reachabilityBadge.bg,
                    }}
                  >
                    {reachabilityBadge.text}
                  </span>
                )}
                {isRestricted && (
                  <span
                    className="px-1.5 py-0.5 rounded-[2px] border"
                    style={{
                      color: "var(--status-amber)",
                      borderColor: "var(--status-amber)",
                      backgroundColor: "var(--bg-amber)",
                    }}
                  >
                    {t.accessShort[aed.access_type]}
                  </span>
                )}
                {envShort && (
                  <span className="px-1.5 py-0.5 rounded-[2px] border border-[var(--border-hairline)] bg-[var(--bg-surface)] text-[var(--ink-secondary)]">
                    {envShort}
                  </span>
                )}
              </div>

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
