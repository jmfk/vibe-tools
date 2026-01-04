import json
import pathlib
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner
from vibe_tools.setup import setup_cli, check_connection

SERVICE_TEST_DETECTIONS = {
    "postgres": {"host": "127.0.0.1", "port": 15432, "container_name": "postgres-docker"},
    "redis": {"host": "127.0.0.1", "port": 16379, "container_name": "redis-docker"},
    "rabbitmq": {"host": "127.0.0.1", "port": 5673, "container_name": "rabbitmq-docker"},
    "elasticsearch": {"host": "127.0.0.1", "port": 9201, "container_name": "es-docker"},
}

SERVICE_COMMANDS = [
    ("postgres", "postgres"),
    ("redis", "redis"),
    ("rabbitmq", "rabbitmq"),
    ("elasticsearch", "elasticsearch"),
]

def _prompt_return_default(*args, default=None, **kwargs):
    return default

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mock_config(tmp_path):
    config_file = tmp_path / ".vibe_config.json"
    config = {
        "services": {
            "postgres": {"host": "localhost", "port": 5432},
            "redis": {"host": "localhost", "port": 6379}
        }
    }
    config_file.write_text(json.dumps(config))
    return config_file

def test_check_connection_success():
    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__.return_value = MagicMock()
        assert check_connection("postgres", {"host": "localhost", "port": 5432}) is True

def test_check_connection_failure():
    with patch("socket.create_connection", side_effect=ConnectionRefusedError):
        assert check_connection("postgres", {"host": "localhost", "port": 5432}) is False

def test_setup_test_command(runner, mock_config, monkeypatch):
    monkeypatch.setattr("vibe_tools.utils.CONFIG_FILE", mock_config)
    
    with patch("vibe_tools.setup.check_connection") as mock_check:
        mock_check.side_effect = [True, False] # postgres ok, redis fails
        
        result = runner.invoke(setup_cli, ["test"])
        
        assert result.exit_code == 0
        assert "PostgreSQL" in result.output
        assert "✅ Connected" in result.output
        assert "Redis" in result.output
        assert "❌ Failed" in result.output

@pytest.mark.parametrize("command, service_key", SERVICE_COMMANDS)
def test_setup_service_commands_save_config(runner, tmp_path, command, service_key):
    config_file = tmp_path / ".vibe_config.json"
    detection = SERVICE_TEST_DETECTIONS[service_key]

    with patch("vibe_tools.utils.CONFIG_FILE", config_file):
        with patch("vibe_tools.setup.detect_docker_service", return_value=detection):
            with patch("vibe_tools.setup.click.prompt", side_effect=_prompt_return_default):
                with patch("vibe_tools.setup.ensure_gitignore"):
                    with patch("vibe_tools.setup.check_connection", return_value=True):
                        result = runner.invoke(setup_cli, [command])
                        assert result.exit_code == 0

    content = json.loads(config_file.read_text())
    service_settings = content["services"][service_key]
    assert service_settings["host"] == detection["host"]
    assert service_settings["port"] == detection["port"]
    assert service_settings["docker_container_name"] == detection["container_name"]

def test_setup_api_command(runner, tmp_path):
    config_file = tmp_path / ".vibe_config.json"
    env_file = tmp_path / ".env"
    with patch("vibe_tools.utils.CONFIG_FILE", config_file):
        with patch("vibe_tools.utils.find_dotenv", return_value=str(env_file)):
            with patch("vibe_tools.setup.click.prompt", return_value="fake-google-key"):
                result = runner.invoke(setup_cli, ["api"])
                assert result.exit_code == 0
                assert "Google API Key saved to .env" in result.output

    assert "GOOGLE_API_KEY" in env_file.read_text()
    assert "fake-google-key" in env_file.read_text()
