export interface PriorityReason {
  factor: string;
  points: number;
  reason: string;
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
  priority_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  priority_reasons: PriorityReason[];
  required_crew: string;
  status: string;
  classification_confidence?: number | null;
  location_confidence?: number | null;
  needs_review: boolean;
}

export interface DashboardSummary {
  reports: number;
  incidents: number;
  high_or_critical: number;
  needs_review: number;
}
