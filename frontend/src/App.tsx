import { useEffect, useMemo, useState } from "react";

import { assignCrew, getIncidents, getSummary } from "./api";
import { DispatchBoard } from "./components/DispatchBoard";
import { IncidentDetailPanel } from "./components/IncidentDetailPanel";
import { IncidentTable } from "./components/IncidentTable";
import { SummaryCards } from "./components/SummaryCards";
import type { DashboardSummary, Incident } from "./types";

type View = "dashboard" | "dispatch";

const EMPTY_SUMMARY: DashboardSummary = {
  reports: 0,
  incidents: 0,
  high_or_critical: 0,
  needs_review: 0,
};

export default function App() {
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [view, setView] = useState<View>("dashboard");
  const [search, setSearch] = useState("");
  const [crewFilter, setCrewFilter] = useState("All crews");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      const [summaryData, incidentData] = await Promise.all([
        getSummary(),
        getIncidents(),
      ]);
      setSummary(summaryData);
      setIncidents(incidentData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleAssign(incidentId: string, crew: string) {
    const updated = await assignCrew(incidentId, crew);
    setIncidents((prev) =>
      prev.map((incident) => (incident.id === incidentId ? updated : incident)),
    );
  }

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();

    return incidents.filter((incident) => {
      const searchMatch =
        !needle ||
        incident.title.toLowerCase().includes(needle) ||
        (incident.canonical_road ?? "").toLowerCase().includes(needle) ||
        (incident.work_type ?? "").toLowerCase().includes(needle);

      const crewMatch =
        crewFilter === "All crews" || incident.required_crew === crewFilter;

      return searchMatch && crewMatch;
    });
  }, [incidents, search, crewFilter]);

  return (
    <main className="app-shell">
      <header className="console-header">
        <div className="console-header__identity">
          <h1>Muthuwella Works Dispatch</h1>
          <p>
            Public Works coordination console — turn resident reports into clear,
            explainable crew decisions.
          </p>
        </div>

        <div className="console-readout">
          <span>Morning triage window</span>
          <strong className="mono">07:00 — 08:00</strong>
        </div>
      </header>

      <nav className="view-tabs" aria-label="Main views">
        <button
          className={view === "dashboard" ? "active" : ""}
          onClick={() => setView("dashboard")}
        >
          Incident dashboard
        </button>
        <button
          className={view === "dispatch" ? "active" : ""}
          onClick={() => setView("dispatch")}
        >
          Crew dispatch
        </button>
      </nav>

      {error && (
        <div className="error-banner">
          <strong>API unavailable.</strong>
          <span>{error}</span>
          <button className="retry-button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <DashboardSkeleton />
      ) : view === "dashboard" ? (
        <>
          <SummaryCards summary={summary} />

          <section className="sheet">
            <div className="sheet-heading">
              <div>
                <h2>Today's incidents</h2>
                <p className="sheet-subtitle">Ranked by explainable priority score.</p>
              </div>

              <div className="filters">
                <input
                  type="search"
                  placeholder="Search incident or road…"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
                <select
                  value={crewFilter}
                  onChange={(event) => setCrewFilter(event.target.value)}
                >
                  <option>All crews</option>
                  <option>Road Surface</option>
                  <option>Drainage</option>
                  <option>Lighting & Street Furniture</option>
                  <option>Manual Review</option>
                </select>
              </div>
            </div>

            <IncidentTable
              incidents={filtered}
              onAssign={handleAssign}
              onSelect={setSelectedIncidentId}
            />
          </section>
        </>
      ) : (
        <DispatchBoard incidents={incidents} onSelect={setSelectedIncidentId} />
      )}

      {selectedIncidentId && (
        <IncidentDetailPanel
          incidentId={selectedIncidentId}
          onClose={() => setSelectedIncidentId(null)}
          onAssign={handleAssign}
        />
      )}
    </main>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <div className="skeleton-strip" aria-hidden="true">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="skeleton-cell" key={index}>
            <div className="skeleton" style={{ width: "70%" }} />
            <div className="skeleton" />
          </div>
        ))}
      </div>

      <div className="sheet">
        <div className="skeleton-rows" aria-hidden="true">
          {Array.from({ length: 6 }).map((_, index) => (
            <div className="skeleton skeleton-row" key={index} />
          ))}
        </div>
      </div>
    </>
  );
}
