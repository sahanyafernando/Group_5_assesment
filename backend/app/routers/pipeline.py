"""Pipeline trigger and re-enrichment endpoints.

The actual ingestion -> classification -> clustering -> incident-construction
pipeline (CLAUDE.md steps 3-6) belongs to Person A. `run_pipeline` is the
placeholder Person C can call now; Person A wires the real implementation in
later. `enrich_all` re-runs Step 8's deterministic enrichment over every
existing incident -- handy right after a priority/crew rule change.
"""

from fastapi import APIRouter, HTTPException

from app.services.enrichment_pipeline import enrich_all_incidents

router = APIRouter(tags=["pipeline"])


@router.post("/pipeline/run")
def run_pipeline() -> dict:
    return {
        "status": "not_implemented",
        "message": "Pipeline trigger -- Person A will implement report ingestion, "
        "classification, clustering and incident construction here.",
    }


@router.post("/pipeline/enrich-all")
def enrich_all() -> dict:
    """Re-run crew/priority/asset/history enrichment over every incident.

    One incident failing never stops the batch; failures are reported, not
    raised (CLAUDE.md section 9).
    """
    try:
        return enrich_all_incidents()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Enrichment batch failed: {exc}") from exc
