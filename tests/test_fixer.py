import pytest
import json
from unittest.mock import patch, MagicMock
from vibe_tools.fixer import run_test_fix_loop

def test_run_test_fix_loop_success():
    with patch("vibe_tools.fixer.run_tests") as mock_tests:
        with patch("vibe_tools.fixer.PROMPTS_DIR") as mock_prompts_dir:
            with patch("vibe_tools.fixer.run_agent") as mock_agent:
                mock_prompts_dir.exists.return_value = True
                mock_tests.return_value = ("passed", True, [])
                
                with patch("vibe_tools.fixer.load_state", return_value=None):
                    with patch("vibe_tools.fixer.clear_state") as mock_clear:
                        run_test_fix_loop()
                        mock_clear.assert_called_once()
                        mock_agent.assert_not_called()

def test_run_test_fix_loop_failure_then_success():
    with patch("vibe_tools.fixer.run_tests") as mock_tests:
        with patch("vibe_tools.fixer.run_agent") as mock_agent:
            with patch("vibe_tools.fixer.PROMPTS_DIR") as mock_prompts_dir:
                with patch("vibe_tools.fixer.TEST_FIX_PROMPT_TEMPLATE") as mock_template:
                    mock_prompts_dir.exists.return_value = True
                    mock_template.exists.return_value = True
                    mock_template.read_text.return_value = "fix it {test_output}"
                    
                    # First fail, then pass
                    mock_tests.side_effect = [("failed", False, []), ("passed", True, [])]
                    mock_agent.return_value = ("fixed", 0)
                    
                    with patch("vibe_tools.fixer.load_state", return_value=None):
                        with patch("vibe_tools.fixer.save_state") as mock_save:
                            with patch("vibe_tools.fixer.clear_state") as mock_clear:
                                run_test_fix_loop()
                                assert mock_tests.call_count == 2
                                mock_agent.assert_called_once()
                                mock_save.assert_called_once()
                                mock_clear.assert_called_once()
