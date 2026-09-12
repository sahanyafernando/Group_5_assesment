import type { Incident } from "../types";
import { AssignControl } from "./AssignControl";

interface Props {
  incidents: Incident[];
  onAssign: (incidentId: string, crew: string) => Promise<void>;
  onSelect: (incidentId: string) => void;
}

function badgeClass(level: string | null | undefined) {
  return `priority-badge priority-${(level ?? "unknown").toLowerCase()}`;
}

export function IncidentTable({ incidents, onAssign, onSelect }: Props) {
  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>
            <th>Priority level</th>
            <th>Score</th>
            <th>Incident</th>
            <th>Location</th>
            <th>Reports</th>
            <th>Crew</th>
            <th>Status</th>
          </tr>
        </thead>

        <tbody>
          {incidents.map((incident) => (
            <tr key={incident.id}>
              <td>
                <span className={badgeClass(incident.priority_level)}>
                  {incident.priority_level ?? "UNKNOWN"}
                </span>
              </td>

              <td>
                <strong className="mono">{incident.priority_score}</strong>
              </td>

              <td>
                <button
                  type="button"
                  className="incident-link"
                  onClick={() => onSelect(incident.id)}
                >
                  <div className="incident-title-row">
                    <strong>{incident.title}</strong>
                    {incident.needs_review && (
                      <span className="review-chip">Review</span>
                    )}
                  </div>
                  <small>
                    {incident.work_type ?? "Unknown work type"} ·{" "}
                    <span className="mono">{incident.incident_code}</span>
                  </small>
                </button>
              </td>

              <td>
                <strong>{incident.canonical_road ?? "Unresolved"}</strong>
                <small>{incident.ward ?? "Ward unavailable"}</small>
              </td>

              <td>
                <span className="report-count">{incident.report_count}</span>
              </td>

              <td>
                <AssignControl incident={incident} onAssign={onAssign} />
              </td>

              <td>
                <span className="status-chip">{incident.status}</span>
              </td>
            </tr>
          ))}

          {incidents.length === 0 && (
            <tr>
              <td colSpan={7} className="empty-state">
                No incidents match the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
