import type { DashboardSummary, Incident, IncidentDetail, IncidentInsight } from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }

  return response.json() as Promise<T>;
}

function postJSON<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getSummary(): Promise<DashboardSummary> {
  return request<DashboardSummary>("/dashboard/summary");
}

export function getIncidents(): Promise<Incident[]> {
  return request<Incident[]>("/incidents");
}

export function assignCrew(
  incidentId: string,
  crew: string,
  notes?: string,
): Promise<Incident> {
  return postJSON<Incident>(`/incidents/${incidentId}/assign`, {
    crew,
    notes,
  });
}

export function getIncidentDetail(incidentId: string): Promise<IncidentDetail> {
  return request<IncidentDetail>(`/incidents/${incidentId}`);
}

export function getIncidentInsight(incidentId: string): Promise<IncidentInsight> {
  return postJSON<IncidentInsight>(`/incidents/${incidentId}/ai-insight`, {});
}
