import { useEffect, useMemo, useState } from "react";

import { getIncidents, getSummary } from "./api";
import { DispatchBoard } from "./components/DispatchBoard";
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

  useEffect(() => {
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

    void load();
  }, []);

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
      <header className="topbar">
        <div>
          <span className="eyebrow">Muthuwella Municipal Council</span>
          <h1>Works Dispatch</h1>
          <p>Turn resident reports into clear, explainable crew decisions.</p>
        </div>

        <div className="morning-pill">
          <span>Morning triage</span>
          <strong>07:00 → 08:00</strong>
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
        </div>
      )}

      {loading ? (
        <div className="loading-state">Loading dispatch picture…</div>
      ) : view === "dashboard" ? (
        <>
          <SummaryCards summary={summary} />

          <section className="section-card">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Ranked by explainable priority</span>
                <h2>Today's incidents</h2>
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

            <IncidentTable incidents={filtered} />
          </section>
        </>
      ) : (
        <DispatchBoard incidents={incidents} />
      )}
    </main>
  );
}
