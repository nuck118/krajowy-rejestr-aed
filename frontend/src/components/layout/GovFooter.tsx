import { useState } from "react";
import { apiUrl, docsUrl } from "../../api/client";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import { CloseIcon, ExternalLinkIcon } from "../icons/Icons";
import { PolishCoatOfArms } from "../icons/PolishCoatOfArms";
import type { AppTab } from "./TopBar";

interface GovFooterProps {
  locale: Locale;
  onNavigate?: (tab: AppTab) => void;
}

export function GovFooter({ locale, onNavigate }: GovFooterProps) {
  const [showAccessibilityModal, setShowAccessibilityModal] = useState(false);
  const t = TRANSLATIONS[locale];

  return (
    <>
      <footer className="mt-10 border-t border-[var(--border-hairline)] bg-[var(--bg-canvas)]">
        <div className="max-w-[1180px] mx-auto px-4 sm:px-6 py-8 space-y-6">
          <div className="flex items-center gap-3.5 pb-5 border-b border-[var(--border-hairline)]">
            <PolishCoatOfArms className="h-11 w-auto shrink-0" />
            <div>
              <div className="text-sm font-bold text-[var(--ink-primary)]">
                {t.footer.serviceTitle}
              </div>
              <div className="text-xs text-[var(--ink-secondary)] mt-0.5">
                {t.footer.serviceSubtitle}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-sm">
            <div className="space-y-2">
              <h3 className="font-bold text-[var(--ink-primary)]">
                {t.footer.colSections}
              </h3>
              <ul className="space-y-1.5 text-[var(--gov-blue)]">
                <li>
                  <button
                    type="button"
                    onClick={() => onNavigate?.("map")}
                    className="hover:underline cursor-pointer text-left"
                  >
                    {t.nav.map}
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={() => onNavigate?.("harvester")}
                    className="hover:underline cursor-pointer text-left"
                  >
                    {t.nav.harvester}
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={() => onNavigate?.("submit")}
                    className="hover:underline cursor-pointer text-left"
                  >
                    {t.nav.submit}
                  </button>
                </li>
              </ul>
            </div>

            <div className="space-y-2">
              <h3 className="font-bold text-[var(--ink-primary)]">
                {t.footer.colFeeds}
              </h3>
              <ul className="space-y-1.5 text-[var(--gov-blue)]">
                <li>
                  <a href={apiUrl("/api/v1/export.geojson")} className="hover:underline">
                    {t.footer.feedGeojson}
                  </a>
                </li>
                <li>
                  <a href={apiUrl("/api/v1/export.csv")} className="hover:underline">
                    {t.footer.feedCsv}
                  </a>
                </li>
                <li>
                  <a href={apiUrl("/api/v1/export.jsonld")} className="hover:underline">
                    {t.footer.feedJsonld}
                  </a>
                </li>
                <li>
                  <a
                    href={docsUrl()}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline inline-flex items-center gap-1"
                  >
                    <span>{t.footer.feedDocs}</span>
                    <ExternalLinkIcon className="w-3.5 h-3.5" />
                  </a>
                </li>
              </ul>
            </div>

            <div className="space-y-2">
              <h3 className="font-bold text-[var(--ink-primary)]">
                {t.footer.colInfo}
              </h3>
              <ul className="space-y-1.5 text-xs text-[var(--ink-secondary)]">
                <li>
                  <button
                    type="button"
                    onClick={() => setShowAccessibilityModal(true)}
                    className="text-sm text-[var(--gov-blue)] hover:underline cursor-pointer font-medium"
                  >
                    {t.footer.a11yBtn}
                  </button>
                </li>
                <li>
                  <a
                    href="https://dane.gov.pl"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-[var(--gov-blue)] hover:underline inline-flex items-center gap-1"
                  >
                    <span>{t.footer.daneGovLink}</span>
                    <ExternalLinkIcon className="w-3.5 h-3.5" />
                  </a>
                </li>
                <li className="pt-1 leading-relaxed">{t.footer.licenseNotice}</li>
              </ul>
            </div>
          </div>
        </div>
      </footer>

      {showAccessibilityModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="a11y-dialog-title"
          className="fixed inset-0 z-50 bg-[#000000]/60 flex items-center justify-center p-4"
        >
          <div className="w-full max-w-lg bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-[4px]">
            <div className="px-5 py-3.5 border-b border-[var(--border-hairline)] flex items-center justify-between gap-2 bg-[var(--bg-surface)]">
              <h2
                id="a11y-dialog-title"
                className="text-base font-bold text-[var(--ink-primary)]"
              >
                {t.footer.a11yTitle}
              </h2>
              <button
                type="button"
                onClick={() => setShowAccessibilityModal(false)}
                aria-label={t.dismiss}
                className="p-1 text-[var(--ink-primary)] hover:text-[var(--gov-blue)] cursor-pointer"
              >
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-3 text-sm leading-relaxed text-[var(--ink-primary)]">
              <p>{t.footer.a11yBody}</p>
              <ul className="list-disc pl-5 space-y-1.5 text-[var(--ink-secondary)]">
                {t.footer.a11yPoints.map((pt) => (
                  <li key={pt}>{pt}</li>
                ))}
              </ul>
              <div className="pt-2 flex justify-end">
                <button
                  type="button"
                  onClick={() => setShowAccessibilityModal(false)}
                  className="h-9 px-4 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-[var(--gov-blue-ink)] text-sm font-medium cursor-pointer"
                >
                  {t.dismiss}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
