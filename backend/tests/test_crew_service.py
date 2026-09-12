import pytest

from app.schemas.common import CREW_ORDER
from app.services.crew_service import (
    ALL_CREWS,
    ALLOWED_WORK_TYPES,
    CREW_MAP,
    MANUAL_REVIEW,
    get_all_crews,
    get_all_work_types,
    get_crew,
    is_supported_work_type,
    recommend_crew,
)


# --- CLAUDE.md section 15: the mappings that must hold -----------------------


def test_road_surface_mapping():
    assert recommend_crew("Pothole") == "Road Surface"


def test_drainage_mapping():
    assert recommend_crew("Manhole") == "Drainage"


def test_lighting_mapping():
    assert recommend_crew("Streetlight") == "Lighting & Street Furniture"


def test_unsupported_goes_to_manual_review():
    assert recommend_crew("Unsupported") == MANUAL_REVIEW


def test_unknown_goes_to_manual_review():
    assert recommend_crew("Tree removal") == MANUAL_REVIEW


# --- Every mapping in the table, so a typo cannot slip through ---------------


@pytest.mark.parametrize(("work_type", "crew"), sorted(CREW_MAP.items()))
def test_every_mapped_work_type(work_type, crew):
    assert get_crew(work_type) == crew


# --- Fallback behaviour ------------------------------------------------------


@pytest.mark.parametrize("work_type", [None, "", "   ", "Unsupported", "Tree removal", "Graffiti"])
def test_missing_or_unmapped_falls_back(work_type):
    assert get_crew(work_type) == MANUAL_REVIEW


def test_casing_and_whitespace_are_tolerated():
    """Normalization only -- it never introduces a work type outside CREW_MAP."""
    assert get_crew("  pothole  ") == "Road Surface"
    assert get_crew("BLOCKED DRAIN") == "Drainage"
    assert get_crew("Bus   shelter") == "Lighting & Street Furniture"


def test_normalization_does_not_invent_mappings():
    assert get_crew("pot hole") == MANUAL_REVIEW
    assert get_crew("potholes") == MANUAL_REVIEW


def test_mapping_is_deterministic():
    assert [get_crew("Gully") for _ in range(5)] == ["Drainage"] * 5


# --- Introspection helpers ---------------------------------------------------


def test_get_all_work_types_matches_allowed_list():
    work_types = get_all_work_types()
    assert work_types == ALLOWED_WORK_TYPES
    assert "Unsupported" in work_types
    assert len(work_types) == 15


def test_get_all_work_types_returns_a_copy():
    get_all_work_types().append("Tree removal")
    assert "Tree removal" not in ALLOWED_WORK_TYPES


def test_get_all_crews_is_three_specialists_plus_manual_review():
    crews = get_all_crews()
    assert crews == ["Road Surface", "Drainage", "Lighting & Street Furniture", MANUAL_REVIEW]
    assert set(crews[:3]) == set(CREW_MAP.values())


def test_crew_order_matches_the_schema_literal_order():
    """Dispatch queue order must not drift from app.schemas.common."""
    assert tuple(get_all_crews()) == CREW_ORDER == ALL_CREWS


def test_no_work_type_maps_to_manual_review_directly():
    """Manual Review is a fallback, never an entry in the table."""
    assert MANUAL_REVIEW not in CREW_MAP.values()


def test_is_supported_work_type():
    assert is_supported_work_type("Kerb") is True
    assert is_supported_work_type("Unsupported") is False
    assert is_supported_work_type(None) is False
