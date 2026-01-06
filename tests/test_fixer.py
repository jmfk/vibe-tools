from unittest.mock import patch

from vibe_tools.fixer import run_test_fix_loop


def test_run_test_fix_loop_success():
    with patch("vibe_tools.fixer.run_tests") as mock_tests:
        with patch("vibe_tools.fixer.get_prompt"):
            with patch("vibe_tools.fixer.run_agent") as mock_agent:
                # Return 4 values: output, passed, env_failures, failed_targets
                mock_tests.return_value = ("passed", True, [], [])

                with patch("vibe_tools.fixer.load_state", return_value=None):
                    with patch("vibe_tools.fixer.clear_state") as mock_clear:
                        run_test_fix_loop()
                        mock_clear.assert_called_once()
                        mock_agent.assert_not_called()


def test_run_test_fix_loop_failure_then_success():
    with patch("vibe_tools.fixer.run_tests") as mock_tests:
        with patch("vibe_tools.fixer.run_agent") as mock_agent:
            with patch("vibe_tools.fixer.get_prompt") as mock_get_prompt:
                mock_get_prompt.return_value = "fix it {test_output}"

                # First fail, then pass
                mock_tests.side_effect = [
                    ("failed", False, [], ["target1"]),
                    ("passed", True, [], []),
                ]
                mock_agent.return_value = ("fixed", 0)

                with patch("vibe_tools.fixer.load_state", return_value=None):
                    with patch("vibe_tools.fixer.save_state") as mock_save:
                        with patch("vibe_tools.fixer.clear_state") as mock_clear:
                            run_test_fix_loop()
                            assert mock_tests.call_count == 2
                            mock_agent.assert_called_once()
                            mock_save.assert_called_once()
                            mock_clear.assert_called_once()
