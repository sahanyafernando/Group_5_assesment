"""AI incident summarization (Person A, Step 6).

Generates actionable titles and summaries for incidents so the works
coordinator can understand the issue without reading individual reports.
Batches 3-5 incidents per Claude call to reduce API calls.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BATCH_SIZE = 4

_INSIGHT_SYSTEM_PROMPT = """You are helping a municipal works coordinator quickly \
understand one already-consolidated incident and what she might want to check \
before acting on it.

You MUST NOT:
- assign a crew or state a priority/score
- claim a job already resolves this incident
- invent facts, causes, or hazards not present in the reports

recommended_actions are things worth checking or considering, not instructions \
she must follow - phrase them as suggestions (e.g. "Confirm..." or "Consider..."), \
never as decisions already made. Give 2-4 short, specific items grounded in what \
the reports actually say (mention concrete details: location, hazards, timing, \
prior work) rather than generic advice like "assign a crew" or "monitor situation".

Return valid JSON only, no markdown, no explanation:
{
  "summary": "2-3 sentence actionable summary",
  "recommended_actions": ["...", "..."]
}
"""

_SYSTEM_PROMPT = """You are writing brief work summaries for a municipal works coordinator.
She uses these summaries to decide what to do, without reading individual reports.

Rules:
- Describe what the problem is clearly
- Mention specific location details (house numbers, landmarks, distances)
- Mention meaningful impact or hazards if reported
- Mention how long the problem has persisted if known
- Do NOT invent causes or details not in the reports
- Do NOT repeat every report individually
- Keep titles under 10 words, summaries 2-3 sentences max
- Return valid JSON only, no markdown, no explanation
"""

_RESULT_SHAPE = """{
  "title": "Short title under 10 words",
  "summary": "2-3 sentence actionable summary"
}"""


def _extract_json(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _format_timestamp(ts):
    """Format a timestamp for human readability."""
    if not ts:
        return None
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return ts
    if isinstance(ts, datetime):
        return ts.strftime("%d %b %Y")
    return str(ts)


async def summarize_incident(client, incident: dict, reports: list[dict]) -> dict:
    """Generate title + summary for one incident.

    Args:
        client: Anthropic client
        incident: incidents table row
        reports: raw_reports rows linked to this incident

    Returns: {title, summary, prompt, response}
    """
    from app.core.config import get_settings

    settings = get_settings()

    # Build the report descriptions for the prompt
    descriptions = []
    for i, report in enumerate(reports[:5], 1):
        desc = (report.get("description") or "").strip()
        if not desc:
            desc = report.get("location_text") or "(no description)"
        descriptions.append(f'{i}. "{desc[:120]}"')

    report_list = "\n".join(descriptions)
    first_reported = _format_timestamp(incident.get("first_reported_at"))
    latest_reported = _format_timestamp(incident.get("latest_reported_at"))
    time_span = f"{first_reported} to {latest_reported}" if first_reported else "unknown"

    user_prompt = f"""Incident: {incident.get('work_type', 'Unknown')} on {incident.get('canonical_road', 'Unknown Road')}
Number of reports: {incident.get('report_count', 1)}
Time span: {time_span}

Source reports:
{report_list}

Write a title and summary as JSON:
{_RESULT_SHAPE}"""

    try:
        message = await asyncio.to_thread(
            client.messages.create,
            model=settings.claude_model,
            max_tokens=300,
            temperature=0,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_response = "\n".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        parsed = _extract_json(raw_response)
    except Exception:
        logger.exception("Summarization failed for incident %s", incident.get("incident_code"))
        return None

    return {
        "title": parsed.get("title", incident.get("title")),
        "summary": parsed.get("summary", ""),
        "prompt": user_prompt,
        "response": raw_response,
    }


def _degraded_insight(reason: str) -> dict:
    return {
        "summary": "AI insight unavailable; review the source reports below directly.",
        "recommended_actions": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "insight_error": reason,
    }


async def generate_incident_insight(client, incident: dict, reports: list[dict]) -> dict:
    """One on-demand Claude read of a single incident: a summary plus a short
    list of things worth checking before acting on it.

    Never raises for a per-call failure (timeout, malformed JSON, API error) -
    degrades to a plain result with insight_error set, so a coordinator
    clicking one incident never sees a crash (CLAUDE.md section 9).
    """
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.claude_configured:
        return _degraded_insight("Claude is not configured.")

    descriptions = []
    for i, report in enumerate(reports[:6], 1):
        desc = (report.get("description") or "").strip()
        if not desc:
            desc = report.get("location_text") or "(no description)"
        descriptions.append(f'{i}. "{desc[:160]}"')
    report_list = "\n".join(descriptions) or "(no source report text available)"

    first_reported = _format_timestamp(incident.get("first_reported_at"))
    latest_reported = _format_timestamp(incident.get("latest_reported_at"))
    time_span = f"{first_reported} to {latest_reported}" if first_reported else "unknown"

    job_warning = incident.get("recent_job_warning") or {}
    job_note = job_warning.get("message") or "None on file"

    user_prompt = f"""Incident: {incident.get('work_type', 'Unknown')} on {incident.get('canonical_road', 'Unknown road')}
