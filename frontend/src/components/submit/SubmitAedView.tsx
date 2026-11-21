import { useState, type FormEvent } from "react";
import { submitAed } from "../../api/client";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import type { AccessType, AEDRecord, AEDSubmitResponse, AedStatus } from "../../types/aed";
import { evaluateCompleteness } from "../../utils/completeness";
import { acquirePreciseBrowserLocation, reverseGeocodeLocation } from "../../utils/geo";
import { CheckIcon } from "../icons/Icons";
import type { AppTab } from "../layout/TopBar";
import { CoordinatePickerMap } from "./CoordinatePickerMap";

interface SubmitAedViewProps {
  locale: Locale;
  initialLat?: number;
  initialLng?: number;
  onViewOnMap: (aed: AEDRecord) => void;
  onNavigate?: (tab: AppTab) => void;
}

export function SubmitAedView({
  locale,
  initialLat = 53.1235,
  initialLng = 18.0084,
  onViewOnMap,
  onNavigate,
}: SubmitAedViewProps) {
  const [latitude, setLatitude] = useState<string>(initialLat.toFixed(6));
  const [longitude, setLongitude] = useState<string>(initialLng.toFixed(6));
  const [streetAddress, setStreetAddress] = useState("");
  const [city, setCity] = useState("Bydgoszcz");
  const [postalCode, setPostalCode] = useState("");
  const [locationDescription, setLocationDescription] = useState("");
  const [accessType, setAccessType] = useState<AccessType>("public");
  const [is24_7, setIs24_7] = useState(true);
  const [openingHours, setOpeningHours] = useState("24/7");
  const [indoor, setIndoor] = useState<boolean>(true);
  const [status] = useState<AedStatus>("operational");
  const [submitterOrg, setSubmitterOrg] = useState("direct_submission");

  const [isLocating, setIsLocating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitResult, setSubmitResult] = useState<AEDSubmitResponse | null>(null);

  const t = TRANSLATIONS[locale].submit;
  const accessLabels = TRANSLATIONS[locale].detail.accessTypes;
  const tiers = TRANSLATIONS[locale].tiers;
  const checkLabels = TRANSLATIONS[locale].checks;

  const parsedLat = Number(latitude);
  const parsedLng = Number(longitude);
  const nowIso = new Date().toISOString();

  const completeness = evaluateCompleteness({
    latitude: Number.isFinite(parsedLat) ? parsedLat : null,
    longitude: Number.isFinite(parsedLng) ? parsedLng : null,
    location_description: locationDescription,
    street_address: streetAddress,
    city,
    postal_code: postalCode,
    access_type: accessType,
    opening_hours: is24_7 ? "24/7" : openingHours,
    is_24_7: is24_7,
    indoor,
    status,
    last_verified_at: nowIso,
  });

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setSubmitError(TRANSLATIONS[locale].geoUnavailable);
      return;
    }
    setIsLocating(true);
    setSubmitError(null);
    acquirePreciseBrowserLocation((interim) => {
      setLatitude(interim.lat.toFixed(6));
      setLongitude(interim.lng.toFixed(6));
    })
      .then(async (fix) => {
        setLatitude(fix.lat.toFixed(6));
        setLongitude(fix.lng.toFixed(6));
        setIsLocating(false);

        const rev = await reverseGeocodeLocation(fix.lat, fix.lng);
        if (rev) {
          if (rev.street_address && !streetAddress.trim()) {
            setStreetAddress(rev.street_address);
          }
          if (rev.city) {
            setCity(rev.city);
          }
          if (rev.postal_code && !postalCode.trim()) {
            setPostalCode(rev.postal_code);
          }
        }
      })
      .catch((err: unknown) => {
        setSubmitError(err instanceof Error ? err.message : String(err));
        setIsLocating(false);
      });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setSubmitResult(null);

    if (!Number.isFinite(parsedLat) || !Number.isFinite(parsedLng)) {
      setSubmitError(t.errCoords);
      return;
    }
    if (locationDescription.trim().length < 3) {
      setSubmitError(t.errPlacement);
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await submitAed({
        latitude: parsedLat,
        longitude: parsedLng,
        street_address: streetAddress.trim() || null,
        city: city.trim() || null,
        postal_code: postalCode.trim() || null,
        location_description: locationDescription.trim(),
        access_type: accessType,
        opening_hours: is24_7 ? "24/7" : openingHours.trim() || null,
        is_24_7: is24_7,
        indoor,
        status,
        last_verified_at: nowIso,
        source_name: submitterOrg.trim() || "direct_submission",
      });
      setSubmitResult(result);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const barColor =
    completeness.score >= 80
      ? "var(--status-emerald)"
      : completeness.score >= 60
        ? "var(--gov-blue)"
        : "var(--aed-red)";

  return (
    <div className="max-w-[1440px] mx-auto px-3 sm:px-4 py-5">
      <div className="bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-[4px] p-4 sm:p-6 space-y-6">
        <div className="space-y-3 pb-5 border-b border-[var(--border-hairline)]">
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

          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--ink-primary)]">
                {t.heading}
              </h1>
              <p className="text-sm sm:text-base text-[var(--ink-secondary)] mt-1 max-w-3xl leading-relaxed">
                {t.intro}
              </p>
            </div>
            <span className="text-xs text-[var(--ink-secondary)] shrink-0">
              {t.requiredLegend}
            </span>
          </div>
        </div>

        {submitResult && (
          <div className="border border-[var(--status-emerald)] rounded-[3px] bg-[var(--bg-surface)] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm font-bold text-[var(--status-emerald)]">
                <CheckIcon className="w-4 h-4" />
                <span>
                  {submitResult.action === "merged"
                    ? `${t.resultMergedPrefix} ${submitResult.merged_distance_m ?? 0} m)`
                    : t.resultCreated}
                </span>
              </div>
              <p className="text-xs text-[var(--ink-primary)]">
                {t.canonicalId} <code className="font-mono">{submitResult.aed.id}</code> |{" "}
                {t.completenessLabel}{" "}
                <strong>{submitResult.aed.completeness_score}%</strong> (
                {tiers[submitResult.aed.completeness_tier] ?? submitResult.aed.completeness_tier})
              </p>
            </div>
            <button
              type="button"
              onClick={() => onViewOnMap(submitResult.aed)}
              className="h-9 px-4 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-[var(--gov-blue-ink)] text-xs font-semibold cursor-pointer shrink-0 transition-colors"
            >
              {t.viewOnMap}
            </button>
          </div>
        )}

        {submitError && (
          <div
            role="alert"
            className="border border-[var(--aed-red)] rounded-[3px] bg-[var(--bg-urgent)] p-3.5 text-sm text-[var(--aed-red)]"
          >
            {submitError}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <form
            onSubmit={handleSubmit}
            className="lg:col-span-7 border border-[var(--border-hairline)] rounded-[3px] bg-[var(--bg-canvas)] p-5 space-y-5"
          >
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="aed-lat"
                  className="block text-sm font-semibold text-[var(--ink-primary)] mb-1"
                >
                  {t.latLabel} <span className="text-[var(--gov-crimson)]">*</span>
                </label>
                <input
                  id="aed-lat"
                  type="number"
                  step="0.000001"
                  required
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                  className="w-full h-10 px-3 rounded-[3px] font-mono text-sm bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
                />
              </div>
              <div>
                <label
                  htmlFor="aed-lng"
                  className="block text-sm font-semibold text-[var(--ink-primary)] mb-1"
                >
                  {t.lngLabel} <span className="text-[var(--gov-crimson)]">*</span>
                </label>
                <input
                  id="aed-lng"
                  type="number"
                  step="0.000001"
                  required
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                  className="w-full h-10 px-3 rounded-[3px] font-mono text-sm bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="aed-placement"
                className="block text-sm font-semibold text-[var(--ink-primary)] mb-1"
              >
                {t.placementLabel} <span className="text-[var(--gov-crimson)]">*</span>
              </label>
              <p className="text-xs text-[var(--ink-secondary)] mb-1.5">
                {t.placementHint}
              </p>
              <textarea
                id="aed-placement"
                rows={2}
                required
                value={locationDescription}
                onChange={(e) => setLocationDescription(e.target.value)}
                placeholder={t.placementPlaceholder}
                className="w-full p-3 rounded-[3px] text-sm bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] placeholder:text-[var(--ink-secondary)] focus:outline-none focus:border-[var(--gov-blue)]"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                <label
                  htmlFor="aed-street"
                  className="block text-sm font-semibold text-[var(--ink-primary)] mb-1"
                >
                  {t.streetLabel}
                </label>
                <input
                  id="aed-street"
                  type="text"
                  value={streetAddress}
                  onChange={(e) => setStreetAddress(e.target.value)}
                  placeholder="ul. Gdańska 15"
                  className="w-full h-10 px-3 rounded-[3px] text-sm bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
                />
              </div>
              <div>
                <label
                  htmlFor="aed-postal"
                  className="block text-sm font-semibold text-[var(--ink-primary)] mb-1"
                >
                  {t.postalLabel}
                </label>
                <input
                  id="aed-postal"
                  type="text"
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  placeholder="85-005"
                  pattern="\d{2}-\d{3}"
                  className="w-full h-10 px-3 rounded-[3px] font-mono text-sm bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="aed-city"
                  className="block text-sm font-semibold text-[var(--ink-primary)] mb-1"
                >
                  {t.cityLabel}
                </label>
                <input
                  id="aed-city"
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="Bydgoszcz"
                  className="w-full h-10 px-3 rounded-[3px] text-sm bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
                />
              </div>
              <div>
                <label
                  htmlFor="aed-access"
                  className="block text-sm font-semibold text-[var(--ink-primary)] mb-1"
                >
                  {t.accessLabel}
                </label>
                <select
                  id="aed-access"
                  value={accessType}
                  onChange={(e) => setAccessType(e.target.value as AccessType)}
                  className="w-full h-10 px-3 rounded-[3px] text-sm bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
                >
                  <option value="public">{accessLabels.public}</option>
                  <option value="customers_only">{accessLabels.customers_only}</option>
                  <option value="private">{accessLabels.private}</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-end">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label
                    htmlFor="aed-hours"
                    className="text-sm font-semibold text-[var(--ink-primary)]"
                  >
                    {t.hoursLabel}
                  </label>
                  <label className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--ink-primary)] cursor-pointer">
                    <input
                      type="checkbox"
                      checked={is24_7}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setIs24_7(checked);
                        if (checked) {
                          setOpeningHours("24/7");
                        } else if (openingHours === "24/7") {
                          setOpeningHours("Mo-Fr 08:00-18:00");
                        }
                      }}
                    />
                    <span>{t.open247}</span>
                  </label>
                </div>
                <input
                  id="aed-hours"
                  type="text"
                  value={is24_7 ? "24/7" : openingHours}
                  disabled={is24_7}
                  onChange={(e) => setOpeningHours(e.target.value)}
                  placeholder="Mo-Fr 08:00-18:00"
                  className="w-full h-10 px-3 rounded-[3px] font-mono text-sm bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] disabled:opacity-60 focus:outline-none focus:border-[var(--gov-blue)]"
                />
              </div>

              <div>
                <span className="block text-sm font-semibold text-[var(--ink-primary)] mb-1">
                  {t.envLabel}
                </span>
                <div className="grid grid-cols-2 h-10 border border-[var(--border-input)] rounded-[3px] divide-x divide-[var(--border-input)] overflow-hidden">
                  <label
                    className={`flex items-center justify-center gap-1.5 text-sm cursor-pointer ${
                      indoor
                        ? "bg-[var(--gov-blue)] text-[var(--gov-blue-ink)] font-semibold"
                        : "bg-[var(--bg-surface)] text-[var(--ink-primary)]"
                    }`}
                  >
                    <input
                      type="radio"
                      name="indoor"
                      checked={indoor === true}
                      onChange={() => setIndoor(true)}
                      className="sr-only"
                    />
                    <span>{t.indoor}</span>
                  </label>
                  <label
                    className={`flex items-center justify-center gap-1.5 text-sm cursor-pointer ${
                      !indoor
                        ? "bg-[var(--gov-blue)] text-[var(--gov-blue-ink)] font-semibold"
                        : "bg-[var(--bg-surface)] text-[var(--ink-primary)]"
                    }`}
                  >
                    <input
                      type="radio"
                      name="indoor"
                      checked={indoor === false}
                      onChange={() => setIndoor(false)}
                      className="sr-only"
                    />
                    <span>{t.outdoor}</span>
                  </label>
                </div>
              </div>
            </div>

            <div>
              <label
                htmlFor="aed-org"
                className="block text-sm font-semibold text-[var(--ink-primary)] mb-1"
              >
                {t.orgLabel}
              </label>
              <p className="text-xs text-[var(--ink-secondary)] mb-1.5">{t.orgHint}</p>
              <input
                id="aed-org"
                type="text"
                value={submitterOrg}
                onChange={(e) => setSubmitterOrg(e.target.value)}
                placeholder="um_bydgoszcz / direct_submission"
                className="w-full h-10 px-3 rounded-[3px] font-mono text-sm bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full h-11 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] disabled:opacity-50 text-[var(--gov-blue-ink)] text-sm font-semibold transition-colors cursor-pointer"
            >
              {isSubmitting ? t.submittingBtn : t.submitBtn}
            </button>
          </form>

          <div className="lg:col-span-5 space-y-5">
            <CoordinatePickerMap
              locale={locale}
              latitude={Number.isFinite(parsedLat) ? parsedLat : initialLat}
              longitude={Number.isFinite(parsedLng) ? parsedLng : initialLng}
              onChange={(lat, lng) => {
                setLatitude(lat.toFixed(6));
                setLongitude(lng.toFixed(6));
              }}
              onUseMyLocation={handleUseMyLocation}
              isLocating={isLocating}
            />

            <div className="border border-[var(--border-hairline)] rounded-[3px] bg-[var(--bg-surface)] p-4 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-bold text-[var(--ink-primary)]">
                  {t.readinessHeading}
                </span>
                <span className="text-sm font-bold text-[var(--ink-primary)]">
                  {completeness.score}% ({tiers[completeness.tier] ?? completeness.tier})
                </span>
              </div>

              <div className="w-full h-2 bg-[var(--border-hairline)] rounded-[2px] overflow-hidden">
                <div
                  className="h-full transition-all"
                  style={{
                    width: `${completeness.score}%`,
                    backgroundColor: barColor,
                  }}
                />
              </div>

              <p className="text-xs text-[var(--ink-secondary)] leading-relaxed">
                {completeness.meetsMinimumHarvestable ? t.readinessPass : t.readinessFail}
              </p>

              <div className="border-t border-[var(--border-hairline)] pt-3 space-y-2">
                {completeness.checks.map((chk) => (
                  <div
                    key={chk.key}
                    className="flex items-center justify-between text-xs"
                  >
                    <span
                      className={
                        chk.passed
                          ? "text-[var(--ink-primary)] font-medium"
                          : "text-[var(--ink-secondary)]"
                      }
                    >
                      {checkLabels[chk.key]}
                    </span>
                    <span
                      className="font-mono font-medium"
                      style={{
                        color: chk.passed
                          ? "var(--status-emerald)"
                          : "var(--ink-secondary)",
                      }}
                    >
                      +{chk.points}/{chk.maxPoints}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
