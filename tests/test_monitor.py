from unittest.mock import patch

import pytest

from vibe_tools.monitor import get_status_report, run_monitor


def test_run_monitor():
    with patch("vibe_tools.monitor.get_status_report") as mock_report:
        mock_report.return_value = None

        # We'll mock time.sleep to raise an exception to break the loop
        with patch("time.sleep", side_effect=InterruptedError()):
            with pytest.raises(InterruptedError):
                run_monitor(agent="cursor-agent", interval=1)

        mock_report.assert_called()


def test_get_status_report(tmp_path):
    with patch("vibe_tools.monitor.get_prompt") as mock_get_prompt:
        mock_get_prompt.return_value = "monitor {timestamp} {current_branch} {git_status} {last_diff}"
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
                    ("diff content", 0),
                ]
                mock_agent.return_value = ("report", 0)

                get_status_report(agent="cursor-agent", interval=60)

                assert mock_agent.called
                assert mock_run.call_count == 4
