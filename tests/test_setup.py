import pathlib
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from vibe_tools.setup import check_connection, setup_cli


def _return_default(*args, default=None, **kwargs):
    return default


def test_check_connection_success():
    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__.return_value = MagicMock()
        assert check_connection("postgres", {"host": "localhost", "port": 5432}) is True


def test_check_connection_failure():
    with patch("socket.create_connection", side_effect=ConnectionRefusedError):
        assert check_connection("postgres", {"host": "localhost", "port": 5432}) is False


def test_api_command_writes_env_keys():
    runner = CliRunner()

    result = runner.invoke(setup_cli, ["api"], input="google-key\ncursor-key\n")

    assert result.exit_code == 0
    assert "Saved Google API key." in result.output
    assert "Saved Cursor API key." in result.output
    env_contents = pathlib.Path(".env").read_text()
    assert "GOOGLE_API_KEY=google-key" in env_contents
    assert "CURSOR_API_KEY=cursor-key" in env_contents


def test_service_command_saves_detected_defaults():
    runner = CliRunner()
    detection = {"host": "127.0.0.1", "port": 15432, "container_name": "postgres-dev"}

    with patch("vibe_tools.setup.detect_docker_service", return_value=detection):
        with patch("vibe_tools.setup.click.prompt", side_effect=_return_default):
            with patch("vibe_tools.setup.check_connection", return_value=True):
                result = runner.invoke(setup_cli, ["postgres"])

    assert result.exit_code == 0
    config_contents = pathlib.Path(".vibe-tools/config.json").read_text()
    assert "postgres-dev" in config_contents
    assert "15432" in config_contents
