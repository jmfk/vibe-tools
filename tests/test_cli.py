from unittest.mock import patch

import pytest
from click.testing import CliRunner

from vibe_tools.cli import cli, load_config
from vibe_tools.utils import save_config


@pytest.fixture
def runner():
    return CliRunner()


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


def test_init_command(runner, tmp_path):
    with patch("vibe_tools.setup.maybe_init_git"):
        with patch("vibe_tools.commands.init.perform_basic_init") as mock_basic:
            with patch("vibe_tools.commands.init.guide_setup", return_value=True):
                # Provide 'D' for manual setup
                result = runner.invoke(cli, ["init"], input="D\n")
                assert result.exit_code == 0
                mock_basic.assert_called_once()


def test_normalize_command(runner):
    with patch("vibe_tools.normalize.normalize_prd") as mock_normalize:
        result = runner.invoke(cli, ["normalize", "input.md", "--yes"])
        assert result.exit_code == 0
        mock_normalize.assert_called_once()


def test_test_fix_command(runner):
    with patch("vibe_tools.fixer.run_test_fix_loop") as mock_loop:
        result = runner.invoke(cli, ["test-fix"])
        assert result.exit_code == 0
        mock_loop.assert_called_once()


def test_memory_command_saves_file(runner, tmp_path, monkeypatch):
    instructions_dir = tmp_path / "instructions"
    instructions_dir.mkdir()
    monkeypatch.setattr("vibe_tools.utils.INSTRUCTIONS_DIR", instructions_dir)

    result = runner.invoke(cli, ["memory", "Test instruction"])

    assert result.exit_code == 0
    assert "Memory saved" in result.output
    files = list(instructions_dir.glob("memory_*_test_instruction.txt"))
    assert len(files) == 1
    assert files[0].read_text() == "Test instruction"


def test_memory_list_command(runner, tmp_path, monkeypatch):
    instructions_dir = tmp_path / "instructions"
    instructions_dir.mkdir()
    monkeypatch.setattr("vibe_tools.utils.INSTRUCTIONS_DIR", instructions_dir)
    (instructions_dir / "memory_1.txt").write_text("Instruction 1")

    result = runner.invoke(cli, ["memory", "--list"])

    assert result.exit_code == 0
    assert "Current memories:" in result.output
    assert "memory_1.txt" in result.output
    assert "Instruction 1" in result.output
