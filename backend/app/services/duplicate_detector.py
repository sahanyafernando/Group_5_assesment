"""Duplicate detection and clustering (Person A, Step 4).

Phase 1: Deterministic pre-grouping by (normalized_location, work_type).
Phase 2: AI semantic verification only within multi-report groups.

Returns clusters ready for Step 5 (incident creation).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

CONFIDENCE_MERGE_THRESHOLD = 0.6


def _extract_json(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _group_key(report: dict) -> str:
    """Generate a deterministic pre-group key from (normalized_location, work_type)."""
    location = report.get("normalized_location") or "unknown"
    analysis = report.get("ai_analysis") or {}
    work_type = analysis.get("work_type", "unknown")
    return f"{location}|{work_type}".lower()


def pre_group_reports(reports: list[dict]) -> dict[str, list[dict]]:
    """Group by (normalized_location, work_type). Returns {group_key: [reports]}."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for report in reports:
        key = _group_key(report)
        groups[key].append(report)
    return dict(groups)


def _report_summary(report: dict) -> str:
    """One-line summary of a report for Claude."""
    report_id = report.get("source_report_id") or report.get("id")
    desc = (report.get("description") or "")[:100]
    return f'Report {report_id}: "{desc}"'


_SYSTEM_PROMPT = """You are a municipal incident triage assistant deciding whether separate resident reports describe the SAME specific problem or DIFFERENT problems.

Rules:
- Reports at the same location with the same work type may still describe different specific problems.
- Same location, same general issue, but clearly distinct causes (e.g. pothole at corner A vs. corner B on the same road) should be separate clusters.
- Same location, same issue, same specific spot (e.g. three people reporting the same blocked drain) should be grouped.
- Return valid JSON only, no markdown, no explanation.
"""

_RESULT_SHAPE = """{
  "clusters": [
    {
      "cluster_id": "C1",
      "report_ids": ["MR-123", "MR-124"],
      "reason": "Both describe blocked drain near house #45, same specific location"
    }
  ],
  "confidence": 0.85
}"""


async def detect_duplicates_in_group(client, group_key: str, reports: list[dict]) -> list[dict]:
    """AI semantic duplicate detection within a pre-grouped set of reports.

    Returns a list of clusters: [{"cluster_id": "C1", "report_ids": [...], "reason": "...", "confidence": float}]
    If the group has only 1 report, returns that as a single cluster with no AI call.
    """
    if len(reports) == 1:
        return [
            {
                "cluster_id": "C1",
                "report_ids": [reports[0].get("source_report_id") or reports[0]["id"]],
                "reason": "Single report in group",
                "confidence": 1.0,
            }
        ]

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.claude_configured:
        logger.warning("Claude not configured; keeping all %d reports separate", len(reports))
        return [
            {
                "cluster_id": f"C{i+1}",
                "report_ids": [r.get("source_report_id") or r["id"]],
                "reason": "Claude not configured; treated as unique",
                "confidence": 1.0,
            }
            for i, r in enumerate(reports)
        ]

    report_summaries = "\n".join(
        f"Report {i+1}:\n  ID: {r.get('source_report_id') or r['id']}\n  {_report_summary(r)}"
        for i, r in enumerate(reports)
    )
    location = reports[0].get("normalized_location", "unknown")
    work_type = (reports[0].get("ai_analysis") or {}).get("work_type", "unknown")

    user_prompt = f"""These {len(reports)} reports are all about {work_type} on {location}.
Decide which reports describe the SAME specific problem (at the same specific spot/location within {location}).

{report_summaries}

Group them into clusters where each cluster contains reports about the SAME specific problem.
Return JSON:
{_RESULT_SHAPE}"""

    try:
        message = await asyncio.to_thread(
            client.messages.create,
            model=settings.claude_model,
            max_tokens=1000,
            temperature=0,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = "\n".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        parsed = _extract_json(raw_text)
    except Exception:
        logger.exception("Duplicate detection failed for group %s; treating all as separate", group_key)
        return [
            {
                "cluster_id": f"C{i+1}",
                "report_ids": [r.get("source_report_id") or r["id"]],
                "reason": "Claude failed; treated as unique",
                "confidence": 1.0,
            }
            for i, r in enumerate(reports)
        ]

    clusters = parsed.get("clusters", [])
    group_confidence = parsed.get("confidence", 0.5)

    # Validate that all report_ids are legitimate
    all_report_ids = {r.get("source_report_id") or r["id"] for r in reports}
    validated = []
    for cluster in clusters:
        cluster_ids = cluster.get("report_ids", [])
        if set(cluster_ids) <= all_report_ids:
            validated.append(
                {
                    "cluster_id": cluster.get("cluster_id", "C?"),
                    "report_ids": cluster_ids,
                    "reason": cluster.get("reason", "grouped by AI"),
                    "confidence": group_confidence,
                }
            )

    if not validated:
        logger.warning("Cluster validation failed for %s; treating all separate", group_key)
        return [
            {
                "cluster_id": f"C{i+1}",
                "report_ids": [r.get("source_report_id") or r["id"]],
                "reason": "Cluster validation failed; treated as unique",
                "confidence": 1.0,
            }
            for i, r in enumerate(reports)
        ]

    return validated


async def detect_all_duplicates(supabase, client) -> dict:
    """Run full duplicate detection. Returns stats dict."""
    reports = (
        supabase.table("raw_reports")
        .select(
            "id, source_report_id, normalized_location, "
            "description, ai_analysis, location_text"
        )
        .execute()
        .data
    )

    groups = pre_group_reports(reports)
    stats = {
        "total_reports": len(reports),
        "total_groups": len(groups),
        "single_report_groups": 0,
        "multi_report_groups": 0,
        "total_clusters": 0,
        "ai_calls_made": 0,
    }

    all_clusters: list[dict] = []

    for group_key, group_reports in sorted(groups.items()):
        if len(group_reports) == 1:
            stats["single_report_groups"] += 1
        else:
            stats["multi_report_groups"] += 1
            stats["ai_calls_made"] += 1

        clusters = await detect_duplicates_in_group(client, group_key, group_reports)
        stats["total_clusters"] += len(clusters)

        for cluster in clusters:
            all_clusters.append(
                {
                    "group_key": group_key,
                    "cluster_id": cluster.get("cluster_id"),
                    "report_ids": cluster.get("report_ids", []),
                    "reason": cluster.get("reason"),
                    "confidence": cluster.get("confidence", 0.5),
                }
            )

    logger.info("Duplicate detection stats: %s", stats)
    return {"stats": stats, "clusters": all_clusters}
