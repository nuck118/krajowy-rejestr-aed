import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
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

function formatLevelLabel(
  rawLevel: string | null | undefined,
  t: (typeof TRANSLATIONS)[Locale]["detail"]
): string | null {
  const trimmed = rawLevel?.trim();
  if (!trimmed) return null;
  if (trimmed === "0") return `${t.levelGround} (0)`;
  return `${t.levelPrefix} ${trimmed}`;
}

export function AedDetailPanel({
  locale,
  aed,
  distanceMeters,
  onBack,
  onUpdated,
}: AedDetailPanelProps) {
  const [detail, setDetail] = useState<AEDDetailRecord | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [photoFailed, setPhotoFailed] = useState(false);
  const [showVerifyForm, setShowVerifyForm] = useState(false);
  const [verifyAction, setVerifyAction] = useState<VerificationAction>("confirm_operational");
  const [placementInput, setPlacementInput] = useState("");
  const [reporterOrg, setReporterOrg] = useState("");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const aedRef = useRef(aed);
  aedRef.current = aed;
  const onUpdatedRef = useRef(onUpdated);
  onUpdatedRef.current = onUpdated;

  const t = TRANSLATIONS[locale].detail;
  const tiers = TRANSLATIONS[locale].tiers;

  useEffect(() => {
    let cancelled = false;
    const initial = aedRef.current;
    setDetail(null);
    setIsLoadingDetail(true);
    setPhotoFailed(false);
    setFeedback(null);
    setShowVerifyForm(false);

    fetchAedDetail(aed.id)
      .then((res) => {
        if (cancelled) return;
        setDetail(res);
        if (
          res.location_description !== initial.location_description ||
          res.street_address !== initial.street_address ||
          res.city !== initial.city ||
          res.postal_code !== initial.postal_code ||
          res.completeness_score !== initial.completeness_score
        ) {
          onUpdatedRef.current(res);
        }
      })
      .catch(() => {
        // Basic record remains visible if detail fetch fails transiently
      })
      .finally(() => {
        if (!cancelled) setIsLoadingDetail(false);
      });

    return () => {
      cancelled = true;
    };
  }, [aed.id]);

  const active = detail ?? aed;
  const meta = detail?.extra_metadata;
  const formattedLevel = formatLevelLabel(meta?.level, t);
  const addressJoined = [active.street_address, active.postal_code, active.city]
    .filter(Boolean)
    .join(", ");
  const envValue =
    active.indoor === true
      ? t.envIndoor
      : active.indoor === false
        ? t.envOutdoor
        : t.envUnknown;
  const envSummary =
    active.indoor === true ? t.envIndoor : active.indoor === false ? t.envOutdoor : null;
  const accessLabel = t.accessTypes[active.access_type];

  const primaryTitle =
    (locale === "en" && meta?.location_en) ||
    active.location_description ||
    [addressJoined, meta?.operator, formattedLevel, envSummary, accessLabel]
      .filter(Boolean)
      .join(", ") ||
    t.noPlacementDesc;

  const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${active.latitude},${active.longitude}&travelmode=walking`;

  const scoreColor =
    active.completeness_score >= 80
      ? "var(--status-emerald)"
      : active.completeness_score >= 60
        ? "var(--gov-blue)"
        : "var(--aed-red)";

  const deviceModel = [meta?.manufacturer, meta?.model].filter(Boolean).join(" ");
  const sourceNote =
    meta?.note && meta.note !== active.location_description ? meta.note : null;

  const metadataRows: { key: string; label: string; value: ReactNode; highlight?: boolean }[] = [
    ...(distanceMeters !== undefined
      ? [
          {
            key: "distance",
            label: t.distanceLabel,
            highlight: true,
            value: (
              <span className="font-bold text-[var(--gov-blue)]">
                {formatDistance(distanceMeters)} ({walkingMinutes(distanceMeters)}{" "}
                {TRANSLATIONS[locale].mapView.minWalk})
              </span>
            ),
          },
        ]
      : []),
    {
      key: "address",
      label: t.addressLabel,
      value: <span className="font-medium">{addressJoined || t.addressEmpty}</span>,
    },
    ...(meta?.operator
      ? [{ key: "operator", label: t.operatorLabel, value: meta.operator }]
      : []),
    ...(formattedLevel
      ? [{ key: "level", label: t.levelLabel, value: formattedLevel }]
      : []),
    {
      key: "access",
      label: t.accessLabel,
      value: accessLabel,
    },
    {
      key: "reachability",
      label: t.reachabilityLabel,
      value: (
        <span
          className="font-semibold"
          style={{
            color:
              active.open_now === true
                ? "var(--status-emerald)"
                : active.open_now === false
                  ? "var(--aed-red)"
                  : "var(--ink-primary)",
          }}
        >
          {active.open_now === true
            ? t.reachableNow
            : active.open_now === false
              ? t.closedNow
              : t.reachabilityCheck}
        </span>
      ),
    },
    {
      key: "hours",
      label: t.hoursLabel,
      value: active.opening_hours || (active.is_24_7 ? "24/7" : t.hoursEmpty),
    },
    {
      key: "env",
      label: t.envLabel,
      value: envValue,
    },
    ...(meta?.phone
      ? [
          {
            key: "phone",
            label: t.phoneLabel,
            value: (
              <a
                href={`tel:${meta.phone.replace(/[^+\d]/g, "")}`}
                className="text-[var(--gov-blue)] hover:underline font-medium"
              >
                {meta.phone}
              </a>
            ),
          },
        ]
      : []),
    ...(meta?.wheelchair
      ? [{ key: "wheelchair", label: t.wheelchairLabel, value: meta.wheelchair }]
      : []),
    ...(deviceModel
      ? [{ key: "device", label: t.deviceLabel, value: deviceModel }]
      : []),
    ...(sourceNote
      ? [{ key: "note", label: t.noteLabel, value: sourceNote }]
      : []),
    ...(meta?.image_url && !photoFailed
      ? [
          {
            key: "photo",
            label: t.photoLabel,
            value: (
              <div className="space-y-1.5">
                <img
                  src={meta.image_url}
                  alt={primaryTitle}
                  onError={() => setPhotoFailed(true)}
                  className="max-h-40 rounded-[3px] border border-[var(--border-hairline)] object-cover"
                />
                <a
                  href={meta.image_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-[var(--gov-blue)] hover:underline"
                >
                  <span>{t.openPhoto}</span>
                  <ExternalLinkIcon className="w-3 h-3" />
                </a>
              </div>
            ),
          },
        ]
      : []),
    {
      key: "coords",
      label: t.coordsLabel,
      value: (
        <span className="font-mono text-xs">
          {active.latitude.toFixed(6)}, {active.longitude.toFixed(6)}
        </span>
      ),
    },
    {
      key: "sources",
      label: t.sourcesLabel,
      value: (
        <span className="font-mono text-xs">
          {(active.sources.length ? active.sources : [active.primary_source]).join(", ")}
        </span>
      ),
    },
    ...(meta?.osm_url
      ? [
          {
            key: "osm",
            label: t.osmLinkLabel,
            value: (
              <a
                href={meta.osm_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-medium text-[var(--gov-blue)] hover:underline"
              >
                <span>{t.osmOpenLink}</span>
                <ExternalLinkIcon className="w-3 h-3" />
              </a>
            ),
          },
        ]
      : []),
    {
      key: "verified",
      label: t.verifiedLabel,
      value: active.last_verified_at
        ? new Date(active.last_verified_at).toISOString().slice(0, 10)
        : t.verifiedEmpty,
    },
  ];

  const handleVerifySubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFeedback(null);
    const trimmedPlacement = placementInput.trim();
    try {
      const updated = await verifyAed(active.id, {
        action: verifyAction,
        reporter_org: reporterOrg.trim() || null,
        notes: notes.trim() || null,
        location_description: trimmedPlacement.length >= 3 ? trimmedPlacement : null,
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

  const phoneHref = meta?.phone ? `tel:${meta.phone.replace(/[^+\d]/g, "")}` : null;

  return (
    <section
      aria-label={t.sheetLabel}
      aria-busy={isLoadingDetail}
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
            {primaryTitle}
          </h2>
          {!active.location_description && (
            <p className="text-xs text-[var(--ink-secondary)]">
              {isLoadingDetail ? t.loadingDetail : t.placementHintMissing}
            </p>
          )}
        </div>

        {/* Physical Reachability Banner ("3 marca" context) */}
        {active.status === "out_of_service" ? (
          <div
            role="alert"
            className="p-3.5 rounded-[3px] border border-[var(--aed-red)] bg-[var(--bg-urgent)] space-y-1"
          >
            <div className="text-xs font-bold uppercase tracking-wide text-[var(--aed-red)]">
              {t.alertOutOfServiceTitle}
            </div>
            <p className="text-xs text-[var(--ink-primary)] leading-relaxed">
              {t.alertOutOfServiceBody}
            </p>
          </div>
        ) : active.open_now === false ? (
          <div
            role="alert"
            className="p-3.5 rounded-[3px] border border-[var(--aed-red)] bg-[var(--bg-urgent)] space-y-1.5"
          >
            <div className="text-xs font-bold uppercase tracking-wide text-[var(--aed-red)]">
              {t.alertClosedTitle}
            </div>
            <p className="text-xs text-[var(--ink-primary)] leading-relaxed">
              {t.alertClosedBody}
            </p>
            {phoneHref && meta?.phone && (
              <a
                href={phoneHref}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[var(--gov-blue)] hover:underline"
              >
                {t.callSecurityBtn}: {meta.phone}
              </a>
            )}
          </div>
        ) : active.access_type !== "public" ? (
          <div
            role="status"
            className="p-3.5 rounded-[3px] border border-[var(--status-amber)] bg-[var(--bg-amber)] space-y-1.5"
          >
            <div className="text-xs font-bold uppercase tracking-wide text-[var(--status-amber)]">
              {t.alertRestrictedTitle} ({accessLabel})
            </div>
            <p className="text-xs text-[var(--ink-primary)] leading-relaxed">
              {t.alertRestrictedBody}
            </p>
            {phoneHref && meta?.phone && (
              <a
                href={phoneHref}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[var(--gov-blue)] hover:underline"
              >
                {t.callSecurityBtn}: {meta.phone}
              </a>
            )}
          </div>
        ) : active.open_now === true ? (
          <div
            role="status"
            className="px-3.5 py-2.5 rounded-[3px] border border-[var(--status-emerald)] bg-[var(--bg-surface)] flex flex-wrap items-center justify-between gap-2 text-xs"
          >
            <span className="font-bold text-[var(--status-emerald)]">
              {t.reachableNow}
              {active.is_24_7 ? " (24/7)" : ""}
            </span>
            <span className="text-[var(--ink-secondary)]">{envValue}</span>
          </div>
        ) : null}

        <div className="border border-[var(--border-hairline)] rounded-[3px] divide-y divide-[var(--border-hairline)] text-sm">
          {metadataRows.map((row, idx) => (
            <div
              key={row.key}
              className={`grid grid-cols-3 p-3 gap-2 ${
                row.highlight
                  ? "bg-[var(--bg-callout)]"
                  : idx % 2 === 1
                    ? "bg-[var(--bg-surface)]"
                    : ""
              }`}
            >
              <span
                className={
                  row.highlight
                    ? "text-[var(--ink-primary)] font-medium"
                    : "text-[var(--ink-secondary)]"
                }
              >
                {row.label}
              </span>
              <div className="col-span-2 text-[var(--ink-primary)] self-center break-words">
                {row.value}
              </div>
            </div>
          ))}
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
          <div
            role="progressbar"
            aria-valuenow={active.completeness_score}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t.completenessHeading}
            className="w-full h-2 bg-[var(--border-hairline)] rounded-[2px] overflow-hidden"
          >
            <div
              className="h-full"
              style={{
                width: `${active.completeness_score}%`,
                backgroundColor: scoreColor,
              }}
            />
          </div>
        </div>

        <div
          className={`grid grid-cols-1 ${
            phoneHref ? "sm:grid-cols-3" : "sm:grid-cols-2"
          } gap-3 pt-1`}
        >
          <a
            href={directionsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="h-10 px-4 rounded-[3px] bg-[var(--gov-blue)] hover:bg-[var(--gov-blue-hover)] text-[var(--gov-blue-ink)] text-sm font-semibold flex items-center justify-center gap-2 transition-colors"
          >
            <span>{t.getDirections}</span>
            <ExternalLinkIcon className="w-4 h-4" />
          </a>
          {phoneHref && (
            <a
              href={phoneHref}
              className="h-10 px-4 rounded-[3px] border border-[var(--status-emerald)] bg-[var(--bg-canvas)] hover:bg-[var(--bg-surface)] text-[var(--status-emerald)] text-sm font-semibold flex items-center justify-center gap-2"
            >
              <span>{t.callSecurityBtn}</span>
            </a>
          )}
          <button
            type="button"
            onClick={() =>
              setShowVerifyForm((v) => {
                const next = !v;
                if (next) {
                  setPlacementInput(active.location_description ?? "");
                }
                return next;
              })
            }
            className="h-10 px-4 rounded-[3px] border border-[var(--gov-blue)] bg-[var(--bg-canvas)] hover:bg-[var(--bg-callout)] text-[var(--gov-blue)] text-sm font-semibold cursor-pointer"
          >
            {t.verifyButton}
          </button>
        </div>

        {feedback && (
          <div
            role="status"
            aria-live="polite"
            className="p-3 border border-[var(--status-emerald)] rounded-[3px] bg-[var(--bg-surface)] text-xs text-[var(--ink-primary)]"
          >
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
                htmlFor="verify-placement"
                className="block text-xs font-medium text-[var(--ink-primary)] mb-1"
              >
                {t.verifyPlacementLabel}
              </label>
              <input
                id="verify-placement"
                type="text"
                maxLength={500}
                value={placementInput}
                onChange={(e) => setPlacementInput(e.target.value)}
                placeholder={t.verifyPlacementPlaceholder}
                className="w-full h-9 px-2.5 text-sm rounded-[3px] bg-[var(--bg-canvas)] border border-[var(--border-input)] text-[var(--ink-primary)] focus:outline-none focus:border-[var(--gov-blue)]"
              />
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
