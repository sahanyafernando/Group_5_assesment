from app.services.priority_service import PriorityInput, calculate_priority


def test_priority_is_deterministic():
    data = PriorityInput(
        severity="high",
        road_class="main road",
        facility_distance_m=80,
        age_days=4,
        report_count=5,
        urgency="high",
    )
    assert calculate_priority(data) == calculate_priority(data)


def test_priority_does_not_exceed_100():
    data = PriorityInput(
        severity="critical",
        road_class="main road",
        facility_distance_m=20,
        age_days=20,
        report_count=20,
        urgency="high",
    )
    assert calculate_priority(data)["score"] <= 100


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
    assert sum(item["points"] for item in result["reasons"]) == result["score"]


def test_main_road_scores_above_lane():
    common = dict(
        severity="medium",
        facility_distance_m=None,
        age_days=0,
        report_count=1,
        urgency=None,
    )
    main_road = calculate_priority(PriorityInput(road_class="main road", **common))
    lane = calculate_priority(PriorityInput(road_class="lane", **common))
    assert main_road["score"] > lane["score"]
