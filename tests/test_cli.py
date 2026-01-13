from unittest.mock import patch

import pytest
from click.testing import CliRunner

from vibe_tools.cli import cli, load_config
from vibe_tools.utils import save_config, save_memory, perform_basic_init


@pytest.fixture
def runner():
    return CliRunner()


def test_save_memory_logic(tmp_path, monkeypatch):
    instructions_dir = tmp_path / "instructions"
    instructions_dir.mkdir()
    monkeypatch.setattr("vibe_tools.utils.INSTRUCTIONS_DIR", instructions_dir)

    filepath = save_memory("Test instruction")

    assert filepath.exists()
    assert filepath.read_text() == "Test instruction"
    assert "test_instruction" in filepath.name


def test_perform_basic_init_logic(tmp_path, monkeypatch):
    # Setup temporary directory for the test
    project_dir = tmp_path / "implementation"
    monkeypatch.setattr("vibe_tools.utils.VIBE_PROJECT_DIR", project_dir)
    monkeypatch.setattr("vibe_tools.utils.CONFIG_FILE", project_dir / "config.json")
    monkeypatch.setattr("vibe_tools.utils.PRD_DIR", project_dir / "prds")
    monkeypatch.setattr("vibe_tools.utils.LOGS_DIR", project_dir / "logs")
    monkeypatch.setattr("vibe_tools.utils.COSTS_DIR", project_dir / "costs")
    monkeypatch.setattr("vibe_tools.utils.VIBE_DATA_DIR", project_dir / "data")
    monkeypatch.setattr(
        "vibe_tools.utils.INSTRUCTIONS_DIR", project_dir / "instructions"
    )

    with patch("vibe_tools.utils.maybe_init_git"):
        perform_basic_init()

    assert project_dir.exists()
    assert (project_dir / "config.json").exists()
    assert (project_dir / "prds").exists()
    assert (project_dir / "instructions").exists()


def test_cli_base(runner):
    result = runner.invoke(cli)
    assert result.exit_code == 0
    assert "vibe-tools configuration" in result.output


def test_cli_debug(runner):
    with patch("vibe_tools.cli.enable_console_debug") as mock_debug:
        runner.invoke(cli, ["--debug"])
        mock_debug.assert_called_once()


def test_load_save_config(tmp_path):
    config_file = tmp_path / "config.json"
    global_file = tmp_path / "global_config.json"
    with patch("vibe_tools.cli.CONFIG_FILE", config_file):
        with patch("vibe_tools.utils.CONFIG_FILE", config_file):
            with patch("vibe_tools.utils.GLOBAL_CONFIG_FILE", global_file):
                config = {"test": "value"}
                save_config(config)
                loaded = load_config()
                assert loaded["test"] == "value"


def test_normalize_command(runner):
    with patch("vibe_tools.normalize.normalize_prd") as mock_normalize:
        # Command doesn't take input file as argument in current version
        result = runner.invoke(cli, ["normalize", "--yes"])
        assert result.exit_code == 0
        mock_normalize.assert_called_once()


def test_test_fix_command(runner):
    # Patch the reference held by the command module
    with patch("vibe_tools.commands.test_fix.run_test_fix_loop") as mock_loop:
        result = runner.invoke(cli, ["test-fix"])
        assert result.exit_code == 0
        mock_loop.assert_called_once()


def test_memory_list_command(runner, tmp_path, monkeypatch):
    instructions_dir = tmp_path / "instructions"
    instructions_dir.mkdir()
    # Patch where it's used in the command module
    monkeypatch.setattr("vibe_tools.commands.memory.INSTRUCTIONS_DIR", instructions_dir)
    (instructions_dir / "memory_1.txt").write_text("Instruction 1")

    result = runner.invoke(cli, ["memory", "--list"])

    assert result.exit_code == 0
    assert "Current memories:" in result.output
    assert "memory_1.txt" in result.output
    assert "Instruction 1" in result.output
