import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { fetchAeds, fetchNearestAeds, fetchStats } from "../../api/client";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import type {
  AEDNearestRecord,
  AEDRecord,
  FinderFilters,
  StatsResponse,
} from "../../types/aed";
import {
  geocodePolishLocation,
  POLISH_CITIES,
  reverseGeocodeLocation,
} from "../../utils/geo";
import { CrosshairIcon, PinIcon, SearchIcon } from "../icons/Icons";
import type { AppTab } from "../layout/TopBar";
import { AedDetailPanel } from "./AedDetailPanel";
import { FinderRail } from "./FinderRail";
import { MapCanvas } from "./MapCanvas";

interface MapFinderViewProps {
  locale: Locale;
  origin: { lat: number; lng: number; label: string; accuracyMeters?: number };
  flySeq: number;
  isLocating: boolean;
  onGeolocate: () => void;
  onOriginChange: (origin: {
    lat: number;
    lng: number;
    label: string;
    accuracyMeters?: number;
  }) => void;
  onNavigate?: (tab: AppTab) => void;
}

const QUICK_CITIES = POLISH_CITIES.slice(0, 6);

export function MapFinderView({
  locale,
  origin,
  flySeq,
  isLocating,
  onGeolocate,
  onOriginChange,
  onNavigate,
}: MapFinderViewProps) {
  const [filters, setFilters] = useState<FinderFilters>({
    openNow: false,
    is24_7: false,
    publicOnly: false,
    outdoorOnly: false,
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [nearestItems, setNearestItems] = useState<AEDNearestRecord[]>([]);
  const [viewportItems, setViewportItems] = useState<AEDRecord[]>([]);
  const [selectedAed, setSelectedAed] = useState<AEDRecord | null>(null);
  const [currentBbox, setCurrentBbox] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [pickMode, setPickMode] = useState(false);
  const [mapCenter, setMapCenter] = useState<{ lat: number; lng: number }>({
    lat: origin.lat,
    lng: origin.lng,
  });
  const [localFlyTarget, setLocalFlyTarget] = useState<{
    lat: number;
    lng: number;
    zoom: number;
    seq: number;
  } | null>(null);

  const detailCardRef = useRef<HTMLDivElement | null>(null);
  const t = TRANSLATIONS[locale].mapView;

  const filterOptions: { key: keyof FinderFilters; label: string }[] = [
    { key: "openNow", label: t.filters.openNow },
    { key: "is24_7", label: t.filters.is24_7 },
    { key: "publicOnly", label: t.filters.publicOnly },
    { key: "outdoorOnly", label: t.filters.outdoorOnly },
  ];

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => {
        // Optional sidebar overview widget
      });
  }, []);

  useEffect(() => {
    if (flySeq > 0) {
      setLocalFlyTarget({
        lat: origin.lat,
        lng: origin.lng,
        zoom: 14.2,
        seq: flySeq,
      });
    }
  }, [flySeq, origin.lat, origin.lng]);

  const loadNearest = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchNearestAeds({
        lat: origin.lat,
        lng: origin.lng,
        radius_m: 15000,
        limit: 40,
        open_now: filters.openNow ? true : undefined,
        is_24_7: filters.is24_7 ? true : undefined,
        access_type: filters.publicOnly ? "public" : undefined,
        indoor: filters.outdoorOnly ? false : undefined,
      });
      setNearestItems(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.loadError);
    } finally {
      setIsLoading(false);
    }
  }, [origin.lat, origin.lng, filters, t.loadError]);

  const loadViewport = useCallback(
    async (bbox: string) => {
      try {
        const res = await fetchAeds({
          bbox,
          limit: 600,
          open_now: filters.openNow ? true : undefined,
          is_24_7: filters.is24_7 ? true : undefined,
          access_type: filters.publicOnly ? "public" : undefined,
          indoor: filters.outdoorOnly ? false : undefined,
        });
        setViewportItems(res.items);
      } catch {
        // Primary error state handled via loadNearest
      }
    },
    [filters]
  );

  useEffect(() => {
    void loadNearest();
  }, [loadNearest]);

  useEffect(() => {
    if (currentBbox) {
      void loadViewport(currentBbox);
    }
  }, [currentBbox, loadViewport]);

  const combinedMapAeds = useMemo(() => {
    const byId = new Map<string, AEDRecord>();
    for (const item of viewportItems) {
      byId.set(item.id, item);
    }
    for (const item of nearestItems) {
      byId.set(item.id, item);
    }
    return Array.from(byId.values());
  }, [viewportItems, nearestItems]);

  const selectedId = selectedAed?.id ?? null;

  const selectedRecord = useMemo(() => {
    if (!selectedAed) return null;
    return combinedMapAeds.find((item) => item.id === selectedAed.id) ?? selectedAed;
  }, [combinedMapAeds, selectedAed]);

  const selectedDistance = useMemo(() => {
    if (!selectedId) return undefined;
    return nearestItems.find((item) => item.id === selectedId)?.distance_m;
  }, [nearestItems, selectedId]);

  const handleToggleFilter = (key: keyof FinderFilters) => {
    setFilters((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSelectAed = (id: string) => {
    const target =
      combinedMapAeds.find((item) => item.id === id) ??
      (selectedAed?.id === id ? selectedAed : null);
    if (target) {
      setSelectedAed(target);
      setLocalFlyTarget({
        lat: target.latitude,
        lng: target.longitude,
        zoom: 16,
        seq: Date.now(),
      });
    }
    window.setTimeout(() => {
      const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      detailCardRef.current?.scrollIntoView({
        behavior: reduced ? "auto" : "smooth",
        block: "nearest",
      });
    }, 60);
  };

  const handleQuickCity = (city: { name: string; lat: number; lng: number }) => {
    setPickMode(false);
    onOriginChange({ lat: city.lat, lng: city.lng, label: city.name });
    setLocalFlyTarget({ lat: city.lat, lng: city.lng, zoom: 13.5, seq: Date.now() });
    setSelectedAed(null);
  };

  const handleManualPickOrigin = useCallback(
    async (lat: number, lng: number, shouldFly = false) => {
      setPickMode(false);
      const fallbackLabel = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      onOriginChange({ lat, lng, label: fallbackLabel });
      if (shouldFly) {
        setLocalFlyTarget({ lat, lng, zoom: 16, seq: Date.now() });
      }
      const rev = await reverseGeocodeLocation(lat, lng);
      if (rev?.label) {
        onOriginChange({ lat, lng, label: rev.label });
      }
    },
    [onOriginChange]
  );

  const handleSearchSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;

    setPickMode(false);
    setIsLoading(true);
    setError(null);
    const geo = await geocodePolishLocation(query);
    if (geo) {
      onOriginChange({ lat: geo.lat, lng: geo.lng, label: geo.label });
      setLocalFlyTarget({
        lat: geo.lat,
        lng: geo.lng,
        zoom: geo.isStreetLevel ? 16 : 13.8,
        seq: Date.now(),
      });
      setSelectedAed(null);
      return;
    }

    try {
      const res = await fetchAeds({ q: query, limit: 20 });
      if (res.items.length > 0) {
        const first = res.items[0];
        onOriginChange({
          lat: first.latitude,
          lng: first.longitude,
          label: first.city || query,
        });
        setLocalFlyTarget({
          lat: first.latitude,
          lng: first.longitude,
          zoom: 14.5,
          seq: Date.now(),
        });
        setSelectedAed(first);
      } else {
        setError(`${t.noSearchMatch} "${query}".`);
        setIsLoading(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t.loadError);
      setIsLoading(false);
    }
  };

  const handleUpdatedAed = useCallback((updated: AEDRecord) => {
    setSelectedAed((prev) =>
      prev && prev.id === updated.id ? { ...prev, ...updated } : prev
    );
    setNearestItems((prev) =>
      prev.map((item) => (item.id === updated.id ? { ...item, ...updated } : item))
    );
    setViewportItems((prev) =>
      prev.map((item) => (item.id === updated.id ? updated : item))
    );
  }, []);

  return (
    <div className="max-w-[1180px] mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Page Header & Search Panel */}
      <div className="bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-[4px] p-5 sm:p-6 space-y-3">
        <nav
          aria-label="Breadcrumb"
          className="text-xs text-[var(--ink-secondary)] flex flex-wrap items-center gap-1.5"
        >
          <span>{t.breadcrumbHome}</span>
          <span aria-hidden="true">/</span>
          <span>{t.breadcrumbMinistry}</span>
          <span aria-hidden="true">/</span>
          <span className="text-[var(--ink-primary)] font-semibold">
            {t.breadcrumbCurrent}
          </span>
        </nav>

        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--ink-primary)]">
          {t.heading}
        </h1>
        <p className="text-sm sm:text-base text-[var(--ink-secondary)] max-w-3xl leading-relaxed">
          {t.intro}
        </p>

        <form
          onSubmit={handleSearchSubmit}
          className="pt-3 border-t border-[var(--border-hairline)] space-y-4"
        >
          <div>
            <label
              htmlFor="aed-location-search"
              className="block text-sm font-semibold text-[var(--ink-primary)] mb-1.5"
            >
              {t.searchLabel}
            </label>
            <div className="flex flex-col sm:flex-row items-stretch gap-2.5">
              <div className="relative flex-1">
                <SearchIcon className="w-4 h-4 text-[var(--ink-secondary)] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  id="aed-location-search"
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={t.searchPlaceholder}
                  className="w-full h-11 pl-9 pr-3 text-sm rounded-[3px] bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] placeholder:text-[var(--ink-secondary)] focus:outline-none focus:border-[var(--gov-blue)]"
                />
              </div>
              <button
                type="submit"
                className="h-11 px-6 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-[var(--gov-blue-ink)] text-sm font-semibold cursor-pointer shrink-0 transition-colors"
              >
                {t.searchButton}
              </button>
              <button
                type="button"
                onClick={onGeolocate}
                disabled={isLocating}
                className="h-11 px-4 rounded-[3px] border border-[var(--border-input)] bg-[var(--bg-surface)] hover:border-[var(--gov-blue)] text-[var(--gov-blue)] text-sm font-semibold inline-flex items-center justify-center gap-2 cursor-pointer shrink-0 disabled:opacity-50"
              >
                <CrosshairIcon className="w-4 h-4" />
                <span>{isLocating ? TRANSLATIONS[locale].locatingGps : t.gpsButton}</span>
              </button>
            </div>
          </div>

          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pt-1">
            <fieldset className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <legend className="sr-only">{t.filtersLegend}</legend>
              {filterOptions.map((opt) => (
                <label
                  key={opt.key}
                  className="inline-flex items-center gap-2 text-sm text-[var(--ink-primary)] cursor-pointer select-none"
                >
                  <input
                    type="checkbox"
                    checked={filters[opt.key]}
                    onChange={() => handleToggleFilter(opt.key)}
                    className="w-4 h-4 accent-[var(--gov-blue)] rounded-[2px] cursor-pointer"
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
            </fieldset>

            <div className="flex flex-wrap items-center gap-2.5 text-xs">
              <span className="text-[var(--ink-secondary)] font-medium">
                {t.popularCities}
              </span>
              {QUICK_CITIES.map((c) => (
                <button
                  key={c.name}
                  type="button"
                  onClick={() => handleQuickCity(c)}
                  className="text-[var(--gov-blue)] hover:underline font-semibold cursor-pointer"
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>
        </form>
      </div>

      {/* Two-Column Portal Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 space-y-6">
          <section
            aria-label={t.mapTitle}
            className="border border-[var(--border-hairline)] rounded-[4px] bg-[var(--bg-canvas)] overflow-hidden"
          >
            <div className="px-4 py-3 border-b border-[var(--border-hairline)] bg-[var(--bg-surface)] flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
              <div>
                <h2 className="text-base font-bold text-[var(--ink-primary)]">{t.mapTitle}</h2>
                <p className="text-xs text-[var(--ink-secondary)]">
                  {t.mapSubtitlePrefix} <strong>{origin.label}</strong>
                  {origin.accuracyMeters !== undefined && (
                    <span>
                      {" "}
                      ({t.gpsAccuracyLabel} +/- {origin.accuracyMeters} m)
                    </span>
                  )}
                  . {t.mapSubtitleSuffix}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  aria-pressed={pickMode}
                  onClick={() => setPickMode((v) => !v)}
                  className={`h-8 px-2.5 rounded-[3px] text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer border transition-colors ${
                    pickMode
                      ? "bg-[var(--gov-blue)] text-[var(--gov-blue-ink)] border-[var(--gov-blue)]"
                      : "bg-[var(--bg-canvas)] text-[var(--gov-blue)] border-[var(--border-input)] hover:border-[var(--gov-blue)]"
                  }`}
                >
                  <PinIcon className="w-3.5 h-3.5" />
                  <span>{pickMode ? t.pickOnMapActive : t.pickOnMapBtn}</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    void handleManualPickOrigin(mapCenter.lat, mapCenter.lng, false)
                  }
                  className="h-8 px-2.5 rounded-[3px] border border-[var(--border-input)] bg-[var(--bg-canvas)] hover:border-[var(--gov-blue)] text-xs font-semibold text-[var(--ink-primary)] cursor-pointer"
                >
                  {t.useMapCenterBtn}
                </button>
              </div>
            </div>
            <div className="h-[460px] sm:h-[500px] w-full">
              <MapCanvas
                locale={locale}
                aeds={combinedMapAeds}
                selectedId={selectedId}
                origin={{ lat: origin.lat, lng: origin.lng }}
                flyTarget={localFlyTarget}
                pickMode={pickMode}
                onSelectAed={handleSelectAed}
                onBoundsChange={setCurrentBbox}
                onPickOrigin={(lat, lng) => void handleManualPickOrigin(lat, lng, false)}
                onCenterChange={(lat, lng) => setMapCenter({ lat, lng })}
              />
            </div>
          </section>

          {selectedRecord && (
            <div ref={detailCardRef}>
              <AedDetailPanel
                locale={locale}
                aed={selectedRecord}
                distanceMeters={selectedDistance}
                onBack={() => setSelectedAed(null)}
                onUpdated={handleUpdatedAed}
              />
            </div>
          )}
        </div>

        {/* Right Sidebar: Nearest Directory + Flat Registry Overview */}
        <aside className="lg:col-span-5 space-y-6">
          <FinderRail
            locale={locale}
            nearestItems={nearestItems}
            selectedId={selectedId}
            originLabel={origin.label}
            isLoading={isLoading}
            error={error}
            onSelectAed={handleSelectAed}
            onRetry={() => void loadNearest()}
          />

          <section className="border border-[var(--border-hairline)] rounded-[4px] bg-[var(--bg-canvas)] overflow-hidden">
            <div className="px-4 py-3 border-b border-[var(--border-hairline)] bg-[var(--bg-surface)]">
              <h2 className="text-base font-bold text-[var(--ink-primary)]">
                {t.overviewTitle}
              </h2>
              <p className="text-xs text-[var(--ink-secondary)] mt-0.5">
                {t.overviewSubtitle}
              </p>
            </div>

            {stats ? (
              <dl className="divide-y divide-[var(--border-hairline)] text-sm">
                <div className="px-4 py-2.5 flex items-center justify-between">
                  <dt className="text-[var(--ink-secondary)]">{t.unifiedAeds}</dt>
                  <dd className="font-bold text-[var(--ink-primary)]">
                    {stats.total_unified_aeds.toLocaleString("en-US")}
                  </dd>
                </div>
                <div className="px-4 py-2.5 flex items-center justify-between">
                  <dt className="text-[var(--ink-secondary)]">{t.duplicatesMerged}</dt>
                  <dd className="font-bold text-[var(--status-emerald)]">
                    {stats.duplicates_merged.toLocaleString("en-US")}
                  </dd>
                </div>
                <div className="px-4 py-2.5 flex items-center justify-between">
                  <dt className="text-[var(--ink-secondary)]">{t.activeSources}</dt>
                  <dd className="font-bold text-[var(--ink-primary)]">
                    {stats.active_sources}
                  </dd>
                </div>
                <div className="px-4 py-2.5 flex items-center justify-between">
                  <dt className="text-[var(--ink-secondary)]">{t.avgCompleteness}</dt>
                  <dd className="font-bold text-[var(--ink-primary)]">
                    {stats.national_completeness_avg.toFixed(1)}%
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="p-4 text-xs text-[var(--ink-secondary)]">
                {t.overviewLoading}
              </p>
            )}

            <div className="p-4 border-t border-[var(--border-hairline)] bg-[var(--bg-surface)] flex flex-col sm:flex-row gap-2">
              <button
                type="button"
                onClick={() => onNavigate?.("harvester")}
                className="flex-1 h-9 px-3 rounded-[3px] border border-[var(--gov-blue)] bg-[var(--bg-canvas)] text-xs font-semibold text-[var(--gov-blue)] hover:bg-[var(--bg-callout)] cursor-pointer"
              >
                {t.btnOpenData}
              </button>
              <button
                type="button"
                onClick={() => onNavigate?.("submit")}
                className="flex-1 h-9 px-3 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-xs font-semibold text-[var(--gov-blue-ink)] cursor-pointer"
              >
                {t.btnSubmitMissing}
              </button>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
