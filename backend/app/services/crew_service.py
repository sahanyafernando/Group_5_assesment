"""Deterministic work type -> crew mapping.

CLAUDE.md section 7: the final crew recommendation is made ONLY here. There is
no AI in this module, no network call, and no database read -- the same input
always produces the same crew.

Do not silently extend CREW_MAP. A work type the council has no crew history
for must fall through to Manual Review so Maya decides, rather than consuming a
specialist crew slot on work they cannot do (DECISIONS.md D3).
"""

MANUAL_REVIEW = "Manual Review"
UNSUPPORTED = "Unsupported"

CREW_MAP: dict[str, str] = {
    "Pothole": "Road Surface",
    "Road surface damage": "Road Surface",
    "Pavement damage": "Road Surface",
    "Kerb": "Road Surface",
    "Road marking": "Road Surface",
    "Blocked drain": "Drainage",
    "Gully": "Drainage",
    "Culvert": "Drainage",
    "Manhole": "Drainage",
    "Drainage flooding": "Drainage",
    "Streetlight": "Lighting & Street Furniture",
    "Sign post": "Lighting & Street Furniture",
    "Bus shelter": "Lighting & Street Furniture",
    "Bench": "Lighting & Street Furniture",
}

# Every work type Claude is allowed to return (CLAUDE.md section 6).
ALLOWED_WORK_TYPES: list[str] = [*CREW_MAP.keys(), UNSUPPORTED]

# The three specialist crews, in dict insertion order, then the fallback queue.
SPECIALIST_CREWS: tuple[str, ...] = tuple(dict.fromkeys(CREW_MAP.values()))
ALL_CREWS: tuple[str, ...] = (*SPECIALIST_CREWS, MANUAL_REVIEW)

# Exact spellings only. This index tolerates casing and stray whitespace in
# stored data; it does NOT add any new work type to the mapping.
_NORMALIZED_MAP: dict[str, str] = {
    " ".join(work_type.lower().split()): crew for work_type, crew in CREW_MAP.items()
}


def get_crew(work_type: str | None) -> str:
    """Return the crew responsible for a work type.

    Returns "Manual Review" for None, blank, "Unsupported", or any work type
    that is not in CREW_MAP.
    """
    if not work_type or not work_type.strip():
        return MANUAL_REVIEW

    if work_type in CREW_MAP:
        return CREW_MAP[work_type]

    normalized = " ".join(work_type.lower().split())
    return _NORMALIZED_MAP.get(normalized, MANUAL_REVIEW)


def get_all_work_types() -> list[str]:
    """Every valid work type, including the Unsupported sentinel."""
    return list(ALLOWED_WORK_TYPES)


def get_all_crews() -> list[str]:
    """The three specialist crews plus Manual Review, in dispatch order."""
    return list(ALL_CREWS)


def is_supported_work_type(work_type: str | None) -> bool:
    """True when a crew can be assigned without coordinator review."""
    return get_crew(work_type) != MANUAL_REVIEW


# Kept as the original name so existing callers and CLAUDE.md section 15 keep working.
recommend_crew = get_crew


if __name__ == "__main__":
    checks = [
        ("Pothole", "Road Surface"),
        ("Road marking", "Road Surface"),
        ("Manhole", "Drainage"),
        ("Drainage flooding", "Drainage"),
        ("Streetlight", "Lighting & Street Furniture"),
        ("Bench", "Lighting & Street Furniture"),
        ("Unsupported", MANUAL_REVIEW),
        ("Tree removal", MANUAL_REVIEW),
        ("", MANUAL_REVIEW),
        (None, MANUAL_REVIEW),
        ("  pothole  ", "Road Surface"),
    ]

    failures = 0
    for work_type, expected in checks:
        actual = get_crew(work_type)
        ok = actual == expected
        failures += not ok
        print(f"  [{'ok' if ok else 'FAIL'}] {str(work_type)!r:<18} -> {actual}")

    print()
    print(f"  work types ({len(get_all_work_types())}): {get_all_work_types()}")
    print(f"  crews ({len(get_all_crews())}): {get_all_crews()}")
    print()
    print("All crew mapping checks passed." if not failures else f"{failures} check(s) FAILED.")
    raise SystemExit(1 if failures else 0)
