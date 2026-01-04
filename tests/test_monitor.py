import pytest
import time
import datetime
from unittest.mock import patch, MagicMock
from vibe_tools.monitor import run_monitor, get_status_report

def test_run_monitor():
    with patch("vibe_tools.monitor.get_status_report") as mock_report:
        mock_report.return_value = None
        
        # We'll mock time.sleep to raise an exception to break the loop
        with patch("time.sleep", side_effect=InterruptedError()):
            with pytest.raises(InterruptedError):
                run_monitor(agent="cursor-agent", interval=1)
        
        mock_report.assert_called()

def test_get_status_report(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    monitor_prompt = prompts_dir / "monitor_prompt.txt"
    monitor_prompt.write_text("monitor {timestamp} {current_branch} {git_status} {last_diff}")
    
    with patch("vibe_tools.monitor.PROMPTS_DIR", prompts_dir):
        with patch("vibe_tools.monitor.MONITOR_PROMPT_TEMPLATE", monitor_prompt):
            with patch("vibe_tools.monitor.run_command") as mock_run:
                with patch("vibe_tools.monitor.run_agent") as mock_agent:
                    # 1. git rev-parse (success)
                    # 2. git branch (success)
                    # 3. git status (success)
                    # 4. git diff (success)
                    mock_run.side_effect = [
                        ("", 0),
                        ("main", 0),
                        ("M file.py", 0),
                        ("diff content", 0)
                    ]
                    mock_agent.return_value = ("report", 0)
                    
                    get_status_report(agent="cursor-agent", interval=60)
                    
                    assert mock_agent.called
                    assert mock_run.call_count == 4
