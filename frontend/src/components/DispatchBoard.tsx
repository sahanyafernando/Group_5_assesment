import type { Incident } from "../types";

interface Props {
  incidents: Incident[];
  onSelect: (incidentId: string) => void;
}

const CREWS = [
  "Road Surface",
  "Drainage",
  "Lighting & Street Furniture",
  "Manual Review",
];

export function DispatchBoard({ incidents, onSelect }: Props) {
  return (
    <section className="dispatch-grid">
      {CREWS.map((crew) => {
        const queue = incidents
          .filter((item) => item.required_crew === crew)
          .sort((a, b) => b.priority_score - a.priority_score);

        return (
          <article className="crew-column" key={crew}>
            <header>
              <h2>{crew}</h2>
              <span className="queue-count">{queue.length}</span>
            </header>

            <div className="crew-list">
              {queue.map((incident, index) => (
                <button
                  type="button"
                  className="dispatch-card"
                  key={incident.id}
                  onClick={() => onSelect(incident.id)}
                >
                  <div className="dispatch-rank mono">#{index + 1}</div>
                  <div>
                    <div className="dispatch-title">
                      <strong>{incident.title}</strong>
                      <span className="mono">{incident.priority_score}</span>
                    </div>
                    <p>{incident.canonical_road ?? "Location unresolved"}</p>
                    <small>
                      {incident.report_count} report(s) ·{" "}
                      {incident.priority_level ?? "UNKNOWN"}
                    </small>
                  </div>
                </button>
              ))}

              {queue.length === 0 && (
                <p className="empty-crew">No incidents in this queue.</p>
              )}
            </div>
          </article>
        );
      })}
    </section>
  );
}
