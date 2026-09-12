import json
import re

from anthropic import Anthropic

from app.core.config import get_settings
from app.schemas.ai import ReportAnalysis, ReportAnalysisRequest
from app.services.crew_service import ALLOWED_WORK_TYPES


SYSTEM_PROMPT = """You are an incident triage assistant for Muthuwella Municipal Council.

Extract and classify facts that are supported by the resident report.

You MUST NOT:
- calculate the final priority score
- assign a crew
- invent a missing location
- invent hazards, causes, or facts
- claim certainty when the report is ambiguous

Choose work_type from this exact allowed list:
{work_types}

Severity must be one of:
critical, high, medium, low, unknown

If evidence is insufficient:
- use a conservative interpretation
- lower confidence
- set needs_review=true

Return exactly one JSON object using this shape:
{{
  "work_type": "...",
  "category": "... or null",
  "incident_title": "...",
  "incident_summary": "...",
  "location": {{
    "road_hint": "... or null",
    "landmark": "... or null"
  }},
  "severity": "critical|high|medium|low|unknown",
  "hazards": [],
  "impact": [],
  "confidence": 0.0,
  "needs_review": true
}}

Do not wrap JSON in markdown.
""".format(work_types="\n".join(f"- {item}" for item in ALLOWED_WORK_TYPES))


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def analyze_report(payload: ReportAnalysisRequest) -> ReportAnalysis:
    settings = get_settings()

    if not settings.claude_configured:
        raise RuntimeError(
            "Claude API is not configured. Set ANTHROPIC_API_KEY in backend/.env."
        )

    client = Anthropic(api_key=settings.anthropic_api_key)

    user_prompt = f"""Analyze this resident report.

report_id: {payload.report_id or 'unknown'}
description: {payload.description}
location_text: {payload.location_text or 'missing'}
existing_category: {payload.category or 'missing'}
resident_urgency: {payload.urgency or 'missing'}
"""

    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=900,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text_parts = [
        block.text
        for block in message.content
        if getattr(block, "type", None) == "text"
    ]
    raw_text = "\n".join(text_parts)

    parsed = _extract_json(raw_text)
    analysis = ReportAnalysis.model_validate(parsed)

    if analysis.work_type not in ALLOWED_WORK_TYPES:
        analysis.work_type = "Unsupported"
        analysis.needs_review = True

    if analysis.confidence < 0.60:
        analysis.needs_review = True

    return analysis
