import { useEffect, useState } from "react";
import { HarvesterView } from "./components/harvester/HarvesterView";
import { CloseIcon } from "./components/icons/Icons";
import { GovFooter } from "./components/layout/GovFooter";
import { TopBar, type AppTab } from "./components/layout/TopBar";
import { MapFinderView } from "./components/map/MapFinderView";
import { SubmitAedView } from "./components/submit/SubmitAedView";
import { TRANSLATIONS, type Locale } from "./i18n/translations";
import type { AEDRecord } from "./types/aed";

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
  const [origin, setOrigin] = useState({
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

  const [largeText, setLargeText] = useState<boolean>(() => {
    try {
      return localStorage.getItem("aed_wcag_font") === "lg";
    } catch {
      return false;
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
    if (largeText) {
      document.documentElement.dataset.fontScale = "lg";
    } else {
      delete document.documentElement.dataset.fontScale;
    }
    try {
      localStorage.setItem("aed_wcag_font", largeText ? "lg" : "normal");
    } catch {
      // Ignore storage failures
    }
  }, [largeText]);

  const handleLocateNearest = () => {
    setActiveTab("map");
    setGeoNotice(null);
    if (!navigator.geolocation) {
      setGeoNotice(t.geoUnavailable);
      return;
    }

    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(6));
        const lng = Number(pos.coords.longitude.toFixed(6));
        setOrigin({
          lat,
          lng,
          label: `GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
        });
        setFlySeq((n) => n + 1);
        setIsLocating(false);
      },
      (err) => {
        setGeoNotice(
          `${t.geoErrorPrefix} ${err.message}. ${t.geoShowingFallback} ${origin.label}.`
        );
        setIsLocating(false);
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
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
    window.scrollTo({ top: 0, behavior: "smooth" });
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
        largeText={largeText}
        onToggleLargeText={() => setLargeText((v) => !v)}
      />

      {geoNotice && (
        <div className="bg-[var(--bg-canvas)] border-b border-[var(--border-hairline)] px-4 sm:px-6 py-2">
          <div className="max-w-[1180px] mx-auto flex items-center justify-between text-xs text-[var(--ink-secondary)]">
            <span>{geoNotice}</span>
            <button
              type="button"
              onClick={() => setGeoNotice(null)}
              aria-label={t.dismiss}
              className="p-0.5 text-[var(--ink-secondary)] hover:text-[var(--ink-primary)] cursor-pointer"
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
      </main>

      <GovFooter locale={locale} onNavigate={handleNavigate} />
    </div>
  );
}

export default App;
