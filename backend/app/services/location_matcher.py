"""Location normalization for the AI pipeline (Person A, Step 2).

Resolves messy raw_reports.location_text to a canonical road name from the
assets table. Rules run first (steps 1-4); Claude is only a fallback for the
locations rules cannot resolve.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import re

logger = logging.getLogger(__name__)

ABBREVIATIONS = {
    "rd": "road", "rd.": "road",
    "st": "street", "st.": "street",
    "ave": "avenue", "ave.": "avenue",
    "ln": "lane", "ln.": "lane",
    "pl": "place", "pl.": "place",
    "cr": "crescent", "cr.": "crescent",
    "mw": "mawatha", "mw.": "mawatha",
    "dr": "drive", "dr.": "drive",
}

FUZZY_THRESHOLD = 0.75

CONFIDENCE_EXACT = 1.0
CONFIDENCE_ALIAS = 0.9
CONFIDENCE_ABBREVIATION = 0.8
CONFIDENCE_FUZZY = 0.7
CONFIDENCE_UNRESOLVED = 0.0

_AI_SYSTEM_PROMPT = """You match a resident-reported location description to a known council road.

Rules:
- Choose exactly one value from the provided road name list, or null if none plausibly matches.
- Do not invent a road name that is not in the list.
- A landmark-based description (e.g. "near the temple on the main road") should only match a road if it is clearly identifiable from the list and context.
- Return valid JSON only, no markdown, no explanation.
"""


def load_known_roads(supabase) -> dict[str, tuple[str, str]]:
    """Load road names and aliases from the assets table.

    Returns a dict mapping lowercased text -> (canonical_road_name, source),
    where source is "name" or "alias".
    """
    rows = supabase.table("assets").select("road_name, also_known_as").execute().data

    known_roads: dict[str, tuple[str, str]] = {}
    for row in rows:
        road_name = (row.get("road_name") or "").strip()
        if road_name:
            known_roads[road_name.lower()] = (road_name, "name")

        alias = (row.get("also_known_as") or "").strip()
        if alias and road_name:
            known_roads[alias.lower()] = (road_name, "alias")

    return known_roads


def _expand_abbreviations(text: str) -> str:
    tokens = text.split()
    expanded = [ABBREVIATIONS.get(token, token) for token in tokens]
    return " ".join(expanded)


def _canonical_names(known_roads: dict[str, tuple[str, str]]) -> list[str]:
    return sorted({canonical for canonical, _source in known_roads.values()})


_ALIAS_MARKER = " (also known as: "


def _build_road_directory(known_roads: dict[str, tuple[str, str]]) -> list[str]:
    """Canonical road names annotated with their known aliases.

    Without the aliases, the AI fallback has no way to know e.g. that
    "Baseline extension" refers to Elvitigala Mawatha and not the
    similarly-spelled Baseline Road, so it must see them to disambiguate.
    """
    aliases_by_canonical: dict[str, list[str]] = {}
    for key, (canonical, source) in known_roads.items():
        if source == "alias":
            aliases_by_canonical.setdefault(canonical, []).append(key)

    directory = []
    for canonical in _canonical_names(known_roads):
        aliases = aliases_by_canonical.get(canonical)
        if aliases:
            directory.append(f"{canonical}{_ALIAS_MARKER}{', '.join(sorted(aliases))})")
        else:
            directory.append(canonical)
    return directory


def _strip_alias_annotation(entry: str) -> str:
    return entry.split(_ALIAS_MARKER)[0].strip()


def normalize_location(location_text: str | None, known_roads: dict) -> tuple[str | None, float]:
    """Match location_text to a canonical road using rules only (steps 1-4).

    Returns (canonical_road_name, confidence).
    Confidence: 1.0=exact, 0.9=alias, 0.8=abbreviation, 0.7=fuzzy, 0.0=unresolved.
    """
    if not location_text or not location_text.strip():
        return None, CONFIDENCE_UNRESOLVED

    text = location_text.lower()

    # Longest keys first so a full road name wins over a shorter partial hit.
    entries = sorted(known_roads.items(), key=lambda item: -len(item[0]))

    # 1. Exact road-name match
    for key, (canonical, source) in entries:
        if source == "name" and key in text:
            return canonical, CONFIDENCE_EXACT

    # 2. Alias match
    for key, (canonical, source) in entries:
        if source == "alias" and key in text:
            return canonical, CONFIDENCE_ALIAS

    # 3. Abbreviation expansion, then re-match against names and aliases
    expanded = _expand_abbreviations(text)
    if expanded != text:
        for key, (canonical, _source) in entries:
            if key in expanded:
                return canonical, CONFIDENCE_ABBREVIATION

    # 4. Fuzzy match against every known name/alias
    best_canonical = None
    best_score = 0.0
    for key, (canonical, _source) in entries:
        score = difflib.SequenceMatcher(None, key, text).ratio()
        if score > best_score:
            best_score = score
            best_canonical = canonical

    if best_canonical and best_score > FUZZY_THRESHOLD:
        return best_canonical, CONFIDENCE_FUZZY

    return None, CONFIDENCE_UNRESOLVED


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


async def normalize_location_ai(client, location_text: str, road_names: list[str]) -> tuple[str | None, float]:
    """AI fallback for a location the rules couldn't match.

    `road_names` entries may be annotated with known aliases, e.g.
    "Elvitigala Mawatha (also known as: baseline extension)" - this lets the
    AI disambiguate typo'd aliases from similarly-spelled but unrelated roads.

    Returns (road_name, confidence). Never raises - falls back to (None, 0.0).
    """
    if client is None:
        return None, 0.0

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.claude_configured:
        logger.warning("Claude not configured; cannot AI-resolve location %r", location_text)
        return None, 0.0

    valid_canonical = {_strip_alias_annotation(entry) for entry in road_names}
    road_list = "\n".join(f"- {name}" for name in road_names)
    user_prompt = f"""Location text: "{location_text}"

