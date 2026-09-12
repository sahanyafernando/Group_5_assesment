"""Deterministic, explainable priority scoring.

CLAUDE.md section 8: the final score is calculated here and nowhere else. No
AI, no network, no database. The same input always produces the same score, and
every point added carries an explanation string.

Claude may supply evidence that feeds this function -- an extracted severity, a
list of hazards -- but never the number itself.

Factor ceilings (CLAUDE.md section 8, REQUIREMENTS.md section 5):

    Safety / severity      0-35
    Road / public impact   0-20
    Critical facility      0-15
    Age / persistence      0-15
    Multiple reports       0-10
    Resident urgency       0-5
                           ----
                           100
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

# --- Factor ceilings ---------------------------------------------------------

MAX_SAFETY = 35
MAX_ROAD = 20
MAX_FACILITY = 15
MAX_AGE = 15
MAX_REPORTS = 10
MAX_URGENCY = 5

# --- Point tables (REQUIREMENTS.md section 5) --------------------------------

SEVERITY_POINTS: dict[str, int] = {
    "critical": 35,
    "high": 28,
    "medium": 18,
    "low": 8,
    "unknown": 10,
}

ROAD_POINTS: dict[str, int] = {
    "main road": 20,
    "bus route": 15,
    "residential": 8,
    "lane": 5,
}

URGENCY_POINTS: dict[str, int] = {
    "high": 5,
    "medium": 3,
    "low": 1,
}

# --- Safety language boosts --------------------------------------------------

# A deterministic regex scan over the resident's own words. Not AI: the same
# description always produces the same boost.
KEYWORD_BOOST_EACH = 3
MAX_KEYWORD_BOOST = 9

HAZARD_BOOST_EACH = 2
MAX_HAZARD_BOOST = 6

SAFETY_KEYWORDS: dict[str, str] = {
    "accident": r"\baccidents?\b",
    "near-miss": r"\bnear[-\s]?miss(?:es)?\b",
    "dangerous": r"\bdanger(?:ous)?\b",
    "flooding": r"\bflood(?:ing|ed|s)?\b",
    "collapsed": r"\bcollapsed?\b",
    "open manhole": r"\bopen\s+manhole\b",
    "fell": r"\b(?:fell|fallen)\b",
    "tripped": r"\btrip(?:ped|ping)\b",
    "vehicle damage": r"\b(?:vehicle|car|tyre|tire)\s+damage\b",
    "child": r"\bchild(?:ren)?\b",
    "elderly": r"\b(?:elderly|pensioner)\b",
}

_COMPILED_KEYWORDS = {
    label: re.compile(pattern, re.IGNORECASE)
    for label, pattern in SAFETY_KEYWORDS.items()
}

# --- Level thresholds --------------------------------------------------------

CRITICAL_THRESHOLD = 85
HIGH_THRESHOLD = 65
MEDIUM_THRESHOLD = 40


def _as_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class PriorityInput:
    """Everything the score depends on. Frozen so a score cannot drift."""

    severity: str | None = None
    road_class: str | None = None
    facility_distance_m: float | None = None
    age_days: float = 0
    report_count: int = 1
    urgency: str | None = None

    # Evidence feeding the safety boosts.
    description: str = ""
    hazards: tuple[str, ...] = ()

    # Used only to make the facility explanation readable.
    nearest_facility: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "PriorityInput":
        """Build from an incident-shaped dict, tolerating missing keys."""
        hazards = data.get("hazards") or ()
        if isinstance(hazards, str):
            hazards = (hazards,)

        description = data.get("description") or ""
        if not description:
            description = " ".join(
                str(data.get(key) or "") for key in ("title", "summary")
            ).strip()

        return cls(
            severity=data.get("severity"),
            road_class=data.get("road_class"),
            facility_distance_m=_as_float(data.get("facility_distance_m")),
            age_days=_as_float(data.get("age_days")) or 0,
            report_count=int(data.get("report_count") or 1),
            urgency=data.get("urgency"),
            description=description,
            hazards=tuple(str(item) for item in hazards),
            nearest_facility=data.get("nearest_facility"),
        )


def matched_safety_keywords(text: str) -> list[str]:
    """Safety keywords present in the text, sorted for a stable explanation."""
    if not text:
        return []
    return sorted(
        label for label, pattern in _COMPILED_KEYWORDS.items() if pattern.search(text)
    )


def _safety_reasons(data: PriorityInput) -> list[dict]:
    """Severity points, plus language and hazard boosts capped at MAX_SAFETY."""
    severity_key = (data.severity or "unknown").strip().lower()
    base = SEVERITY_POINTS.get(severity_key, SEVERITY_POINTS["unknown"])

    reasons = [
        {
            "factor": "Safety / severity",
            "points": base,
            "reason": f"severity assessed as {severity_key}",
        }
    ]

    headroom = max(MAX_SAFETY - base, 0)

    keywords = matched_safety_keywords(data.description)
    keyword_points = min(len(keywords) * KEYWORD_BOOST_EACH, MAX_KEYWORD_BOOST, headroom)
    if keyword_points > 0:
        reasons.append(
            {
                "factor": "Safety / severity",
                "points": keyword_points,
                "reason": f"safety language in report: {', '.join(keywords)}",
            }
        )
        headroom -= keyword_points

    hazard_points = min(len(data.hazards) * HAZARD_BOOST_EACH, MAX_HAZARD_BOOST, headroom)
    if hazard_points > 0:
        listed = ", ".join(data.hazards[:3])
        reasons.append(
            {
                "factor": "Safety / severity",
                "points": hazard_points,
                "reason": f"{len(data.hazards)} hazard(s) identified: {listed}",
            }
        )

    return reasons


def _road_reason(data: PriorityInput) -> dict:
    road_key = (data.road_class or "").strip().lower()
    return {
        "factor": "Road / public impact",
        "points": ROAD_POINTS.get(road_key, 0),
        "reason": f"road class is {road_key or 'unknown'}",
    }


def _facility_points(distance: float | None) -> int:
    if distance is None:
        return 0
    if distance <= 100:
        return 15
    if distance <= 200:
        return 10
    if distance <= 300:
        return 5
    return 0


def _facility_reason(data: PriorityInput) -> dict:
    distance = data.facility_distance_m
    if distance is None:
        reason = "no facility distance available"
    elif data.nearest_facility:
        reason = f"near {data.nearest_facility} ({distance:.0f}m)"
    else:
        reason = f"critical facility {distance:.0f}m away"
    return {
        "factor": "Critical facility",
        "points": _facility_points(distance),
        "reason": reason,
    }


def _age_points(days: float) -> int:
    if days > 7:
        return 15
    if days >= 3:
        return 10
    if days >= 1:
        return 5
    return 0


def _age_reason(data: PriorityInput) -> dict:
    days = data.age_days
    if days > 7:
        text = f"unresolved for over 7 days ({days:.0f} days)"
    elif days >= 1:
        text = f"unresolved for {days:.0f} day(s)"
    else:
        text = "reported today"
    return {"factor": "Age / persistence", "points": _age_points(days), "reason": text}


def _report_points(count: int) -> int:
    if count >= 5:
        return 10
    if count >= 3:
        return 6
    if count == 2:
        return 3
    return 0


def _report_reason(data: PriorityInput) -> dict:
    count = max(int(data.report_count or 1), 1)
    return {
        "factor": "Multiple reports",
        "points": _report_points(count),
        "reason": f"{count} independent report(s)",
    }


def _urgency_reason(data: PriorityInput) -> dict:
    urgency_key = (data.urgency or "").strip().lower()
    return {
        "factor": "Resident urgency",
        "points": URGENCY_POINTS.get(urgency_key, 0),
        "reason": f"resident urgency: {urgency_key or 'not stated'}",
    }


def priority_level(score: int) -> str:
    """Band a 0-100 score. Four levels, matching the incidents table."""
    if score >= CRITICAL_THRESHOLD:
        return "CRITICAL"
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def calculate_priority(data: PriorityInput | dict) -> dict:
    """Score an incident and explain every point.

    Accepts a PriorityInput or an incident-shaped dict. The returned keys match
    the incidents table and IncidentOut exactly, so a caller can merge the
    result straight into an incident record.
    """
    if isinstance(data, dict):
        data = PriorityInput.from_dict(data)

    safety = _safety_reasons(data)
    road = _road_reason(data)
    facility = _facility_reason(data)
    age = _age_reason(data)
    reports = _report_reason(data)
    urgency = _urgency_reason(data)

    # Only scoring factors are explained; a zero adds nothing to explain.
    scored = [item for item in [*safety, road, facility, age, reports, urgency] if item["points"] > 0]

    reasons = [
        {**item, "label": f"+{item['points']} {item['reason']}"} for item in scored
    ]

    score = sum(item["points"] for item in reasons)

    factors = {
        "safety": sum(item["points"] for item in safety),
        "road_impact": road["points"],
        "facility": facility["points"],
        "persistence": age["points"],
        "report_count": reports["points"],
        "urgency": urgency["points"],
    }

    return {
        "priority_score": score,
        "priority_level": priority_level(score),
        "priority_reasons": reasons,
        "priority_factors": factors,
    }


def days_between(earlier: datetime | None, later: datetime | None = None) -> float:
    """Day gap between two timestamps, for the age factor.

    Returns 0 when the earlier timestamp is missing, so absent data never
    inflates a score. The caller decides what "later" means; Step 8 passes now.
    """
    if earlier is None:
        return 0.0
    later = later or datetime.now(timezone.utc)
    if earlier.tzinfo is None:
        earlier = earlier.replace(tzinfo=timezone.utc)
    if later.tzinfo is None:
        later = later.replace(tzinfo=timezone.utc)
    return max((later - earlier).total_seconds() / 86400.0, 0.0)


def parse_iso_datetime(value) -> datetime | None:
    """Parse a timestamp column value (Supabase returns ISO 8601 strings).

    Returns None for anything unparseable rather than raising, so a bad or
    missing first_reported_at degrades the age factor to 0 instead of crashing
    enrichment (CLAUDE.md section 9: one bad value must not fail a batch).
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


