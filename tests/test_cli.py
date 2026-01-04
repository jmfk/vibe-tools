from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vibe_tools.cli import cli, load_config, save_config


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
    config_file = tmp_path / ".vibe_config.json"
    with patch("vibe_tools.cli.CONFIG_FILE", config_file):
        config = {"test": "value"}
        save_config(config)
        assert load_config() == config


def test_init_command(runner, tmp_path):
    with patch("vibe_tools.cli.maybe_init_git") as mock_git:
        with patch("vibe_tools.cli.ensure_dir"):
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            mock_git.assert_called_once()


def test_ralph_command_prompt(runner, tmp_path):
    config_file = tmp_path / ".vibe_config.json"
    with patch("vibe_tools.cli.CONFIG_FILE", config_file):
        with patch("vibe_tools.cli.maybe_init_git"):
            with patch("vibe_tools.ralph.ralph_loop"):
                # 1. Enable Tests? y
                # 2. Enable Agentic Review? y
                # 3. Enable Auto-merge? n
                # 4. Set budget? 5.0
                # 5. Enable verbose? n
                # 6. Use caffeinate? y
                # 7. Save settings? y
                # 8. Proceed with Ralph loop? n
                result = runner.invoke(cli, ["ralph"], input="y\ny\nn\n5.0\nn\ny\ny\nn\n")
                assert "Aborted" in result.output


def test_history_command(runner):
    with patch("vibe_tools.cli.PRD_DIR") as mock_prd_dir:
        mock_prd_dir.exists.return_value = True
        mock_file = MagicMock()
        mock_file.stem = "prd_01_test"
        mock_prd_dir.glob.return_value = [mock_file]

        with patch("vibe_tools.ralph.load_state", return_value={"completed_prds": [], "started_prds": []}):
            result = runner.invoke(cli, ["history"])
            assert result.exit_code == 0
            assert "prd_01_test" in result.output
            assert "PENDING" in result.output


def test_rerun_command_found(runner, tmp_path):
    prds_dir = tmp_path / "prds"
    prds_dir.mkdir()
    prd_file = prds_dir / "prd_01_test.yaml"
    prd_file.write_text("content")

    with patch("vibe_tools.cli.PRD_DIR", prds_dir):
        state_file = tmp_path / "state.json"
        with patch("vibe_tools.cli.STATE_FILE", state_file):
            with patch("vibe_tools.cli.run_command") as mock_run:
                mock_run.return_value = ("main", 0)  # branch check
                with patch("vibe_tools.ralph.load_state", return_value={"completed_prds": ["prd_01_test"], "started_prds": ["prd_01_test"]}):
                    result = runner.invoke(cli, ["rerun", "01"])
                    assert "Rerunning PRD: prd_01_test" in result.output
                    assert "Removed from completed PRDs list." in result.output
                    assert "Removed from started PRDs list." in result.output


def test_monitor_command(runner):
    with patch("vibe_tools.monitor.run_monitor") as mock_monitor:
        result = runner.invoke(cli, ["monitor", "--interval", "10"])
        assert result.exit_code == 0
        mock_monitor.assert_called_once()


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
