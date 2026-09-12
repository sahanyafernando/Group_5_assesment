"""AI report classification (Person A, Step 3).

Batches raw_reports through Claude to extract work_type, severity, hazards,
impact and location hints from free text. A bad or missing AI response never
crashes the batch - it just marks that report needs_review.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from app.core.config import get_settings
from app.schemas.classification import ReportClassification
from app.services.crew_service import ALLOWED_WORK_TYPES

logger = logging.getLogger(__name__)

BATCH_SIZE = 7
CONFIDENCE_REVIEW_THRESHOLD = 0.6

VALID_CATEGORIES = [
    "Roads",
    "Pavements",
    "Drains",
    "Street lighting",
    "Street furniture",
    "Trees",
    "Waste",
    "Other",
]
VALID_SEVERITIES = ["critical", "high", "medium", "low"]

SYSTEM_PROMPT = """You are an incident triage assistant for Muthuwella Municipal Council Public Works division.

Your task is to extract and classify facts from resident reports about road, drain, lighting, and street furniture problems.

Rules:
- Choose work_type from ONLY these values: {work_types}
- Choose category from: {categories}
- Choose severity from: {severities}
- Do NOT invent facts not present in the report
- Do NOT invent locations or hazards
- If evidence is insufficient, lower confidence and set needs_review to true
- Return valid JSON only, no markdown, no explanation
""".format(
    work_types=", ".join(ALLOWED_WORK_TYPES),
    categories=", ".join(VALID_CATEGORIES),
    severities=", ".join(VALID_SEVERITIES),
)

_FALLBACK_KWARGS = dict(
    work_type="Unsupported",
    category="Other",
    severity="medium",
    confidence=0.0,
    needs_review=True,
)


def _fallback(report_id: str) -> ReportClassification:
    return ReportClassification(report_id=report_id, **_FALLBACK_KWARGS)


def _report_id(report: dict) -> str:
    return str(report.get("source_report_id") or report["id"])


def _has_description(report: dict) -> bool:
    return bool(report.get("description") and report["description"].strip())


def _extract_json(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\[.*\]|\{.*\})", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _report_block(report: dict) -> str:
    return f"""Report ID: {_report_id(report)}
