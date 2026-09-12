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

ALLOWED_WORK_TYPES = [*CREW_MAP.keys(), "Unsupported"]


def recommend_crew(work_type: str | None) -> str:
    if not work_type:
        return "Manual Review"
    return CREW_MAP.get(work_type, "Manual Review")