if __name__ == "__main__":
    examples = [
        (
            "Open manhole, main road, college nearby, 8 days old, 5 reports",
            PriorityInput(
                severity="critical",
                road_class="main road",
                facility_distance_m=80,
                nearest_facility="Vidyala College",
                age_days=8,
                report_count=5,
                urgency="High",
                description="Dangerous open manhole, a child nearly fell in.",
                hazards=("open hole", "pedestrian fall"),
            ),
        ),
        (
            "Faded road marking, lane, single same-day report",
            PriorityInput(severity="low", road_class="lane", age_days=0, report_count=1),
        ),
        (
            "Unknown severity, unresolved location, 2 reports over 2 days",
            PriorityInput(severity=None, road_class=None, age_days=2, report_count=2),
        ),
        (
            "Low severity but alarming resident language",
            PriorityInput(
                severity="low",
                road_class="bus route",
                age_days=0,
                report_count=1,
                description="Flooding again, an elderly man tripped and fell yesterday.",
            ),
        ),
    ]

    for title, data in examples:
        result = calculate_priority(data)
        print()
        print(f"  {title}")
        print(f"  score {result['priority_score']}/100 -> {result['priority_level']}")
        for item in result["priority_reasons"]:
            print(f"      {item['label']}")

    first = examples[0][1]
    print()
    print("  deterministic:", calculate_priority(first) == calculate_priority(first))
    print("  dict input matches dataclass input:",
          calculate_priority(first) == calculate_priority({
              "severity": "critical", "road_class": "main road",
              "facility_distance_m": 80, "nearest_facility": "Vidyala College",
              "age_days": 8, "report_count": 5, "urgency": "High",
              "description": "Dangerous open manhole, a child nearly fell in.",
              "hazards": ["open hole", "pedestrian fall"],
          }))
