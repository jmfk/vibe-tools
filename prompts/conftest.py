import pytest
import os
import sys

# Ensure the root directory is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    # Ensure tests use the local data directory
    data_dir = os.environ.get("VIBE_DATA_DIR", "vibe_data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
