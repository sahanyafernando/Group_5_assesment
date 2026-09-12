from app.services.crew_service import recommend_crew


def test_road_surface_mapping():
    assert recommend_crew("Pothole") == "Road Surface"


def test_drainage_mapping():
    assert recommend_crew("Manhole") == "Drainage"


def test_lighting_mapping():
    assert recommend_crew("Streetlight") == "Lighting & Street Furniture"


def test_unsupported_goes_to_manual_review():
    assert recommend_crew("Unsupported") == "Manual Review"


def test_unknown_goes_to_manual_review():
    assert recommend_crew("Tree removal") == "Manual Review"
