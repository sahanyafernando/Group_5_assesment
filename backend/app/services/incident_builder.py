"""Incident creation from clusters (Person A, Step 5).

Takes the clusters from Step 4 and creates incident records in the database,
linking all source reports via the incident_reports junction table.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_incident_code(supabase) -> str:
    """Generate the next available incident code (INC-001, INC-002, ...)."""
    result = (
        supabase.table("incidents")
        .select("incident_code")
        .order("incident_code", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return "INC-001"
    last_code = result.data[0].get("incident_code", "INC-000")
    try:
        num = int(last_code.split("-")[-1])
        return f"INC-{num + 1:03d}"
    except (ValueError, IndexError):
        return "INC-001"


def _severity_rank(severity: str) -> int:
    """Higher rank = worse. Used to pick the 'worst' severity from a cluster."""
    ranks = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}
    return ranks.get(severity, 0)


def build_incident_from_cluster(supabase, cluster: dict, reports: list[dict]) -> dict:
    """Merge cluster reports into one incident record.

    Args:
        supabase: Supabase client
        cluster: {cluster_id, report_ids, reason, confidence}
        reports: List of raw_reports dicts matching the cluster

    Returns: Dict ready for incidents table insert.
    """
    if not reports:
        logger.warning("Empty cluster %s; skipping", cluster.get("cluster_id"))
        return None

    incident_code = generate_incident_code(supabase)

    canonical_road = reports[0].get("normalized_location", "Unknown")
    work_types = [
        (r.get("ai_analysis") or {}).get("work_type", "Unsupported")
        for r in reports
    ]
    categories = [
        (r.get("ai_analysis") or {}).get("category", "Other")
        for r in reports
    ]
    severities = [
        (r.get("ai_analysis") or {}).get("severity", "unknown")
        for r in reports
    ]

    from collections import Counter

    work_type = Counter(work_types).most_common(1)[0][0]
    category = Counter(categories).most_common(1)[0][0]
    severity = max(severities, key=_severity_rank)

    all_hazards = set()
    all_impacts = set()
    for r in reports:
        analysis = r.get("ai_analysis") or {}
        all_hazards.update(analysis.get("hazards", []))
        all_impacts.update(analysis.get("impact", []))

    received_times = [r.get("received_at") for r in reports if r.get("received_at")]
    first_reported_at = min(received_times) if received_times else None
    latest_reported_at = max(received_times) if received_times else None

    confidences = [
        (r.get("ai_analysis") or {}).get("confidence", 0.5)
        for r in reports
    ]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

    title = f"{work_type} on {canonical_road}"
    needs_review = any(r.get("needs_review") for r in reports)

    return {
        "incident_code": incident_code,
        "title": title,
        "summary": None,
        "canonical_road": canonical_road,
        "ward": None,
        "category": category,
        "work_type": work_type,
        "severity": severity,
        "hazards": sorted(list(all_hazards)),
        "impact": sorted(list(all_impacts)),
        "report_count": len(reports),
        "first_reported_at": first_reported_at,
        "latest_reported_at": latest_reported_at,
        "priority_score": 0,
        "priority_level": None,
        "priority_reasons": [],
        "required_crew": None,
        "status": "New",
        "classification_confidence": avg_confidence,
        "location_confidence": reports[0].get("location_confidence"),
        "needs_review": needs_review,
        "recent_job_warning": None,
        "ai_metadata": {
            "cluster_id": cluster.get("cluster_id"),
            "merge_reason": cluster.get("reason"),
            "merge_confidence": cluster.get("confidence"),
        },
    }


async def create_all_incidents(supabase, clusters_and_reports: list[tuple]) -> dict:
    """Create all incidents from clusters.

    Args:
        supabase: Supabase client
        clusters_and_reports: List of (cluster_dict, report_list_dict) tuples
            from detect_all_duplicates

    Returns: {created: int, errors: int, incident_codes: []}
    """
    stats = {"created": 0, "errors": 0, "incident_codes": []}

    for cluster, reports in clusters_and_reports:
        try:
            incident_data = build_incident_from_cluster(supabase, cluster, reports)
            if not incident_data:
                stats["errors"] += 1
                continue

            result = supabase.table("incidents").insert(incident_data).execute()
            if not result.data:
                logger.error("Failed to insert incident for cluster %s", cluster.get("cluster_id"))
                stats["errors"] += 1
                continue

            incident_id = result.data[0]["id"]
            incident_code = result.data[0]["incident_code"]
            stats["incident_codes"].append(incident_code)

            # Link all reports to this incident
            for report in reports:
                link_data = {
                    "incident_id": incident_id,
                    "report_id": report["id"],
                    "match_confidence": cluster.get("confidence", 1.0),
                    "match_reason": cluster.get("reason", "grouped by AI"),
                }
                supabase.table("incident_reports").insert(link_data).execute()

                # Update report's incident_id
                supabase.table("raw_reports").update({"incident_id": incident_id}).eq(
                    "id", report["id"]
                ).execute()

            stats["created"] += 1

        except Exception:
            logger.exception(
                "Failed to create incident for cluster %s",
                cluster.get("cluster_id"),
            )
            stats["errors"] += 1

    logger.info("Incident creation stats: %s", stats)
    return stats
