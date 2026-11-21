import { docsUrl } from "../../api/client";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import { ContrastIcon, CrosshairIcon, ExternalLinkIcon } from "../icons/Icons";
import { PolishCoatOfArms } from "../icons/PolishCoatOfArms";

export type AppTab = "map" | "harvester" | "submit" | "campaign";
export type FontScale = "md" | "lg" | "xl";

interface TopBarProps {
  locale: Locale;
  onLocaleChange: (locale: Locale) => void;
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  onLocateNearest: () => void;
  isLocating: boolean;
  highContrast: boolean;
  onToggleHighContrast: () => void;
  fontScale: FontScale;
  onFontScaleChange: (scale: FontScale) => void;
}

export function TopBar({
  locale,
  onLocaleChange,
  activeTab,
  onTabChange,
  onLocateNearest,
  isLocating,
  highContrast,
  onToggleHighContrast,
  fontScale,
  onFontScaleChange,
}: TopBarProps) {
  const t = TRANSLATIONS[locale];
  const tabs: { id: AppTab; label: string }[] = [
    { id: "map", label: t.nav.map },
    { id: "harvester", label: t.nav.harvester },
    { id: "submit", label: t.nav.submit },
    { id: "campaign", label: t.nav.campaign },
  ];

  return (
    <header className="w-full bg-[var(--bg-canvas)] shrink-0 z-30">
      {/* Band 1: Official gov.pl Utility, Language & Accessibility Strip */}
      <div className="bg-[var(--bg-surface)] border-b border-[var(--border-hairline)] px-3 sm:px-4 py-1.5">
        <div className="max-w-[1440px] mx-auto flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2">
            <PolishCoatOfArms className="h-6 w-auto shrink-0" />
            <span className="font-[var(--font-display)] font-extrabold text-sm text-[var(--ink-primary)] tracking-tight">
              gov.pl
            </span>
            <span className="text-[var(--border-input)] select-none" aria-hidden="true">
              |
            </span>
            <span className="text-[var(--ink-secondary)]">{t.serviceName}</span>
          </div>

          <div className="flex flex-wrap items-center gap-3 sm:gap-4">
            <div
              role="group"
              aria-label="Language switcher"
              className="inline-flex items-center border border-[var(--border-hairline)] rounded-[2px] overflow-hidden bg-[var(--bg-canvas)]"
            >
              <button
                type="button"
                onClick={() => onLocaleChange("pl")}
                aria-pressed={locale === "pl"}
                className={`px-2 py-0.5 text-xs font-semibold cursor-pointer ${
                  locale === "pl"
                    ? "bg-[var(--gov-blue)] text-[var(--gov-blue-ink)]"
                    : "text-[var(--ink-primary)] hover:bg-[var(--bg-surface)]"
                }`}
              >
                PL
              </button>
              <button
                type="button"
                onClick={() => onLocaleChange("en")}
                aria-pressed={locale === "en"}
                className={`px-2 py-0.5 text-xs font-semibold border-l border-[var(--border-hairline)] cursor-pointer ${
                  locale === "en"
                    ? "bg-[var(--gov-blue)] text-[var(--gov-blue-ink)]"
                    : "text-[var(--ink-primary)] hover:bg-[var(--bg-surface)]"
                }`}
              >
                EN
              </button>
            </div>

            <div role="group" aria-label={t.textSize} className="flex items-center gap-1">
              <span className="hidden sm:inline text-[var(--ink-secondary)] mr-0.5">
                {t.textSize}
              </span>
              {(
                [
                  { id: "md", label: "A", title: "100%" },
                  { id: "lg", label: "A+", title: "120%" },
                  { id: "xl", label: "A++", title: "140%" },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onFontScaleChange(opt.id)}
                  aria-pressed={fontScale === opt.id}
                  title={opt.title}
                  className={`px-1.5 py-0.5 rounded-[2px] font-semibold cursor-pointer ${
                    fontScale === opt.id
                      ? "bg-[var(--gov-blue)] text-[var(--gov-blue-ink)]"
                      : "text-[var(--ink-primary)] hover:underline"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={onToggleHighContrast}
              aria-pressed={highContrast}
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[2px] border cursor-pointer transition-colors ${
                highContrast
                  ? "bg-[var(--gov-blue)] text-[var(--gov-blue-ink)] border-[var(--gov-blue)] font-semibold"
                  : "bg-[var(--bg-canvas)] text-[var(--ink-primary)] border-[var(--border-hairline)] hover:border-[var(--gov-blue)]"
              }`}
            >
              <ContrastIcon className="w-3.5 h-3.5" />
              <span>{t.highContrast}</span>
            </button>

            <a
              href="https://dane.gov.pl"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden md:inline-flex items-center gap-1 text-[var(--gov-blue)] hover:underline font-medium"
            >
              <span>dane.gov.pl</span>
              <ExternalLinkIcon className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>

      {/* Band 2: Official Ministerial Masthead (Clean 1px rules, zero thick highlighters or square boxes) */}
      <div className="bg-[var(--bg-canvas)] px-3 sm:px-4 py-4 border-b border-[var(--border-hairline)]">
        <div className="max-w-[1440px] mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <button
            type="button"
            onClick={() => onTabChange("map")}
            className="flex items-center gap-3.5 text-left cursor-pointer rounded-[2px]"
          >
            <PolishCoatOfArms className="h-12 sm:h-14 w-auto shrink-0" />
            <span
              className="w-px h-11 bg-[var(--border-hairline)] shrink-0"
              aria-hidden="true"
            />
            <span className="flex flex-col">
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--ink-secondary)]">
                {t.ministryName}
              </span>
              <span className="font-[var(--font-display)] text-xl sm:text-2xl font-extrabold tracking-[-0.025em] text-[var(--ink-primary)] leading-tight">
                {t.portalTitle}
              </span>
              <span className="text-xs sm:text-sm text-[var(--ink-secondary)]">
                {t.portalSubtitle}
              </span>
            </span>
          </button>

          <button
            type="button"
            onClick={onLocateNearest}
            disabled={isLocating}
            className="h-10 px-4 rounded-[3px] bg-[var(--aed-red)] hover:bg-[var(--aed-red-hover)] disabled:opacity-60 text-[var(--aed-red-ink)] text-sm font-semibold inline-flex items-center justify-center gap-2 transition-colors cursor-pointer shrink-0 self-start sm:self-auto"
          >
            <CrosshairIcon className="w-4 h-4" />
            <span>{isLocating ? t.locatingGps : t.locateNearest}</span>
          </button>
        </div>
      </div>

      {/* Band 3: Classic WordPress Polish Government Blue Navigation Bar */}
      <nav
        aria-label="Primary portal navigation"
        className="bg-[var(--gov-blue)] border-b border-[var(--border-hairline)] px-3 sm:px-4"
      >
        <div className="max-w-[1440px] mx-auto flex items-stretch justify-between gap-2 overflow-x-auto">
          <div className="flex items-stretch">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => onTabChange(tab.id)}
                  aria-current={isActive ? "page" : undefined}
                  className={`px-4 py-3 text-sm whitespace-nowrap transition-colors cursor-pointer border-r border-[#FFFFFF]/15 first:border-l first:border-[#FFFFFF]/15 ${
                    isActive
                      ? "bg-[var(--gov-blue-dark)] text-[var(--gov-blue-ink)] font-bold underline underline-offset-4"
                      : "text-[var(--gov-blue-ink)] hover:bg-[var(--gov-blue-dark)] font-medium"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          <a
            href={docsUrl()}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-3 text-xs font-medium text-[var(--gov-blue-ink)] hover:bg-[var(--gov-blue-dark)] whitespace-nowrap"
          >
            <span>{t.apiDocs}</span>
            <ExternalLinkIcon className="w-3.5 h-3.5" />
          </a>
        </div>
      </nav>
    </header>
  );
}
