export interface PriorityReason {
  factor: string;
  points: number;
  reason: string;
  label?: string;
}

export interface RecentJobWarning {
  message?: string | null;
  days_ago?: number | null;
  [key: string]: unknown;
}

export interface SourceReport {
  id: string;
  source_report_id: string | null;
  channel?: string | null;
  received_at?: string | null;
  reporter_name?: string | null;
  location_text?: string | null;
  normalized_location?: string | null;
  description?: string | null;
  category?: string | null;
  urgency?: string | null;
  needs_review: boolean;
}

export interface IncidentInsight {
  summary: string;
  recommended_actions: string[];
  generated_at: string;
  insight_error?: string | null;
}

export interface Incident {
  id: string;
  incident_code: string;
  title: string;
  summary?: string | null;
  canonical_road?: string | null;
  ward?: string | null;
  category?: string | null;
  work_type?: string | null;
  severity?: string | null;
  report_count: number;
  priority_score: number;
  priority_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string | null;
  priority_reasons: PriorityReason[];
  required_crew: string | null;
  status: string;
  classification_confidence?: number | null;
  location_confidence?: number | null;
  needs_review: boolean;
}

export interface IncidentDetail extends Incident {
  road_class?: string | null;
  asset_types?: string[];
  nearest_facility?: string | null;
  facility_distance_m?: number | null;
  hazards?: string[];
  impact?: string[];
  first_reported_at?: string | null;
  latest_reported_at?: string | null;
  recent_job_warning?: RecentJobWarning | null;
  source_reports: SourceReport[];
}

export interface DashboardSummary {
  reports: number;
  incidents: number;
  high_or_critical: number;
  needs_review: number;
}
