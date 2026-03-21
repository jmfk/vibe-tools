import json
from unittest.mock import patch

from click.testing import CliRunner

from vibe_tools.servers import servers_cli
from vibe_tools import utils


def test_list_servers_shows_known_services():
    runner = CliRunner()

    def mock_run_command(cmd, **kwargs):
        if cmd[:2] == ["docker", "info"]:
            return ("", 0)
        if cmd[:2] == ["docker", "inspect"]:
            return ("", 1)
        return ("", 0)

    with patch("vibe_tools.servers.run_command", side_effect=mock_run_command):
        result = runner.invoke(servers_cli, ["list"])

    assert result.exit_code == 0
    assert "postgres" in result.output
    assert "Not Installed" in result.output


def test_install_server_updates_global_config():
    runner = CliRunner()

    with patch("vibe_tools.servers.get_container_status", return_value="not_created"):
        with patch("vibe_tools.servers.run_command", return_value=("container-id", 0)):
            result = runner.invoke(servers_cli, ["install", "redis"])

    assert result.exit_code == 0
    config = json.loads(utils.GLOBAL_CONFIG_FILE.read_text())
    assert config["services"]["redis"]["port"] == 6379


def test_start_and_stop_server_call_docker():
    runner = CliRunner()

    with patch("vibe_tools.servers.get_container_status", return_value="exited"):
        with patch("vibe_tools.servers.run_command", return_value=("", 0)) as mock_run:
            start_result = runner.invoke(servers_cli, ["start", "postgres"])
    assert start_result.exit_code == 0
    mock_run.assert_called_with(["docker", "start", "vibe-postgres"], check=False)

    with patch("vibe_tools.servers.get_container_status", return_value="running"):
        with patch("vibe_tools.servers.run_command", return_value=("", 0)) as mock_run:
            stop_result = runner.invoke(servers_cli, ["stop", "postgres"])
    assert stop_result.exit_code == 0
    mock_run.assert_called_with(["docker", "stop", "vibe-postgres"], check=False)
