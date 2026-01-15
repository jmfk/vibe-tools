from unittest.mock import patch

from vibe_tools.coverage import improve_coverage_loop


def test_improve_coverage_loop_already_100():
    with patch("vibe_tools.coverage.get_coverage_report") as mock_report:
        with patch("vibe_tools.coverage.get_prompt"):
            with patch("vibe_tools.coverage.run_agent") as mock_agent:
                with patch("vibe_tools.cli.load_config", return_value={}):
                    mock_report.return_value = ("report", 100)

                    improve_coverage_loop()
                    mock_report.assert_called_once()
                    mock_agent.assert_not_called()


def test_improve_coverage_loop_improvement():
    with patch("vibe_tools.coverage.get_coverage_report") as mock_report:
        with patch("vibe_tools.coverage.run_agent") as mock_agent:
            with patch("vibe_tools.coverage.run_command") as mock_run:
                with patch("vibe_tools.coverage.get_prompt") as mock_get_prompt:
                    with patch("vibe_tools.cli.load_config", return_value={}):
                        mock_get_prompt.return_value = "improve it {report}"

                        # First 50%, then 70%
                        mock_report.side_effect = [("report1", 50), ("report2", 70)]
                        mock_agent.return_value = ("done <promise>DONE</promise>", 0)
                        mock_run.return_value = ("", 0)

                        # Set MAX_ITERATIONS to 1 to keep test fast
                        with patch("vibe_tools.coverage.MAX_ITERATIONS", 1):
                            improve_coverage_loop()
                            assert mock_report.call_count == 2
                            mock_agent.assert_called_once()
                            # Verify git commit was called
                            mock_run.assert_any_call(
                                [
                                    "git",
                                    "commit",
                                    "-m",
                                    "Improve test coverage from 50% to 70%",
                                ],
                            )
