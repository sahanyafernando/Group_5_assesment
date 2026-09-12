from dataclasses import dataclass


@dataclass(frozen=True)
class PriorityInput:
    severity: str | None = None
    road_class: str | None = None
    facility_distance_m: float | None = None
    age_days: float = 0
    report_count: int = 1
    urgency: str | None = None


SEVERITY_POINTS = {
    "critical": 35,
    "high": 28,
    "medium": 18,
    "low": 8,
    "unknown": 10,
}

ROAD_POINTS = {
    "main road": 20,
    "bus route": 15,
    "residential": 8,
    "lane": 5,
}

URGENCY_POINTS = {
    "high": 5,
    "medium": 3,
    "low": 1,
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


def _age_points(days: float) -> int:
    if days > 7:
        return 15
    if days >= 3:
        return 10
    if days >= 1:
        return 5
    return 0


def _report_points(count: int) -> int:
    if count >= 5:
        return 10
    if count >= 3:
        return 6
    if count == 2:
        return 3
    return 0


def priority_level(score: int) -> str:
    if score >= 85:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def calculate_priority(data: PriorityInput) -> dict:
    severity_key = (data.severity or "unknown").strip().lower()
    road_key = (data.road_class or "").strip().lower()
    urgency_key = (data.urgency or "").strip().lower()

    factors = [
        (
            "Safety / severity",
            SEVERITY_POINTS.get(severity_key, SEVERITY_POINTS["unknown"]),
            f"Severity classified as {severity_key}.",
        ),
        (
            "Road / public impact",
            ROAD_POINTS.get(road_key, 0),
            f"Road class is {road_key or 'unknown'}.",
        ),
        (
            "Critical facility",
            _facility_points(data.facility_distance_m),
            (
                f"Nearest critical/public facility is {data.facility_distance_m:.0f}m away."
                if data.facility_distance_m is not None
                else "No facility distance available."
            ),
        ),
        (
            "Age / persistence",
            _age_points(data.age_days),
            f"Incident age is approximately {data.age_days:.1f} day(s).",
        ),
        (
            "Multiple reports",
            _report_points(data.report_count),
            f"{data.report_count} report(s) support this incident.",
        ),
        (
            "Resident urgency",
            URGENCY_POINTS.get(urgency_key, 0),
            f"Resident urgency is {urgency_key or 'missing'}.",
        ),
    ]

    reasons = [
        {"factor": factor, "points": points, "reason": reason}
        for factor, points, reason in factors
        if points > 0
    ]

    score = min(100, sum(item["points"] for item in reasons))

    return {
        "score": score,
        "level": priority_level(score),
        "reasons": reasons,
    }
