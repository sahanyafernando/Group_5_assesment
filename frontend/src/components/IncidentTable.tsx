import type { Incident } from "../types";

interface Props {
  incidents: Incident[];
}

function badgeClass(level: string) {
  return `priority-badge priority-${level.toLowerCase()}`;
}

export function IncidentTable({ incidents }: Props) {
  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>
            <th>Priority</th>
            <th>Incident</th>
            <th>Location</th>
            <th>Reports</th>
            <th>Required crew</th>
            <th>Status</th>
          </tr>
        </thead>

        <tbody>
          {incidents.map((incident) => (
            <tr key={incident.id}>
              <td>
                <div className="priority-cell">
                  <span className={badgeClass(incident.priority_level)}>
                    {incident.priority_level}
                  </span>
                  <strong>{incident.priority_score}</strong>
                </div>
              </td>

              <td>
                <div className="incident-title-row">
                  <strong>{incident.title}</strong>
                  {incident.needs_review && (
                    <span className="review-chip">Review</span>
                  )}
                </div>
                <small>
                  {incident.work_type ?? "Unknown work type"} ·{" "}
                  {incident.incident_code}
                </small>
              </td>

              <td>
                <strong>{incident.canonical_road ?? "Unresolved"}</strong>
                <small>{incident.ward ?? "Ward unavailable"}</small>
              </td>

              <td>
                <span className="report-count">{incident.report_count}</span>
              </td>

              <td>{incident.required_crew}</td>

              <td>
                <span className="status-chip">{incident.status}</span>
              </td>
            </tr>
          ))}

          {incidents.length === 0 && (
            <tr>
              <td colSpan={6} className="empty-state">
                No incidents match the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
