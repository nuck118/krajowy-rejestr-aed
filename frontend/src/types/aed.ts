export type AccessType = "public" | "customers_only" | "private";
export type AedStatus = "operational" | "out_of_service" | "unverified";
export type VerificationAction =
  | "confirm_operational"
  | "report_out_of_service"
  | "report_missing";

export interface AEDRecord {
  id: string;
  latitude: number;
  longitude: number;
  street_address: string | null;
  city: string | null;
  postal_code: string | null;
  teryt_code: string | null;
  location_description: string | null;
  access_type: AccessType;
  opening_hours: string | null;
  is_24_7: boolean;
  indoor: boolean | null;
  status: AedStatus;
  last_verified_at: string | null;
  completeness_score: number;
  completeness_tier: string;
  primary_source: string;
  sources: string[];
  open_now: boolean | null;
  created_at: string;
  updated_at: string;
}

export interface AEDNearestRecord extends AEDRecord {
  distance_m: number;
  walking_minutes: number;
}

export interface SourceRecordSummary {
  id: string;
  source_name: string;
  source_trust_tier: number;
  external_id: string;
  ingested_at: string;
}

export interface AEDDetailRecord extends AEDRecord {
  provenance: SourceRecordSummary[];
}

export interface AEDCreatePayload {
  latitude: number;
  longitude: number;
  street_address: string | null;
  city: string | null;
  postal_code: string | null;
  teryt_code?: string | null;
  location_description: string;
  access_type: AccessType;
  opening_hours: string | null;
  is_24_7: boolean;
  indoor: boolean | null;
  status: AedStatus;
  last_verified_at?: string | null;
  source_name: string;
}

export interface AEDSubmitResponse {
  action: "created" | "merged";
  merged_distance_m: number | null;
  aed: AEDRecord;
}

export interface AEDVerifyPayload {
  action: VerificationAction;
  reporter_org?: string | null;
  notes?: string | null;
}

export interface PaginatedAEDResponse {
  total: number;
  limit: number;
  offset: number;
  items: AEDRecord[];
}

export interface NearestAEDResponse {
  origin: { lat: number; lng: number };
  radius_m: number;
  count: number;
  items: AEDNearestRecord[];
}

export interface SourceReconciliationRow {
  source_name: string;
  trust_tier: number;
  raw_records: number;
  valid_records: number;
  pass_rate_pct: number;
  duplicates_merged: number;
  last_sync_at: string | null;
  status: string;
}

export interface StatsResponse {
  total_unified_aeds: number;
  duplicates_merged: number;
  active_sources: number;
  national_completeness_avg: number;
  standard_compliant_count: number;
  minimum_harvestable_count: number;
  sources: SourceReconciliationRow[];
}

export interface IngestionRunResponse {
  id: string;
  source_name: string;
  status: string;
  records_fetched: number;
  records_valid: number;
  records_rejected: number;
  records_inserted: number;
  duplicates_merged: number;
  error_summary: string | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number;
}

export interface FinderFilters {
  openNow: boolean;
  is24_7: boolean;
  publicOnly: boolean;
  outdoorOnly: boolean;
}