Channel: {report.get('channel') or 'unknown'}
Location: {report.get('location_text') or 'missing'}
Description: {report.get('description') or ''}
Category (if provided): {report.get('category') or 'missing'}
Urgency (if provided): {report.get('urgency') or 'missing'}"""


_RESULT_SHAPE = """{
  "report_id": "...",
  "work_type": "one of the allowed values",
  "category": "one of the allowed values",
  "severity": "critical|high|medium|low",
  "hazards": ["list of specific hazards mentioned or clearly implied"],
  "impact": ["list of impacts mentioned: road users, pedestrians, vehicles, property"],
  "location_hints": {"road_hint": "...", "landmark": "...", "house_number": "..."},
  "persistence": "any time indicators like 'for three weeks', 'since the weekend', or null",
  "confidence": 0.0,
  "needs_review": false
}"""


def _numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d+", text or ""))


def _flag_ungrounded_location_hints(report: dict, analysis: ReportClassification) -> None:
    """Catch a hallucinated house/plate number in location_hints - one that
    appears in neither the description nor the location_text Claude was
    given (both are legitimate sources for a number, e.g. "outside 151
    Kirula Road" as location_text)."""
    hint_text = " ".join(str(v) for v in analysis.location_hints.values() if v)
    hint_numbers = _numbers_in(hint_text)
    source_numbers = _numbers_in(report.get("description")) | _numbers_in(report.get("location_text"))
    if hint_numbers and not hint_numbers <= source_numbers:
        logger.warning(
            "Ungrounded location_hints for %s: %s not found in description or location_text",
            _report_id(report),
            hint_numbers - source_numbers,
        )
        analysis.needs_review = True


def _validate(raw: dict, report: dict) -> ReportClassification:
    report_id = _report_id(report)
    payload = {**raw, "report_id": report_id} if isinstance(raw, dict) else {"report_id": report_id}

    try:
        analysis = ReportClassification.model_validate(payload)
    except Exception:
        logger.warning("Malformed classification for %s: %r", report_id, raw)
        return _fallback(report_id)

    if analysis.work_type not in ALLOWED_WORK_TYPES:
        analysis.work_type = "Unsupported"
        analysis.needs_review = True

    if analysis.category not in VALID_CATEGORIES:
        analysis.category = "Other"
        analysis.needs_review = True

    if analysis.severity not in VALID_SEVERITIES:
        analysis.severity = "medium"
        analysis.needs_review = True

    if analysis.confidence < CONFIDENCE_REVIEW_THRESHOLD:
        analysis.needs_review = True

    _flag_ungrounded_location_hints(report, analysis)

    return analysis


async def classify_report(client, report: dict) -> ReportClassification:
    """Classify a single report. Also used as the fallback for failed batch items."""
    report_id = _report_id(report)

    if not _has_description(report):
        return _fallback(report_id)

    settings = get_settings()
    user_prompt = f"""Analyze this resident report.

{_report_block(report)}

Extract the following as JSON:
{_RESULT_SHAPE}"""

    try:
        message = await asyncio.to_thread(
            client.messages.create,
            model=settings.claude_model,
            max_tokens=500,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = "\n".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        parsed = _extract_json(raw_text)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else {}
    except Exception:
        logger.exception("Claude classification failed for %s", report_id)
        return _fallback(report_id)

    return _validate(parsed, report)


async def classify_reports_batch(client, reports: list[dict]) -> list[ReportClassification]:
    """Classify a batch of 5-8 reports in one API call.

    Matches Claude's response back to reports by POSITION, not by report_id -
    source_report_id is not guaranteed unique (CLAUDE.md section 10), so
    matching by id could silently misassign a result to the wrong report.
    Falls back to per-report calls if the batch call fails or the response
    shape doesn't line up.
    """
    settings = get_settings()

    classifiable = [r for r in reports if _has_description(r)]
    results_by_db_id: dict[str, ReportClassification] = {
        r["id"]: _fallback(_report_id(r)) for r in reports if not _has_description(r)
    }

    if classifiable:
        report_blocks = "\n\n".join(
            f"Report {i + 1}:\n{_report_block(r)}" for i, r in enumerate(classifiable)
        )
        user_prompt = f"""Analyze each of the following {len(classifiable)} reports and return a JSON array with one result per report.

{report_blocks}

Return a JSON array with EXACTLY {len(classifiable)} objects, one per report, IN THE SAME ORDER as listed above. Each object shaped as:
{_RESULT_SHAPE}"""

        try:
            message = await asyncio.to_thread(
                client.messages.create,
                model=settings.claude_model,
                max_tokens=4000,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = "\n".join(
                block.text for block in message.content if getattr(block, "type", None) == "text"
            )
            parsed = _extract_json(raw_text)
            if not isinstance(parsed, list) or len(parsed) != len(classifiable):
                raise ValueError(
                    f"Expected a JSON array of {len(classifiable)} items, got: {parsed!r}"
                )

            for report, raw in zip(classifiable, parsed):
                results_by_db_id[report["id"]] = _validate(raw, report)

        except Exception:
            logger.exception(
                "Batch classification failed for %s reports; falling back to per-report calls",
                len(classifiable),
            )
            fallback_results = await asyncio.gather(
                *(classify_report(client, r) for r in classifiable)
            )
            for report, analysis in zip(classifiable, fallback_results):
                results_by_db_id[report["id"]] = analysis

    return [results_by_db_id[r["id"]] for r in reports]


def _batches(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def classify_all_reports(supabase, client) -> dict:
    """Classify all reports. Updates raw_reports.ai_analysis. Returns stats."""
    reports = (
        supabase.table("raw_reports")
        .select(
            "id, source_report_id, channel, location_text, description, "
            "category, urgency, needs_review"
        )
        .execute()
        .data
    )

    stats = {
        "total": len(reports),
        "classified": 0,
        "needs_review": 0,
        "empty_description": 0,
        "ai_calls_made": 0,
    }

    for batch in _batches(reports, BATCH_SIZE):
        classifiable_count = sum(1 for r in batch if _has_description(r))
        stats["empty_description"] += len(batch) - classifiable_count
        if classifiable_count:
            stats["ai_calls_made"] += 1

        results = await classify_reports_batch(client, batch)

        for report, analysis in zip(batch, results):
            needs_review = analysis.needs_review or bool(report.get("needs_review"))
            supabase.table("raw_reports").update(
                {
                    "ai_analysis": analysis.model_dump(),
                    "ai_confidence": analysis.confidence,
                    "needs_review": needs_review,
                }
            ).eq("id", report["id"]).execute()

            stats["classified"] += 1
            if needs_review:
                stats["needs_review"] += 1

    logger.info("Classification stats: %s", stats)
    return stats
