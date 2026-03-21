from unittest.mock import patch

import pytest

import vibe_tools.utils as utils


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    global_dir = tmp_path / ".global-vibe-tools"
    monkeypatch.setattr(utils, "GLOBAL_VIBE_TOOLS_DIR", global_dir)
    monkeypatch.setattr(utils, "GLOBAL_CONFIG_FILE", global_dir / "config.json")
    monkeypatch.setattr(utils, "GLOBAL_SERVERS_FILE", global_dir / "servers.json")
    monkeypatch.setattr(utils, "PROJECTS_REGISTRY_FILE", global_dir / "projects.json")

    with patch("atexit.register"):
        yield
