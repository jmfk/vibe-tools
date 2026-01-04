import logging
import pathlib
import pytest
import json
from unittest.mock import patch, MagicMock
from vibe_tools import utils
from vibe_tools.utils import (
    logger, enable_console_debug, run_command, 
    ensure_dir, rotate_log, is_merged, run_agent, get_agent_command,
    is_git_repo, ensure_gitignore
)

def test_enable_console_debug():
    # Ensure stream_handler is not None for the test
    if utils.stream_handler is None:
        utils.stream_handler = logging.StreamHandler()
        utils.logger.addHandler(utils.stream_handler)

    # Initial level might have been changed by previous tests, so we set it back
    utils.stream_handler.setLevel(logging.INFO)
    assert utils.stream_handler.level == logging.INFO
    
    enable_console_debug()
    
    assert utils.stream_handler.level == logging.DEBUG
    assert logger.level == logging.DEBUG

def test_ensure_dir(tmp_path):
    test_dir = tmp_path / "test_dir"
    assert not test_dir.exists()
    
    ensure_dir(test_dir)
    assert test_dir.exists()
    
    # Run again to ensure it doesn't fail if exists
    ensure_dir(test_dir)
    assert test_dir.exists()

def test_run_command_success():
    stdout, code = run_command(["echo", "hello"], check=True)
    assert stdout == "hello"
    assert code == 0

def test_run_command_failure():
    # Using a command that returns non-zero
    stdout, code = run_command(["false"], check=False)
    assert code != 0

def test_rotate_log(tmp_path):
    with patch("vibe_tools.utils.LOG_FILE", tmp_path / "vibe.log"):
        with patch("vibe_tools.utils.file_handler") as mock_handler:
            # File doesn't exist
            rotate_log()
            mock_handler.doRollover.assert_not_called()
            
            # File exists and not empty
            log_file = tmp_path / "vibe.log"
            log_file.write_text("some logs")
            rotate_log()
            mock_handler.doRollover.assert_called_once()

def test_is_merged():
    with patch("vibe_tools.utils.run_command") as mock_run:
        mock_run.return_value = ("", 0)
        assert is_merged("feature/branch") == True
        
        mock_run.return_value = ("", 1)
        assert is_merged("feature/branch") == False

def test_run_agent():
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["line1\n", "line2\n", ""]
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        output, code = run_agent(["some-agent", "prompt"])
        assert "line1\nline2\n" in output
        assert code == 0

def test_get_agent_command():
    assert get_agent_command("cursor-agent", "prompt")[0] == "cursor-agent"
    assert get_agent_command("claude", "prompt")[0] == "claude"
    assert get_agent_command("antigravity", "prompt")[0] == "antigravity"
    with pytest.raises(ValueError):
        get_agent_command("unknown", "prompt")

def test_is_git_repo():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert is_git_repo() == True
        
        mock_run.return_value.returncode = 1
        assert is_git_repo() == False
        
        mock_run.side_effect = FileNotFoundError()
        assert is_git_repo() == False

def test_ensure_gitignore(tmp_path):
    gitignore = tmp_path / ".gitignore"
    with patch("pathlib.Path.exists", return_value=False):
        with patch("vibe_tools.utils.pathlib.Path") as mock_path:
            mock_path.return_value = MagicMock()
            mock_path.return_value.exists.return_value = False
            ensure_gitignore(".vibe_config.json")
            mock_path.return_value.write_text.assert_called_once()
