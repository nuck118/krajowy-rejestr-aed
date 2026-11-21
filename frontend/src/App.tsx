import { useEffect, useState } from "react";
import { CampaignView } from "./components/campaign/CampaignView";
import { HarvesterView } from "./components/harvester/HarvesterView";
import { CloseIcon } from "./components/icons/Icons";
import { GovFooter } from "./components/layout/GovFooter";
import { TopBar, type AppTab, type FontScale } from "./components/layout/TopBar";
import { MapFinderView } from "./components/map/MapFinderView";
import { SubmitAedView } from "./components/submit/SubmitAedView";
import { TRANSLATIONS, type Locale } from "./i18n/translations";
import type { AEDRecord } from "./types/aed";
import { acquirePreciseBrowserLocation, reverseGeocodeLocation } from "./utils/geo";

export interface OriginPoint {
  lat: number;
  lng: number;
  label: string;
  accuracyMeters?: number;
}

export function App() {
  const [locale, setLocale] = useState<Locale>(() => {
    try {
      const saved = localStorage.getItem("aed_lang");
      return saved === "en" ? "en" : "pl";
    } catch {
      return "pl";
    }
  });

  const [activeTab, setActiveTab] = useState<AppTab>("map");
  const [origin, setOrigin] = useState<OriginPoint>({
    lat: 53.1235,
    lng: 18.0084,
    label: "Bydgoszcz",
  });
  const [flySeq, setFlySeq] = useState(0);
  const [isLocating, setIsLocating] = useState(false);
  const [geoNotice, setGeoNotice] = useState<string | null>(null);

  const [highContrast, setHighContrast] = useState<boolean>(() => {
    try {
      return localStorage.getItem("aed_wcag_contrast") === "high";
    } catch {
      return false;
    }
  });

  const [fontScale, setFontScale] = useState<FontScale>(() => {
    try {
      const saved = localStorage.getItem("aed_wcag_font");
      return saved === "lg" || saved === "xl" ? saved : "md";
    } catch {
      return "md";
    }
  });

  const t = TRANSLATIONS[locale];

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = t.pageTitle;
    try {
      localStorage.setItem("aed_lang", locale);
    } catch {
      // Ignore storage failures
    }
  }, [locale, t.pageTitle]);

  useEffect(() => {
    if (highContrast) {
      document.documentElement.dataset.contrast = "high";
    } else {
      delete document.documentElement.dataset.contrast;
    }
    try {
      localStorage.setItem("aed_wcag_contrast", highContrast ? "high" : "normal");
    } catch {
      // Ignore storage failures
    }
  }, [highContrast]);

  useEffect(() => {
    if (fontScale === "md") {
      delete document.documentElement.dataset.fontScale;
    } else {
      document.documentElement.dataset.fontScale = fontScale;
    }
    try {
      localStorage.setItem("aed_wcag_font", fontScale);
    } catch {
      // Ignore storage failures
    }
  }, [fontScale]);

  const handleLocateNearest = () => {
    setActiveTab("map");
    setGeoNotice(null);
    if (!navigator.geolocation) {
      setGeoNotice(t.geoUnavailable);
      return;
    }

    setIsLocating(true);
    acquirePreciseBrowserLocation((interim) => {
      setOrigin({
        lat: interim.lat,
        lng: interim.lng,
        label: `GPS (${interim.lat.toFixed(4)}, ${interim.lng.toFixed(4)})`,
        accuracyMeters: interim.accuracyMeters,
      });
    })
      .then(async (fix) => {
        const baseLabel = `GPS (${fix.lat.toFixed(4)}, ${fix.lng.toFixed(4)})`;
        setOrigin({
          lat: fix.lat,
          lng: fix.lng,
          label: baseLabel,
          accuracyMeters: fix.accuracyMeters,
        });
        setFlySeq((n) => n + 1);
        setIsLocating(false);

        if (fix.accuracyMeters > 400) {
          setGeoNotice(
            `${t.geoCoarsePrefix} +/- ${fix.accuracyMeters} ${t.geoCoarseSuffix}`
          );
        }

        const rev = await reverseGeocodeLocation(fix.lat, fix.lng);
        if (rev?.label) {
          setOrigin((prev) =>
            Math.abs(prev.lat - fix.lat) < 0.0001 && Math.abs(prev.lng - fix.lng) < 0.0001
              ? { ...prev, label: rev.label }
              : prev
          );
        }
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        setGeoNotice(
          `${t.geoErrorPrefix} ${msg}. ${t.geoShowingFallback} ${origin.label}.`
        );
        setIsLocating(false);
      });
  };

  const handleViewSubmittedOnMap = (aed: AEDRecord) => {
    setOrigin({
      lat: aed.latitude,
      lng: aed.longitude,
      label: aed.city || `${aed.latitude.toFixed(4)}, ${aed.longitude.toFixed(4)}`,
    });
    setFlySeq((n) => n + 1);
    setActiveTab("map");
  };

  const handleNavigate = (tab: AppTab) => {
    setActiveTab(tab);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
  };

  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg-page)] text-[var(--ink-primary)]">
      <a
        href="#main-workspace"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-1.5 focus:bg-[var(--gov-blue)] focus:text-[var(--gov-blue-ink)] focus:text-xs focus:font-semibold rounded-[3px]"
      >
        {t.skipToContent}
      </a>

      <TopBar
        locale={locale}
        onLocaleChange={setLocale}
        activeTab={activeTab}
        onTabChange={handleNavigate}
        onLocateNearest={handleLocateNearest}
        isLocating={isLocating}
        highContrast={highContrast}
        onToggleHighContrast={() => setHighContrast((v) => !v)}
        fontScale={fontScale}
        onFontScaleChange={setFontScale}
      />

      {geoNotice && (
        <div
          role="alert"
          aria-live="assertive"
          className="bg-[var(--bg-amber)] border-b border-[var(--border-hairline)] px-3 sm:px-4 py-2.5"
        >
          <div className="max-w-[1440px] mx-auto flex items-center justify-between gap-3 text-xs font-medium text-[var(--status-amber)]">
            <span>{geoNotice}</span>
            <button
              type="button"
              onClick={() => setGeoNotice(null)}
              aria-label={t.dismiss}
              className="p-1 text-[var(--ink-primary)] hover:text-[var(--gov-blue)] cursor-pointer shrink-0"
            >
              <CloseIcon className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      <main id="main-workspace" className="flex-1">
        {activeTab === "map" && (
          <MapFinderView
            locale={locale}
            origin={origin}
            flySeq={flySeq}
            isLocating={isLocating}
            onGeolocate={handleLocateNearest}
            onOriginChange={setOrigin}
            onNavigate={handleNavigate}
          />
        )}
        {activeTab === "harvester" && (
          <HarvesterView locale={locale} onNavigate={handleNavigate} />
        )}
        {activeTab === "submit" && (
          <SubmitAedView
            locale={locale}
            initialLat={origin.lat}
            initialLng={origin.lng}
            onViewOnMap={handleViewSubmittedOnMap}
            onNavigate={handleNavigate}
          />
        )}
        {activeTab === "campaign" && (
          <CampaignView locale={locale} onNavigate={handleNavigate} />
        )}
      </main>

      <GovFooter locale={locale} onNavigate={handleNavigate} />
    </div>
  );
}

export default App;
