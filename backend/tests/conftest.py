"""Shared fixtures for API-level tests.

Forces DEMO_MODE for the whole test session so router tests are deterministic
and never touch the network (CLAUDE.md section 14), independent of whatever
backend/.env happens to have on a given machine.
"""

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True, scope="session")
def _force_demo_mode():
    import os

    os.environ["DEMO_MODE"] = "true"
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import demo_store

    demo_store.reset()
    with TestClient(app) as test_client:
        yield test_client
    demo_store.reset()
