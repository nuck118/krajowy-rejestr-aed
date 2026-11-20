import { useEffect, useState, type FormEvent } from "react";
import { fetchAedDetail, verifyAed } from "../../api/client";
import { TRANSLATIONS, type Locale } from "../../i18n/translations";
import type {
  AEDDetailRecord,
  AEDRecord,
  VerificationAction,
} from "../../types/aed";
import { formatDistance, walkingMinutes } from "../../utils/geo";
import { CloseIcon, ExternalLinkIcon } from "../icons/Icons";

interface AedDetailPanelProps {
  locale: Locale;
  aed: AEDRecord;
  distanceMeters?: number;
  onBack: () => void;
  onUpdated: (updated: AEDRecord) => void;
}

export function AedDetailPanel({
  locale,
  aed,
  distanceMeters,
  onBack,
  onUpdated,
}: AedDetailPanelProps) {
  const [detail, setDetail] = useState<AEDDetailRecord | null>(null);
  const [showVerifyForm, setShowVerifyForm] = useState(false);
  const [verifyAction, setVerifyAction] = useState<VerificationAction>("confirm_operational");
  const [reporterOrg, setReporterOrg] = useState("");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const t = TRANSLATIONS[locale].detail;
  const tiers = TRANSLATIONS[locale].tiers;

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setFeedback(null);
    setShowVerifyForm(false);
    fetchAedDetail(aed.id)
      .then((res) => {
        if (!cancelled) setDetail(res);
      })
      .catch(() => {
        // Basic record remains visible if detail fetch fails transiently
      });
    return () => {
      cancelled = true;
    };
  }, [aed.id]);

  const active = detail ?? aed;
  const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${active.latitude},${active.longitude}&travelmode=walking`;

  const scoreColor =
    active.completeness_score >= 80
      ? "var(--status-emerald)"
      : active.completeness_score >= 60
        ? "var(--gov-blue)"
        : "var(--aed-red)";

  const handleVerifySubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const updated = await verifyAed(active.id, {
        action: verifyAction,
        reporter_org: reporterOrg.trim() || null,
        notes: notes.trim() || null,
      });
      onUpdated(updated);
      setDetail((prev) => (prev ? { ...prev, ...updated } : null));
      setShowVerifyForm(false);
      setNotes("");
      setFeedback(t.verifySuccess);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section
      aria-label={t.sheetLabel}
      className="border border-[var(--border-hairline)] rounded-[4px] bg-[var(--bg-canvas)] overflow-hidden"
    >
      <div className="px-5 py-3.5 border-b border-[var(--border-hairline)] flex items-center justify-between gap-2 bg-[var(--bg-surface)]">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-[var(--ink-secondary)] block">
            {t.sheetLabel}
          </span>
          <span className="font-mono text-[11px] text-[var(--ink-secondary)]">
            ID: {active.id}
          </span>
        </div>
        <button
          type="button"
          onClick={onBack}
          aria-label={t.close}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[3px] border border-[var(--border-hairline)] bg-[var(--bg-canvas)] text-xs font-medium text-[var(--ink-primary)] hover:border-[var(--gov-blue)] cursor-pointer"
        >
          <CloseIcon className="w-3.5 h-3.5" />
          <span>{t.close}</span>
        </button>
      </div>

      <div className="p-5 space-y-5">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-[var(--ink-secondary)]">
              {t.placementHeading}
            </span>
            <span
              className="text-xs font-semibold px-2.5 py-0.5 rounded-[2px] border"
              style={{
                borderColor:
                  active.status === "operational"
                    ? "var(--status-emerald)"
                    : active.status === "out_of_service"
                      ? "var(--aed-red)"
                      : "var(--border-hairline)",
                color:
                  active.status === "operational"
                    ? "var(--status-emerald)"
                    : active.status === "out_of_service"
                      ? "var(--aed-red)"
                      : "var(--ink-secondary)",
              }}
            >
              {t.statuses[active.status]}
            </span>
          </div>
          <h2 className="text-lg font-bold text-[var(--ink-primary)] leading-snug">
            {active.location_description || t.noPlacementDesc}
          </h2>
        </div>

        <div className="border border-[var(--border-hairline)] rounded-[3px] divide-y divide-[var(--border-hairline)] text-sm">
          {distanceMeters !== undefined && (
            <div className="grid grid-cols-3 p-3 gap-2 bg-[var(--bg-callout)]">
              <span className="text-[var(--ink-primary)] font-medium">{t.distanceLabel}</span>
              <span className="col-span-2 font-bold text-[var(--gov-blue)]">
                {formatDistance(distanceMeters)} ({walkingMinutes(distanceMeters)}{" "}
                {TRANSLATIONS[locale].mapView.minWalk})
              </span>
            </div>
          )}
          <div className="grid grid-cols-3 p-3 gap-2">
            <span className="text-[var(--ink-secondary)]">{t.addressLabel}</span>
            <span className="col-span-2 text-[var(--ink-primary)] font-medium">
              {[active.street_address, active.postal_code, active.city]
                .filter(Boolean)
                .join(", ") || t.addressEmpty}
            </span>
          </div>
          <div className="grid grid-cols-3 p-3 gap-2 bg-[var(--bg-surface)]">
            <span className="text-[var(--ink-secondary)]">{t.accessLabel}</span>
            <span className="col-span-2 text-[var(--ink-primary)]">
              {t.accessTypes[active.access_type]}
            </span>
          </div>
          <div className="grid grid-cols-3 p-3 gap-2">
            <span className="text-[var(--ink-secondary)]">{t.hoursLabel}</span>
            <span className="col-span-2 text-[var(--ink-primary)]">
              {active.opening_hours || (active.is_24_7 ? "24/7" : t.hoursEmpty)}
            </span>
          </div>
          <div className="grid grid-cols-3 p-3 gap-2 bg-[var(--bg-surface)]">
            <span className="text-[var(--ink-secondary)]">{t.envLabel}</span>
            <span className="col-span-2 text-[var(--ink-primary)]">
              {active.indoor === true
                ? t.envIndoor
                : active.indoor === false
                  ? t.envOutdoor
                  : t.envUnknown}
            </span>
          </div>
          <div className="grid grid-cols-3 p-3 gap-2">
            <span className="text-[var(--ink-secondary)]">{t.coordsLabel}</span>
            <span className="col-span-2 font-mono text-xs text-[var(--ink-primary)] self-center">
              {active.latitude.toFixed(6)}, {active.longitude.toFixed(6)}
            </span>
          </div>
          <div className="grid grid-cols-3 p-3 gap-2 bg-[var(--bg-surface)]">
            <span className="text-[var(--ink-secondary)]">{t.sourcesLabel}</span>
            <span className="col-span-2 font-mono text-xs text-[var(--ink-primary)] self-center">
              {(active.sources.length ? active.sources : [active.primary_source]).join(", ")}
            </span>
          </div>
          <div className="grid grid-cols-3 p-3 gap-2">
            <span className="text-[var(--ink-secondary)]">{t.verifiedLabel}</span>
            <span className="col-span-2 text-[var(--ink-primary)]">
              {active.last_verified_at
                ? new Date(active.last_verified_at).toISOString().slice(0, 10)
                : t.verifiedEmpty}
            </span>
          </div>
        </div>

        <div className="space-y-2 pt-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[var(--ink-secondary)] font-semibold">
              {t.completenessHeading}
            </span>
            <span className="font-semibold text-[var(--ink-primary)]">
              {active.completeness_score}% ({tiers[active.completeness_tier] ?? active.completeness_tier})
            </span>
          </div>
          <div className="w-full h-2 bg-[var(--border-hairline)] rounded-[2px] overflow-hidden">
            <div
              className="h-full"
              style={{
                width: `${active.completeness_score}%`,
                backgroundColor: scoreColor,
              }}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          <a
            href={directionsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="h-10 px-4 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-[var(--gov-blue-ink)] text-sm font-semibold flex items-center justify-center gap-2 transition-colors"
          >
            <span>{t.getDirections}</span>
            <ExternalLinkIcon className="w-4 h-4" />
          </a>
          <button
            type="button"
            onClick={() => setShowVerifyForm((v) => !v)}
            className="h-10 px-4 rounded-[3px] border border-[var(--gov-blue)] bg-[var(--bg-canvas)] hover:bg-[var(--bg-callout)] text-[var(--gov-blue)] text-sm font-semibold cursor-pointer"
          >
            {t.verifyButton}
          </button>
        </div>

        {feedback && (
          <div className="p-3 border border-[var(--status-emerald)] rounded-[3px] bg-[var(--bg-surface)] text-xs text-[var(--ink-primary)]">
            {feedback}
          </div>
        )}

        {showVerifyForm && (
          <form
            onSubmit={handleVerifySubmit}
            className="border border-[var(--border-hairline)] rounded-[3px] p-4 bg-[var(--bg-surface)] space-y-3"
          >
            <div className="text-sm font-bold text-[var(--ink-primary)]">
              {t.verifyFormTitle}
            </div>
            <div>
              <label
                htmlFor="verify-action"
                className="block text-xs font-medium text-[var(--ink-primary)] mb-1"
              >
                {t.verifyOutcomeLabel}
              </label>
              <select
                id="verify-action"
                value={verifyAction}
                onChange={(e) => setVerifyAction(e.target.value as VerificationAction)}
                className="w-full h-9 px-2.5 text-sm rounded-[3px] bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
              >
                <option value="confirm_operational">{t.verifyConfirm}</option>
                <option value="report_out_of_service">{t.verifyBroken}</option>
                <option value="report_missing">{t.verifyMissing}</option>
              </select>
            </div>
            <div>
              <label
                htmlFor="verify-org"
                className="block text-xs font-medium text-[var(--ink-primary)] mb-1"
              >
                {t.verifyOrgLabel}
              </label>
              <input
                id="verify-org"
                type="text"
                value={reporterOrg}
                onChange={(e) => setReporterOrg(e.target.value)}
                placeholder={t.verifyOrgPlaceholder}
                className="w-full h-9 px-2.5 text-sm rounded-[3px] bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
              />
            </div>
            <div>
              <label
                htmlFor="verify-notes"
                className="block text-xs font-medium text-[var(--ink-primary)] mb-1"
              >
                {t.verifyNotesLabel}
              </label>
              <textarea
                id="verify-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                placeholder={t.verifyNotesPlaceholder}
                className="w-full p-2.5 text-sm rounded-[3px] bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
              />
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowVerifyForm(false)}
                className="px-3 py-1.5 text-xs font-medium text-[var(--ink-secondary)] hover:text-[var(--ink-primary)] cursor-pointer"
              >
                {t.cancel}
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="h-9 px-4 rounded-[3px] text-xs font-semibold bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-[var(--gov-blue-ink)] cursor-pointer disabled:opacity-50"
              >
                {isSubmitting ? t.saving : t.submitVerify}
              </button>
            </div>
          </form>
        )}

        {detail && detail.provenance.length > 0 && (
          <div className="pt-2 border-t border-[var(--border-hairline)] space-y-2">
            <h3 className="text-xs font-semibold text-[var(--ink-secondary)] uppercase tracking-wide">
              {t.provenanceHeading} ({detail.provenance.length})
            </h3>
            <div className="border border-[var(--border-hairline)] rounded-[3px] divide-y divide-[var(--border-hairline)]">
              {detail.provenance.map((sr) => (
                <div
                  key={sr.id}
                  className="px-3 py-2 flex items-center justify-between text-xs"
                >
                  <span className="font-medium text-[var(--ink-primary)]">
                    {sr.source_name}{" "}
                    <span className="text-[var(--ink-secondary)] font-normal">
                      ({t.tierLabel} {sr.source_trust_tier})
                    </span>
                  </span>
                  <span className="font-mono text-[11px] text-[var(--ink-secondary)] truncate max-w-[200px]">
                    {sr.external_id}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
