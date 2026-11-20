import type { AccessType, AedStatus } from "../types/aed";

export type CompletenessCheckKey =
  | "coords"
  | "placement"
  | "street"
  | "city"
  | "postalOrTeryt"
  | "access"
  | "hours"
  | "indoor"
  | "status"
  | "freshness";

export interface CompletenessInput {
  latitude: number | null;
  longitude: number | null;
  location_description: string | null;
  street_address: string | null;
  city: string | null;
  postal_code: string | null;
  teryt_code?: string | null;
  access_type: AccessType | string | null;
  opening_hours: string | null;
  is_24_7: boolean;
  indoor: boolean | null;
  status: AedStatus | string | null;
  last_verified_at: string | null;
}

export interface CompletenessCheck {
  key: CompletenessCheckKey;
  label: string;
  points: number;
  maxPoints: number;
  passed: boolean;
}

export interface CompletenessResult {
  score: number;
  tier: string;
  meetsMinimumHarvestable: boolean;
  checks: CompletenessCheck[];
}

const POSTAL_RE = /^\d{2}-\d{3}$/;
const TERYT_RE = /^\d{7}$/;
const VALID_ACCESS = new Set(["public", "customers_only", "private"]);

export function getCompletenessTier(score: number): string {
  if (score >= 80) return "Standard Compliant";
  if (score >= 60) return "Minimum Harvestable";
  return "Incomplete";
}

export function evaluateCompleteness(input: CompletenessInput): CompletenessResult {
  const checks: CompletenessCheck[] = [];

  const coordsValid =
    input.latitude !== null &&
    input.longitude !== null &&
    !Number.isNaN(input.latitude) &&
    !Number.isNaN(input.longitude) &&
    input.latitude >= 49.0 &&
    input.latitude <= 55.0 &&
    input.longitude >= 14.0 &&
    input.longitude <= 24.5;
  checks.push({
    key: "coords",
    label: "WGS84 coordinates inside Poland",
    points: coordsValid ? 20 : 0,
    maxPoints: 20,
    passed: coordsValid,
  });

  const desc = (input.location_description ?? "").trim();
  const descPts = desc.length >= 10 ? 25 : desc.length >= 3 ? 5 : 0;
  checks.push({
    key: "placement",
    label: "Placement description (>= 10 chars)",
    points: descPts,
    maxPoints: 25,
    passed: descPts === 25,
  });

  const hasStreet = Boolean((input.street_address ?? "").trim());
  checks.push({
    key: "street",
    label: "Street address",
    points: hasStreet ? 10 : 0,
    maxPoints: 10,
    passed: hasStreet,
  });

  const hasCity = Boolean((input.city ?? "").trim());
  checks.push({
    key: "city",
    label: "City / municipality",
    points: hasCity ? 10 : 0,
    maxPoints: 10,
    passed: hasCity,
  });

  const hasPostal = Boolean(input.postal_code && POSTAL_RE.test(input.postal_code.trim()));
  const hasTeryt = Boolean(input.teryt_code && TERYT_RE.test(input.teryt_code.trim()));
  checks.push({
    key: "postalOrTeryt",
    label: "Postal code (XX-XXX) or TERYT",
    points: hasPostal || hasTeryt ? 5 : 0,
    maxPoints: 5,
    passed: hasPostal || hasTeryt,
  });

  const hasAccess = Boolean(input.access_type && VALID_ACCESS.has(input.access_type));
  checks.push({
    key: "access",
    label: "Access classification",
    points: hasAccess ? 5 : 0,
    maxPoints: 5,
    passed: hasAccess,
  });

  const hasHours = input.is_24_7 || Boolean((input.opening_hours ?? "").trim());
  checks.push({
    key: "hours",
    label: "Opening hours / 24/7 schedule",
    points: hasHours ? 10 : 0,
    maxPoints: 10,
    passed: hasHours,
  });

  const hasIndoor = input.indoor !== null && input.indoor !== undefined;
  checks.push({
    key: "indoor",
    label: "Indoor / outdoor placement",
    points: hasIndoor ? 5 : 0,
    maxPoints: 5,
    passed: hasIndoor,
  });

  const isOp = input.status === "operational";
  checks.push({
    key: "status",
    label: "Operational status confirmed",
    points: isOp ? 5 : 0,
    maxPoints: 5,
    passed: isOp,
  });

  let isFresh = false;
  if (input.last_verified_at) {
    const dt = Date.parse(input.last_verified_at);
    if (!Number.isNaN(dt) && Date.now() - dt <= 365 * 24 * 3600 * 1000) {
      isFresh = true;
    }
  }
  checks.push({
    key: "freshness",
    label: "Verified within 365 days",
    points: isFresh ? 5 : 0,
    maxPoints: 5,
    passed: isFresh,
  });

  const score = checks.reduce((acc, item) => acc + item.points, 0);
  return {
    score,
    tier: getCompletenessTier(score),
    meetsMinimumHarvestable: score >= 60,
    checks,
  };
}
