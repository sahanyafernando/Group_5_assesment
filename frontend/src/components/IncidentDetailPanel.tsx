import { useEffect, useState } from "react";

import { getIncidentDetail, getIncidentInsight } from "../api";
import type { IncidentDetail, IncidentInsight } from "../types";
import { AssignControl } from "./AssignControl";

interface Props {
  incidentId: string;
  onClose: () => void;
  onAssign: (incidentId: string, crew: string) => Promise<void>;
}

function badgeClass(level: string | null | undefined) {
  return `priority-badge priority-${(level ?? "unknown").toLowerCase()}`;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function IncidentDetailPanel({ incidentId, onClose, onAssign }: Props) {
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [insight, setInsight] = useState<IncidentInsight | null>(null);
  const [insightLoading, setInsightLoading] = useState(false);
  const [insightError, setInsightError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setInsight(null);
    setInsightError(null);
    setError(null);
    setLoading(true);

    getIncidentDetail(incidentId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load incident.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [incidentId]);

  async function handleGetInsight() {
    setInsightLoading(true);
    setInsightError(null);
    try {
      const result = await getIncidentInsight(incidentId);
      setInsight(result);
    } catch (err) {
      setInsightError(err instanceof Error ? err.message : "AI insight failed.");
    } finally {
      setInsightLoading(false);
    }
  }

  return (
    <div className="panel-overlay" onClick={onClose}>
      <aside
        className="panel"
        role="dialog"
        aria-label="Incident detail"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="panel-header">
          <div>
            {detail && <span className="mono panel-code">{detail.incident_code}</span>}
            <h2>{detail?.title ?? "Loading…"}</h2>
          </div>
          <button type="button" className="panel-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        {loading && <div className="loading-state">Loading incident…</div>}
        {error && <div className="error-banner">{error}</div>}

        {detail && (
          <div className="panel-body">
            <div className="panel-row">
              <span className={badgeClass(detail.priority_level)}>
                {detail.priority_level ?? "UNKNOWN"}
              </span>
              <strong className="mono panel-score">{detail.priority_score}</strong>
              <span className="status-chip">{detail.status}</span>
              {detail.needs_review && <span className="review-chip">Review</span>}
            </div>

            {detail.summary && <p className="panel-summary">{detail.summary}</p>}

            <section className="panel-section">
              <h3>Location</h3>
              <p>
                <strong>{detail.canonical_road ?? "Unresolved"}</strong>
                {detail.ward ? ` · ${detail.ward}` : ""}
                {detail.road_class ? ` · ${detail.road_class}` : ""}
              </p>
              {detail.nearest_facility && (
                <p className="panel-muted">
                  Nearest facility: {detail.nearest_facility}
                  {detail.facility_distance_m != null
                    ? ` (${Math.round(detail.facility_distance_m)}m)`
                    : ""}
                </p>
              )}
            </section>

            <section className="panel-section">
              <h3>Classification</h3>
              <p>
                {detail.work_type ?? "Unknown"} · {detail.category ?? "Uncategorized"} ·
                severity: {detail.severity ?? "unknown"}
              </p>
              {(detail.hazards ?? []).length > 0 && (
                <ul className="panel-list">
                  {(detail.hazards ?? []).map((hazard) => (
                    <li key={hazard}>{hazard}</li>
                  ))}
                </ul>
              )}
            </section>

            <section className="panel-section">
              <h3>Why this priority</h3>
              <ul className="panel-reasons">
                {detail.priority_reasons.map((reason, index) => (
                  <li key={index}>{reason.label ?? `+${reason.points} ${reason.reason}`}</li>
                ))}
              </ul>
            </section>

            {detail.recent_job_warning?.message && (
              <section className="panel-section panel-warning">
                <h3>Recent work on this road</h3>
                <p>{detail.recent_job_warning.message}</p>
              </section>
            )}

            <section className="panel-section">
              <h3>Crew assignment</h3>
              <AssignControl incident={detail} onAssign={onAssign} />
            </section>

            <section className="panel-section">
              <div className="panel-section-heading">
                <h3>AI insight</h3>
                <button
                  type="button"
                  className="assign-button"
                  onClick={handleGetInsight}
                  disabled={insightLoading}
                >
                  {insightLoading ? "Thinking…" : insight ? "Regenerate" : "Get AI insight"}
                </button>
              </div>

              {insightError && (
                <p className="panel-muted assign-feedback--error">{insightError}</p>
              )}

              {insight && (
                <div className="panel-insight">
                  <p>{insight.summary}</p>
                  {insight.recommended_actions.length > 0 && (
                    <ul className="panel-list">
                      {insight.recommended_actions.map((action, index) => (
                        <li key={index}>{action}</li>
                      ))}
                    </ul>
                  )}
                  {insight.insight_error && (
                    <p className="panel-muted">Note: {insight.insight_error}</p>
                  )}
                </div>
              )}
            </section>

            <section className="panel-section">
              <h3>Source reports ({detail.source_reports.length})</h3>
              <ul className="panel-reports">
                {detail.source_reports.map((report) => (
                  <li key={report.id}>
                    <div className="panel-report-meta">
                      <span className="mono">{report.source_report_id ?? report.id}</span>
                      <span>{formatDate(report.received_at)}</span>
                    </div>
                    <p>{report.description || report.location_text || "No description."}</p>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}
      </aside>
    </div>
  );
}
