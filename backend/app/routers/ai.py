from fastapi import APIRouter, HTTPException

from app.schemas.ai import ReportAnalysis, ReportAnalysisRequest
from app.services.claude_service import analyze_report

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze-report", response_model=ReportAnalysis)
def analyze_report_endpoint(payload: ReportAnalysisRequest) -> ReportAnalysis:
    try:
        return analyze_report(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Claude analysis failed safely: {exc}",
        ) from exc
