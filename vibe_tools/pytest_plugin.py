import os
import pytest
import sys
from unittest.mock import patch


def pytest_configure(config):
    """
    Globally configure pytest to enforce vibe-tools non-intrusive testing policy.
    This runs automatically for any project using pytest with vibe-tools installed.
    """
    # Enforce test mode environment variables
    os.environ["VIBE_TEST_MODE"] = "1"
    os.environ["VIBE_AGENT_ACTIVE"] = "1"


@pytest.fixture(autouse=True)
def enforce_vibe_safeguards(monkeypatch):
    """
    Autouse fixture to ensure environment variables and basic mocks are in place.
    """
    monkeypatch.setenv("VIBE_TEST_MODE", "1")
    monkeypatch.setenv("VIBE_AGENT_ACTIVE", "1")

    # Patch potentially destructive global operations if they are imported
    with patch("atexit.register"):
        yield
