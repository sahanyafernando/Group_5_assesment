from datetime import datetime, timedelta, timezone

import pytest

from app.services.priority_service import (
    MAX_SAFETY,
    PriorityInput,
    calculate_priority,
    days_between,
    matched_safety_keywords,
    priority_level,
)


def score(**kwargs) -> int:
    return calculate_priority(PriorityInput(**kwargs))["priority_score"]


# --- CLAUDE.md section 15: required priority tests ---------------------------


def test_priority_is_deterministic():
    data = PriorityInput(
        severity="high",
        road_class="main road",
        facility_distance_m=80,
        age_days=4,
        report_count=5,
        urgency="high",
        description="Dangerous pothole, a car was damaged.",
        hazards=("vehicle damage",),
    )
    assert calculate_priority(data) == calculate_priority(data)


def test_priority_does_not_exceed_100():
    result = calculate_priority(
        PriorityInput(
            severity="critical",
            road_class="main road",
            facility_distance_m=20,
            age_days=20,
            report_count=20,
            urgency="high",
            description="accident near-miss dangerous flooding collapsed open manhole fell tripped child elderly",
            hazards=tuple(f"hazard {n}" for n in range(10)),
        )
    )
    assert result["priority_score"] <= 100
    assert result["priority_level"] == "CRITICAL"


def test_priority_reasons_total_score():
    result = calculate_priority(
        PriorityInput(
            severity="medium",
            road_class="residential",
            facility_distance_m=150,
            age_days=3,
            report_count=3,
            urgency="medium",
        )
    )
    assert sum(item["points"] for item in result["priority_reasons"]) == result["priority_score"]


def test_main_road_scores_above_lane():
    common = dict(severity="medium", facility_distance_m=None, age_days=0, report_count=1, urgency=None)
    assert score(road_class="main road", **common) > score(road_class="lane", **common)


def test_multiple_reports_increase_score():
    common = dict(severity="medium", road_class="residential", age_days=0, urgency=None)
    assert score(report_count=1, **common) < score(report_count=2, **common) < score(report_count=3, **common) < score(report_count=5, **common)


# --- Factor bands (REQUIREMENTS.md section 5) --------------------------------


@pytest.mark.parametrize(
    ("severity", "points"),
    [("critical", 35), ("high", 28), ("medium", 18), ("low", 8), ("unknown", 10), (None, 10), ("nonsense", 10)],
)
def test_severity_band(severity, points):
    assert score(severity=severity) == points


@pytest.mark.parametrize(
    ("road_class", "points"),
    [("main road", 20), ("bus route", 15), ("residential", 8), ("lane", 5), (None, 0), ("motorway", 0)],
)
def test_road_band(road_class, points):
    assert score(severity="unknown", road_class=road_class) == 10 + points


@pytest.mark.parametrize(
    ("distance", "points"), [(100, 15), (101, 10), (200, 10), (201, 5), (300, 5), (301, 0), (None, 0)]
)
def test_facility_band(distance, points):
    assert score(severity="unknown", facility_distance_m=distance) == 10 + points


@pytest.mark.parametrize(("days", "points"), [(0, 0), (0.9, 0), (1, 5), (3, 10), (7, 10), (7.1, 15), (30, 15)])
def test_age_band(days, points):
    assert score(severity="unknown", age_days=days) == 10 + points


@pytest.mark.parametrize(("count", "points"), [(1, 0), (2, 3), (3, 6), (4, 6), (5, 10), (50, 10)])
def test_report_count_band(count, points):
    assert score(severity="unknown", report_count=count) == 10 + points


@pytest.mark.parametrize(("urgency", "points"), [("High", 5), ("medium", 3), ("LOW", 1), (None, 0), ("", 0)])
def test_urgency_band_is_case_insensitive(urgency, points):
    assert score(severity="unknown", urgency=urgency) == 10 + points


# --- Safety boosts -----------------------------------------------------------


def test_keyword_scan_finds_expected_terms():
    found = matched_safety_keywords("A child tripped near the flooding and a car damage claim followed.")
    assert found == ["child", "flooding", "tripped", "vehicle damage"]


def test_keyword_scan_is_sorted_and_stable():
    text = "dangerous flooding accident"
    assert matched_safety_keywords(text) == matched_safety_keywords(text) == ["accident", "dangerous", "flooding"]


def test_keyword_scan_avoids_false_positives():
    assert matched_safety_keywords("Please fix the road, a trip to the shops is hard.") == []
    assert matched_safety_keywords("") == []


