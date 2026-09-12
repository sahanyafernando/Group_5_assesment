import type { Incident } from "../types";

interface Props {
  incidents: Incident[];
}

const CREWS = [
  "Road Surface",
  "Drainage",
  "Lighting & Street Furniture",
  "Manual Review",
];

export function DispatchBoard({ incidents }: Props) {
  return (
    <section className="dispatch-grid">
      {CREWS.map((crew) => {
        const queue = incidents
          .filter((item) => item.required_crew === crew)
          .sort((a, b) => b.priority_score - a.priority_score);

        return (
          <article className="crew-column" key={crew}>
            <header>
              <div>
                <span className="eyebrow">Crew queue</span>
                <h2>{crew}</h2>
              </div>
              <span className="queue-count">{queue.length}</span>
            </header>

            <div className="crew-list">
              {queue.map((incident, index) => (
                <div className="dispatch-card" key={incident.id}>
                  <div className="dispatch-rank">#{index + 1}</div>
                  <div>
                    <div className="dispatch-title">
                      <strong>{incident.title}</strong>
                      <span>{incident.priority_score}</span>
                    </div>
                    <p>{incident.canonical_road ?? "Location unresolved"}</p>
                    <small>
                      {incident.report_count} report(s) · {incident.priority_level}
                    </small>
                  </div>
                </div>
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
