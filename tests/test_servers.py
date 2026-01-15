from unittest.mock import patch

import pytest
from click.testing import CliRunner

from vibe_tools.servers import servers_cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_global_servers(tmp_path, monkeypatch):
    global_vibe = tmp_path / ".vibe"
    global_vibe.mkdir()
    servers_file = global_vibe / "servers.json"
    config_file = global_vibe / "config.json"

    monkeypatch.setattr("vibe_tools.utils.GLOBAL_VIBE_DIR", global_vibe)
    monkeypatch.setattr("vibe_tools.utils.GLOBAL_SERVERS_FILE", servers_file)
    monkeypatch.setattr("vibe_tools.utils.GLOBAL_CONFIG_FILE", config_file)

    return global_vibe


def test_list_servers(runner, mock_global_servers):
    with patch("vibe_tools.servers.run_command") as mock_run:
        # Mock docker inspect response (not created)
        mock_run.return_value = ("", 1)

        result = runner.invoke(servers_cli, ["list"])

        assert result.exit_code == 0
        assert "Service" in result.output
        assert "postgres" in result.output
        assert "⚪ Not Installed" in result.output
        assert (mock_global_servers / "servers.json").exists()


def test_install_server(runner, mock_global_servers):
    with patch("vibe_tools.servers.run_command") as mock_run:
        # 1. inspect (not created)
        # 2. docker run (success)
        mock_run.side_effect = [
            ("", 1),  # inspect fails -> not created
            ("container_id", 0),  # docker run succeeds
        ]

        result = runner.invoke(servers_cli, ["install", "redis"])

        assert result.exit_code == 0
        assert "Installing redis..." in result.output
        assert "✅ redis installed and started successfully." in result.output
        assert "✅ Saved connection details to global config." in result.output

        # Verify global config was updated
        import json

        config_data = json.loads((mock_global_servers / "config.json").read_text())
        assert "redis" in config_data["services"]
        assert config_data["services"]["redis"]["port"] == 6379


def test_start_server(runner, mock_global_servers):
    with patch("vibe_tools.servers.run_command") as mock_run:
        # 1. inspect (exited)
        # 2. docker start (success)
        mock_run.side_effect = [("exited", 0), ("", 0)]

        result = runner.invoke(servers_cli, ["start", "postgres"])

        assert result.exit_code == 0
        assert "Starting postgres..." in result.output
        assert "✅ postgres started." in result.output

        # Check docker start call
        mock_run.assert_any_call(["docker", "start", "vibe-postgres"], check=False)


def test_stop_server(runner):
    with patch("vibe_tools.servers.run_command") as mock_run:
        # 1. inspect (running)
        # 2. docker stop (success)
        mock_run.side_effect = [("running", 0), ("", 0)]

        result = runner.invoke(servers_cli, ["stop", "rabbitmq"])

        assert result.exit_code == 0
        assert "Stopping rabbitmq..." in result.output
        assert "✅ rabbitmq stopped." in result.output

        # Check docker stop call
        mock_run.assert_any_call(["docker", "stop", "vibe-rabbitmq"], check=False)


def test_remove_server(runner):
    with patch("vibe_tools.servers.run_command") as mock_run:
        # 1. inspect (exited)
        # 2. docker rm (success)
        mock_run.side_effect = [("exited", 0), ("", 0)]

        # Provide 'y' to the confirmation prompt
        result = runner.invoke(servers_cli, ["remove", "mailhog"], input="y\n")

        assert result.exit_code == 0
        assert "Removing mailhog..." in result.output
        assert "✅ mailhog removed." in result.output

        # Check docker rm call
        mock_run.assert_any_call(["docker", "rm", "-f", "vibe-mailhog"], check=False)
