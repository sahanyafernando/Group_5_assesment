"""Full AI pipeline orchestrator (Person A, Step 7).

Chains all 6 steps (CSV load → location normalize → AI classify → duplicate detect →
incident create → incident summarize) into one triggerable flow. Optionally calls
Person B's enrichment at the end.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


async def run_full_pipeline(supabase, anthropic_client, data_dir: str) -> dict:
    """Run the complete Person A pipeline.

    Args:
        supabase: Supabase client
        anthropic_client: Anthropic API client
        data_dir: Path to directory containing reports.csv, assets.csv, jobs-history.csv

    Returns: Dict with pipeline stats and timings.
    """
    start_time = time.time()
    stats = {
        "reports_loaded": 0,
        "locations_normalized": 0,
        "locations_unresolved": 0,
        "reports_classified": 0,
        "reports_needs_review": 0,
        "clusters_found": 0,
        "incidents_created": 0,
        "incidents_summarized": 0,
        "total_time_seconds": 0,
        "ai_calls_made": 0,
        "errors": [],
    }

    try:
        # Step 1: Load CSVs
        logger.info("Step 1/7: Loading CSVs...")
        from app.services.csv_loader import load_all

        load_stats = load_all(supabase, data_dir)
        stats["reports_loaded"] = load_stats["raw_reports"]["loaded"]
        logger.info("  ✓ Loaded %d reports", stats["reports_loaded"])

        # Step 2: Normalize locations
        logger.info("Step 2/7: Normalizing locations...")
        from app.services.location_matcher import normalize_all_reports

        loc_stats = await normalize_all_reports(supabase, anthropic_client)
        stats["locations_normalized"] = loc_stats.get("resolved_exact", 0) + loc_stats.get(
            "resolved_alias", 0
        ) + loc_stats.get("resolved_abbreviation", 0) + loc_stats.get("resolved_fuzzy", 0) + loc_stats.get("resolved_ai", 0)
        stats["locations_unresolved"] = loc_stats.get("unresolved", 0)
        stats["ai_calls_made"] += loc_stats.get("ai_calls_made", 0)
        logger.info("  ✓ Normalized %d locations (%d unresolved)", stats["locations_normalized"], stats["locations_unresolved"])

        # Step 3: Classify reports with AI
        logger.info("Step 3/7: Classifying reports...")
        from app.services.ai_classifier import classify_all_reports

        class_stats = await classify_all_reports(supabase, anthropic_client)
        stats["reports_classified"] = class_stats.get("classified", 0)
        stats["reports_needs_review"] = class_stats.get("needs_review", 0)
        stats["ai_calls_made"] += class_stats.get("ai_calls_made", 0)
        logger.info("  ✓ Classified %d reports (%d flagged for review)", stats["reports_classified"], stats["reports_needs_review"])

        # Step 4: Detect duplicates and cluster
        logger.info("Step 4/7: Detecting duplicates and clustering...")
        from app.services.duplicate_detector import detect_all_duplicates

        dup_result = await detect_all_duplicates(supabase, anthropic_client)
        dup_stats = dup_result.get("stats", {})
        clusters = dup_result.get("clusters", [])
        stats["clusters_found"] = len(clusters)
        stats["ai_calls_made"] += dup_stats.get("ai_calls_made", 0)
        logger.info("  ✓ Created %d clusters from %d groups", stats["clusters_found"], dup_stats.get("total_groups", 0))

        # Step 5: Create incidents
        logger.info("Step 5/7: Creating incidents...")
        from app.services.incident_builder import create_all_incidents

        # Build (cluster, reports) pairs
        all_reports = (
            supabase.table("raw_reports")
            .select(
                "id, source_report_id, normalized_location, received_at, "
                "ai_analysis, description, location_text, location_confidence, needs_review"
            )
            .execute()
            .data
        )
        clusters_and_reports = []
        for cluster in clusters:
            cluster_report_ids = set(cluster["report_ids"])
            matched_reports = [
                r for r in all_reports
                if (r.get("source_report_id") or r["id"]) in cluster_report_ids
            ]
            if matched_reports:
                clusters_and_reports.append((cluster, matched_reports))

        incident_stats = await create_all_incidents(supabase, clusters_and_reports)
        stats["incidents_created"] = incident_stats.get("created", 0)
        logger.info("  ✓ Created %d incidents", stats["incidents_created"])

        # Step 6: Summarize incidents
        logger.info("Step 6/7: Summarizing incidents...")
        from app.services.ai_summarizer import summarize_all_incidents

        summary_stats = await summarize_all_incidents(supabase, anthropic_client)
        stats["incidents_summarized"] = summary_stats.get("summarized", 0)
        stats["ai_calls_made"] += summary_stats.get("ai_calls_made", 0)
        logger.info("  ✓ Summarized %d incidents", stats["incidents_summarized"])

        # Step 7: Call Person B's enrichment (if available)
        logger.info("Step 7/7: Enriching incidents (Person B)...")
        try:
            from app.services.enrichment_pipeline import enrich_all_incidents

            await enrich_all_incidents(supabase)
            logger.info("  ✓ Enrichment complete")
        except ImportError:
            logger.info("  ⊘ enrichment_pipeline not yet available (Person B not ready)")
        except Exception:
            logger.exception("  ! Enrichment failed (non-blocking)")

    except Exception as e:
        logger.exception("Pipeline failed at a step")
        stats["errors"].append(str(e))

    stats["total_time_seconds"] = time.time() - start_time
    logger.info("Pipeline complete in %.1f seconds", stats["total_time_seconds"])
    return stats


async def run_classification_only(supabase, anthropic_client) -> dict:
    """Re-run just the AI classification step (for testing/re-analysis)."""
    from app.services.ai_classifier import classify_all_reports

    logger.info("Running classification-only pass...")
    stats = await classify_all_reports(supabase, anthropic_client)
    logger.info("Classification-only complete: %s", stats)
    return stats


async def run_clustering_only(supabase, anthropic_client) -> dict:
    """Re-run just the clustering step (for testing/re-analysis)."""
    from app.services.duplicate_detector import detect_all_duplicates

    logger.info("Running clustering-only pass...")
    result = await detect_all_duplicates(supabase, anthropic_client)
    stats = result.get("stats", {})
    logger.info("Clustering-only complete: %s", stats)
    return stats
