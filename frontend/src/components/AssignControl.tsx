import { useState } from "react";

import type { Incident } from "../types";

export const CREWS = [
  "Road Surface",
  "Drainage",
  "Lighting & Street Furniture",
  "Manual Review",
];

const ASSIGNED_STATUSES = new Set(["Assigned", "In Progress", "Completed"]);

interface Props {
  incident: Incident;
  onAssign: (incidentId: string, crew: string) => Promise<void>;
}

export function AssignControl({ incident, onAssign }: Props) {
  const [crew, setCrew] = useState(incident.required_crew ?? CREWS[0]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  const alreadyAssigned = ASSIGNED_STATUSES.has(incident.status);
  const isSuggestion = crew === incident.required_crew && !alreadyAssigned;

  async function handleClick() {
    setPending(true);
    setError(null);
    setConfirmed(false);
    try {
      await onAssign(incident.id, crew);
      setConfirmed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assignment failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="assign-control">
      <select
        className="assign-select"
        value={crew}
        onChange={(event) => {
          setCrew(event.target.value);
          setConfirmed(false);
        }}
        disabled={pending}
      >
        {CREWS.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>

      <button className="assign-button" onClick={handleClick} disabled={pending}>
        {pending
          ? "Assigning…"
          : alreadyAssigned
            ? "Reassign"
            : isSuggestion
              ? "Approve & assign"
              : "Assign"}
      </button>

      {confirmed && <small className="assign-feedback assign-feedback--ok">Assigned</small>}
      {error && <small className="assign-feedback assign-feedback--error">{error}</small>}
    </div>
  );
}
