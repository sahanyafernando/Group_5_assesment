"""Location enrichment from the assets table.

REQUIREMENTS.md FR-11 / FR-06: an incident's canonical_road is resolved
elsewhere (location resolution, CLAUDE.md step 4/Person A); this service takes
that resolved road name and looks up what the council knows about it -- ward,
road class, and the nearest critical facility. assets.csv is the only
authority on whether a road or asset exists (CLAUDE.md section 5): Claude may
suggest a road_hint, but this table is what confirms it.

Results are cached in memory per process, since assets.csv does not change
during a session (Person B step 6).
"""

from app.db.supabase import get_supabase_client

# road_name (lowercased) -> enrichment dict. Populated lazily; never expires
# during a process lifetime because asset data is static for the session.
_CACHE: dict[str, dict] = {}

EMPTY_ENRICHMENT: dict = {
    "ward": None,
    "road_class": None,
    "asset_types": [],
    "nearest_facility": None,
    "facility_distance_m": None,
}


def _build_enrichment(rows: list[dict]) -> dict:
    """Combine every asset row for one road into a single enrichment dict.

    ward, road_class, nearest_facility and facility_distance_m are identical
    across every asset row for a given road in the supplied data (verified:
    zero roads disagree), so the first row supplies them. asset_types is the
    one field that genuinely varies row to row, so it is the union.
    """
    if not rows:
        return dict(EMPTY_ENRICHMENT)

    first = rows[0]
    asset_types = sorted({row["asset_type"] for row in rows if row.get("asset_type")})

    return {
        "ward": first.get("ward"),
        "road_class": first.get("road_class"),
        "asset_types": asset_types,
        "nearest_facility": first.get("nearest_facility") or None,
        "facility_distance_m": first.get("facility_distance_m"),
    }


def enrich_from_assets(road_name: str | None, *, db=None, use_cache: bool = True) -> dict:
    """Ward / road_class / facility context for a canonical road.

    Returns EMPTY_ENRICHMENT when the road is unknown or unmatched -- an empty
    result means "the council has no asset record for this road," it is not an
    error and should not crash a batch (CLAUDE.md section 9).
    """
    road = (road_name or "").strip()
    if not road:
        return dict(EMPTY_ENRICHMENT)

    cache_key = road.lower()
    if use_cache and cache_key in _CACHE:
        return dict(_CACHE[cache_key])

    db = db or get_supabase_client()
    response = db.table("assets").select("*").ilike("road_name", road).execute()
    rows = response.data or []

    enrichment = _build_enrichment(rows)
    if use_cache:
        _CACHE[cache_key] = enrichment
    return dict(enrichment)


def clear_cache() -> None:
    """Drop the in-memory cache. Mainly for tests, or after re-importing assets."""
    _CACHE.clear()


def cache_size() -> int:
    return len(_CACHE)


if __name__ == "__main__":
    # Runs against Supabase. Requires backend/.env and an imported assets table.
    roads = [
        "Station Road",
        "station road",
        "  Kirula Road  ",
        "Galle Road",
        "Nowhere Street",
        None,
        "",
    ]

    print("  road -> enrichment")
    for road in roads:
        result = enrich_from_assets(road)
        print(f"      {str(road)!r:<20} ward={result['ward']!r:<20} road_class={result['road_class']!r:<12} "
              f"assets={result['asset_types']} facility={result['nearest_facility']!r} ({result['facility_distance_m']})")

    print()
    print(f"  cache size after {len(roads)} lookups: {cache_size()}")
    print("  repeat lookup uses cache (no query):", enrich_from_assets("Station Road") == enrich_from_assets("Station Road"))