def test_safety_keywords_raise_the_score():
    plain = score(severity="low", description="The pavement slab is loose.")
    alarming = score(severity="low", description="Dangerous loose slab, an elderly resident fell.")
    assert alarming > plain


def test_hazards_raise_the_score():
    assert score(severity="low", hazards=("trip hazard", "open hole")) > score(severity="low")


def test_safety_boost_is_capped_at_factor_ceiling():
    """Critical severity already spends the full 35, so boosts add nothing."""
    description = "accident dangerous flooding collapsed child elderly fell tripped"
    hazards = ("a", "b", "c", "d", "e")
    assert score(severity="critical", description=description, hazards=hazards) == MAX_SAFETY
    result = calculate_priority(
        PriorityInput(severity="critical", description=description, hazards=hazards)
    )
    assert result["priority_factors"]["safety"] == MAX_SAFETY


def test_safety_boost_partially_fills_headroom():
    """High severity leaves 7 points of headroom; boosts fill exactly that."""
    result = calculate_priority(
        PriorityInput(
            severity="high",
            description="accident dangerous flooding collapsed",
            hazards=("a", "b", "c"),
        )
    )
    assert result["priority_factors"]["safety"] == MAX_SAFETY


def test_factors_sum_to_the_score():
    result = calculate_priority(
        PriorityInput(
            severity="high",
            road_class="bus route",
            facility_distance_m=120,
            age_days=4,
            report_count=3,
            urgency="High",
            description="A child fell.",
        )
    )
    assert sum(result["priority_factors"].values()) == result["priority_score"]


# --- Levels ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "level"),
    [(100, "CRITICAL"), (85, "CRITICAL"), (84, "HIGH"), (65, "HIGH"), (64, "MEDIUM"), (40, "MEDIUM"), (39, "LOW"), (0, "LOW")],
)
def test_priority_level_thresholds(value, level):
    assert priority_level(value) == level


# --- Explanations ------------------------------------------------------------


def test_every_reason_has_a_label_and_positive_points():
    result = calculate_priority(
        PriorityInput(severity="high", road_class="main road", report_count=3, urgency="High")
    )
    for item in result["priority_reasons"]:
        assert item["points"] > 0
        assert item["label"] == f"+{item['points']} {item['reason']}"
        assert item["factor"]


def test_zero_scoring_factors_are_not_explained():
    """A factor worth nothing adds no noise to the explanation."""
    result = calculate_priority(PriorityInput(severity="low", road_class=None, report_count=1))
    factors = {item["factor"] for item in result["priority_reasons"]}
    assert factors == {"Safety / severity"}


def test_facility_reason_names_the_facility():
    result = calculate_priority(
        PriorityInput(severity="low", facility_distance_m=120, nearest_facility="Vidyala College")
    )
    labels = [item["label"] for item in result["priority_reasons"]]
    assert "+10 near Vidyala College (120m)" in labels


# --- Dict input --------------------------------------------------------------


def test_dict_input_matches_dataclass_input():
    kwargs = dict(
        severity="high",
        road_class="bus route",
        facility_distance_m=120,
        age_days=4,
        report_count=3,
        urgency="High",
        description="A child fell.",
    )
    from_dataclass = calculate_priority(PriorityInput(hazards=("trip",), **kwargs))
    from_dict = calculate_priority({**kwargs, "hazards": ["trip"]})
    assert from_dataclass == from_dict


def test_dict_input_tolerates_missing_keys():
    result = calculate_priority({})
    assert result["priority_score"] == 10
    assert result["priority_level"] == "LOW"


def test_dict_input_falls_back_to_title_and_summary_text():
    result = calculate_priority(
        {"severity": "low", "title": "Dangerous open manhole", "summary": "A child nearly fell in."}
    )
    assert result["priority_factors"]["safety"] > 8


def test_result_keys_match_incident_fields():
    """Keys must merge straight into an incident record."""
    assert set(calculate_priority({}).keys()) == {
        "priority_score",
        "priority_level",
        "priority_reasons",
        "priority_factors",
    }


# --- days_between ------------------------------------------------------------


def test_days_between_counts_whole_days():
    later = datetime(2026, 9, 8, tzinfo=timezone.utc)
    assert days_between(later - timedelta(days=3), later) == pytest.approx(3.0)


def test_days_between_handles_missing_and_naive_timestamps():
    assert days_between(None) == 0.0
    later = datetime(2026, 9, 8)
    assert days_between(datetime(2026, 9, 1), later) == pytest.approx(7.0)


def test_days_between_never_returns_negative():
    later = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert days_between(later + timedelta(days=5), later) == 0.0