Known roads (each may list its known aliases in parentheses):
{road_list}

Return JSON:
{{"road_name": "the canonical road name only, exactly as listed before any '(also known as: ...)' part, or null", "confidence": 0.0}}
"""

    try:
        message = await asyncio.to_thread(
            client.messages.create,
            model=settings.claude_model,
            max_tokens=200,
            temperature=0,
            system=_AI_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = "\n".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        parsed = _extract_json(raw_text)
    except Exception:
        logger.exception("AI location fallback failed for %r", location_text)
        return None, 0.0

    road_name = parsed.get("road_name")
    if road_name not in valid_canonical:
        return None, 0.0

    try:
        confidence = float(parsed.get("confidence", 0.6))
    except (TypeError, ValueError):
        confidence = 0.6

    return road_name, max(0.0, min(confidence, 1.0))


def _method_for_confidence(confidence: float) -> str:
    if confidence >= CONFIDENCE_EXACT:
        return "exact"
    if confidence >= CONFIDENCE_ALIAS:
        return "alias"
    if confidence >= CONFIDENCE_ABBREVIATION:
        return "abbreviation"
    if confidence >= CONFIDENCE_FUZZY:
        return "fuzzy"
    return "unresolved"


async def normalize_all_reports(supabase, client) -> dict:
    """Normalize locations for all reports. Updates raw_reports. Returns stats."""
    known_roads = load_known_roads(supabase)
    road_directory = _build_road_directory(known_roads)

    reports = (
        supabase.table("raw_reports")
        .select("id, location_text, needs_review")
        .execute()
        .data
    )

    stats = {
        "total": len(reports),
        "resolved_exact": 0,
        "resolved_alias": 0,
        "resolved_abbreviation": 0,
        "resolved_fuzzy": 0,
        "resolved_ai": 0,
        "unresolved": 0,
        "ai_calls_made": 0,
    }

    ai_cache: dict[str, tuple[str | None, float]] = {}

    for report in reports:
        location_text = report.get("location_text")
        canonical, confidence = normalize_location(location_text, known_roads)
        method = _method_for_confidence(confidence)

        if canonical is None and location_text and location_text.strip():
            cache_key = location_text.strip().lower()
            if cache_key not in ai_cache:
                ai_cache[cache_key] = await normalize_location_ai(client, location_text, road_directory)
                stats["ai_calls_made"] += 1
            canonical, confidence = ai_cache[cache_key]
            method = "ai" if canonical else "unresolved"

        if canonical:
            stats[f"resolved_{method}"] += 1
        else:
            stats["unresolved"] += 1

        supabase.table("raw_reports").update(
            {
                "normalized_location": canonical,
                "location_confidence": confidence,
                "needs_review": (canonical is None) or bool(report.get("needs_review")),
            }
        ).eq("id", report["id"]).execute()

    logger.info("Location normalization stats: %s", stats)
    return stats
