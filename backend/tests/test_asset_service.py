import pytest

from app.services.asset_service import (
    EMPTY_ENRICHMENT,
    cache_size,
    clear_cache,
    enrich_from_assets,
)
from tests.fakes import ExplodingSupabase, FakeSupabase

ASSETS = [
    {"road_name": "Station Road", "ward": "Bambalapitiya", "road_class": "bus route",
     "asset_type": "bus shelter", "nearest_facility": "Vidyala College", "facility_distance_m": 120},
    {"road_name": "Station Road", "ward": "Bambalapitiya", "road_class": "bus route",
     "asset_type": "streetlight", "nearest_facility": "Vidyala College", "facility_distance_m": 120},
    {"road_name": "Station Road", "ward": "Bambalapitiya", "road_class": "bus route",
     "asset_type": "drain", "nearest_facility": "Vidyala College", "facility_distance_m": 120},
    {"road_name": "Galle Road", "ward": "Kollupitiya", "road_class": "main road",
     "asset_type": "footpath", "nearest_facility": None, "facility_distance_m": None},
    {"road_name": "Kirula Road", "ward": "Thimbirigasyaya", "road_class": "residential",
     "asset_type": "drain", "nearest_facility": "", "facility_distance_m": None},
]


@pytest.fixture(autouse=True)
def _clear_cache():
    """Every test starts with a cold cache -- results must not leak between tests."""
    clear_cache()
    yield
    clear_cache()


def db() -> FakeSupabase:
    return FakeSupabase(tables={"assets": ASSETS})


# --- Aggregation --------------------------------------------------------------


def test_combines_asset_types_from_multiple_rows():
    result = enrich_from_assets("Station Road", db=db())
    assert result["asset_types"] == ["bus shelter", "drain", "streetlight"]


def test_ward_and_road_class_come_from_the_matched_rows():
    result = enrich_from_assets("Station Road", db=db())
    assert result["ward"] == "Bambalapitiya"
    assert result["road_class"] == "bus route"


def test_single_asset_row_road():
    result = enrich_from_assets("Galle Road", db=db())
    assert result["asset_types"] == ["footpath"]
    assert result["road_class"] == "main road"


def test_blank_facility_becomes_none_not_empty_string():
    result = enrich_from_assets("Kirula Road", db=db())
    assert result["nearest_facility"] is None
    assert result["facility_distance_m"] is None


# --- Matching -----------------------------------------------------------------


def test_road_match_is_case_insensitive():
    assert enrich_from_assets("station road", db=db())["ward"] == "Bambalapitiya"
    assert enrich_from_assets("STATION ROAD", db=db())["ward"] == "Bambalapitiya"


def test_road_match_tolerates_surrounding_whitespace():
    assert enrich_from_assets("  Station Road  ", db=db())["ward"] == "Bambalapitiya"


# --- Unknown / missing input never crashes ------------------------------------


@pytest.mark.parametrize("road", [None, "", "   ", "Nowhere Street"])
def test_unknown_or_missing_road_returns_empty_shape(road):
    assert enrich_from_assets(road, db=db()) == EMPTY_ENRICHMENT


def test_missing_road_does_not_query_the_database():
    client = db()
    enrich_from_assets(None, db=client, use_cache=False)
    enrich_from_assets("", db=client, use_cache=False)
    assert client.calls == []


def test_empty_result_is_a_fresh_dict_not_a_shared_reference():
    """Callers must be able to mutate their copy without corrupting the sentinel."""
    result = enrich_from_assets("Nowhere Street", db=db())
    result["ward"] = "mutated"
    assert EMPTY_ENRICHMENT["ward"] is None


# --- Caching -------------------------------------------------------------------


def test_second_lookup_uses_the_cache_not_a_new_query():
    client = db()
    enrich_from_assets("Station Road", db=client)
    calls_after_first = len(client.calls)
    enrich_from_assets("Station Road", db=client)
    assert len(client.calls) == calls_after_first  # no additional query


def test_cache_is_keyed_case_insensitively():
    client = db()
    enrich_from_assets("Station Road", db=client)
    calls_after_first = len(client.calls)
    enrich_from_assets("STATION ROAD", db=client)
    assert len(client.calls) == calls_after_first


def test_use_cache_false_bypasses_and_does_not_populate_cache():
    client = db()
    enrich_from_assets("Station Road", db=client, use_cache=False)
    assert cache_size() == 0


def test_cached_result_is_a_copy_not_a_shared_reference():
    client = db()
    first = enrich_from_assets("Station Road", db=client)
    first["ward"] = "mutated"
    second = enrich_from_assets("Station Road", db=client)
    assert second["ward"] == "Bambalapitiya"


def test_clear_cache_forces_a_fresh_query():
    client = db()
    enrich_from_assets("Station Road", db=client)
    clear_cache()
    assert cache_size() == 0
    enrich_from_assets("Station Road", db=client)
    assert cache_size() == 1


# --- Errors propagate, never a silent empty result ----------------------------


def test_query_errors_are_raised_not_swallowed():
    with pytest.raises(RuntimeError, match="connection reset"):
        enrich_from_assets("Station Road", db=ExplodingSupabase())