Ward: {incident.get('ward') or 'unknown'}
Severity: {incident.get('severity') or 'unknown'}
Hazards on file: {', '.join(incident.get('hazards') or []) or 'none listed'}
Number of reports: {incident.get('report_count', 1)}
Time span: {time_span}
Recent related job history: {job_note}

Source reports:
{report_list}

Write the summary and recommended_actions as JSON:
{{
  "summary": "2-3 sentence actionable summary",
  "recommended_actions": ["...", "..."]
}}"""

    try:
        message = await asyncio.to_thread(
            client.messages.create,
            model=settings.claude_model,
            max_tokens=400,
            temperature=0,
            system=_INSIGHT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_response = "\n".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        parsed = _extract_json(raw_response)
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the request
        logger.exception("AI insight failed for incident %s", incident.get("incident_code"))
        return _degraded_insight(f"Claude call failed: {exc}")

    return {
        "summary": parsed.get("summary") or "Claude returned no summary.",
        "recommended_actions": parsed.get("recommended_actions") or [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "insight_error": None,
    }


async def summarize_incidents_batch(
    client, incidents: list[dict], all_reports_by_incident: dict
) -> list[dict]:
    """Summarize a batch of 3-5 incidents.

    If individual incident summarization is needed, falls back to per-incident calls.

    Args:
        client: Anthropic client
        incidents: List of incidents to summarize
        all_reports_by_incident: Dict mapping incident_id -> list of raw_reports

    Returns: List of {incident_id, title, summary, prompt, response}
    """
    results = []

    for incident in incidents:
        incident_id = incident["id"]
        reports = all_reports_by_incident.get(incident_id, [])

        result = await summarize_incident(client, incident, reports)
        if result:
            result["incident_id"] = incident_id
            results.append(result)
        else:
            results.append(
                {
                    "incident_id": incident_id,
                    "title": incident.get("title"),
                    "summary": incident.get("summary", ""),
                    "prompt": None,
                    "response": None,
                }
            )

    return results


def _batches(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def summarize_all_incidents(supabase, client) -> dict:
    """Summarize all incidents. Updates incidents table. Returns stats."""
    incidents = supabase.table("incidents").select("*").execute().data
    stats = {
        "total": len(incidents),
        "summarized": 0,
        "failed": 0,
        "ai_calls_made": 0,
    }

    # Build a map of incident_id -> linked reports
    incident_reports = (
        supabase.table("incident_reports")
        .select("incident_id, report_id")
        .execute()
        .data
    )
    incident_report_ids = {}
    for link in incident_reports:
        incident_id = link["incident_id"]
        report_id = link["report_id"]
        if incident_id not in incident_report_ids:
            incident_report_ids[incident_id] = []
        incident_report_ids[incident_id].append(report_id)

    # Fetch all reports once
    all_reports = supabase.table("raw_reports").select("id, description, location_text").execute().data
    reports_by_id = {r["id"]: r for r in all_reports}

    # Build reports per incident
    all_reports_by_incident = {}
    for incident_id, report_ids in incident_report_ids.items():
        all_reports_by_incident[incident_id] = [
            reports_by_id[rid] for rid in report_ids if rid in reports_by_id
        ]

    # Process in batches
    for batch in _batches(incidents, BATCH_SIZE):
        stats["ai_calls_made"] += 1
        results = await summarize_incidents_batch(client, batch, all_reports_by_incident)

        for result in results:
            incident_id = result["incident_id"]
            try:
                # Update metadata with the prompt/response for traceability
                existing_metadata = next(
                    (inc.get("ai_metadata") or {} for inc in incidents if inc["id"] == incident_id),
                    {},
                )
                if isinstance(existing_metadata, str):
                    existing_metadata = json.loads(existing_metadata)

                new_metadata = {
                    **existing_metadata,
                    "summary_prompt": result.get("prompt"),
                    "summary_response": result.get("response"),
                }

                supabase.table("incidents").update(
                    {
                        "title": result.get("title"),
                        "summary": result.get("summary"),
                        "ai_metadata": new_metadata,
                    }
                ).eq("id", incident_id).execute()

                stats["summarized"] += 1
            except Exception:
                logger.exception("Failed to update incident %s", incident_id)
                stats["failed"] += 1

    logger.info("Incident summarization stats: %s", stats)
    return stats
