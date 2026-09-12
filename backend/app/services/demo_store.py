"""In-memory mutation helpers for demo mode.

DEMO_MODE lets the dashboard run before Supabase is configured (README.md
"Quick start"). Status/assign/override actions need somewhere to write to in
that mode too, so Person C can build and demo the workflow offline. This is a
plain in-process list -- it resets on restart, same as the rest of demo mode.
"""

from copy import deepcopy

from app.services.demo_data import DEMO_INCIDENTS

# A working copy, so importing this module twice in tests never shares state
# with a mutated DEMO_INCIDENTS from an earlier test.
_incidents: list[dict] = deepcopy(DEMO_INCIDENTS)
_overrides: list[dict] = []
_next_override_id = 1


def reset() -> None:
    """Restore the demo incidents to their original shipped values. Tests only."""
    global _incidents, _overrides, _next_override_id
    _incidents = deepcopy(DEMO_INCIDENTS)
    _overrides = []
    _next_override_id = 1


def list_incidents() -> list[dict]:
    return list(_incidents)


def find_incident(incident_id: str) -> dict | None:
    for incident in _incidents:
        if incident["id"] == incident_id:
            return incident
    return None


def update_incident(incident_id: str, fields: dict) -> dict:
    incident = find_incident(incident_id)
    if incident is None:
        raise RuntimeError(f"Incident {incident_id} not found; nothing updated.")
    incident.update(fields)
    return incident


def record_override(
    incident_id: str,
    field_name: str,
    previous_value,
    new_value,
    *,
    reason: str | None = None,
    changed_by: str = "Maya",
) -> dict:
    global _next_override_id
    row = {
        "id": f"demo-override-{_next_override_id}",
        "incident_id": incident_id,
        "field_name": field_name,
        "previous_value": previous_value,
        "new_value": new_value,
        "reason": reason,
        "changed_by": changed_by,
    }
    _next_override_id += 1
    _overrides.append(row)
    return row


def list_overrides(incident_id: str | None = None) -> list[dict]:
    if incident_id is None:
        return list(_overrides)
    return [row for row in _overrides if row["incident_id"] == incident_id]
