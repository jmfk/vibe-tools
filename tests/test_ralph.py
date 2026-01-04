import pytest
import json
import pathlib
import sys
from unittest.mock import patch, MagicMock
from vibe_tools.ralph import (
    save_state, load_state, mark_prd_completed, ralph_loop, 
    run_tests_logic, run_review_logic
)

@pytest.fixture
def mock_state_file(tmp_path):
    state_file = tmp_path / ".ralph_state.json"
    with patch("vibe_tools.ralph.STATE_FILE", state_file):
        yield state_file

def test_save_and_load_state(mock_state_file):
    save_state("prd_test", 1, "output", "context", "build")
    
    state = load_state()
    assert state["active_task"]["prd_name"] == "prd_test"
    assert state["active_task"]["iteration"] == 1
    assert state["active_task"]["phase"] == "build"

def test_mark_prd_completed(mock_state_file):
    mark_prd_completed("prd_test")
    state = load_state()
    assert "prd_test" in state["completed_prds"]
    assert state["active_task"] is None

def test_run_tests_logic():
    with patch("vibe_tools.ralph.ProjectTester") as mock_tester_cls:
        mock_tester = mock_tester_cls.return_value
        mock_tester.run_tests.return_value = ("output", True, [])
        
        output, passed, env_failures = run_tests_logic()
        assert passed == True
        assert output == "output"

def test_run_review_logic():
    with patch("vibe_tools.ralph.REVIEW_PROMPT_TEMPLATE") as mock_template:
        with patch("vibe_tools.ralph.run_agent") as mock_agent:
            mock_template.exists.return_value = True
            mock_template.read_text.return_value = "review {prd_path}"
            mock_agent.return_value = ("<review>PASSED</review>", 0)
            
            output, passed = run_review_logic("cursor-agent", "prd.yaml")
            assert passed == True
            assert "<review>PASSED</review>" in output

def test_ralph_loop_with_test_failure(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "ralph_base_prompt.txt").write_text("base prompt")
    
    prds_dir = tmp_path / "prds"
    prds_dir.mkdir()
    (prds_dir / "prd_01_test.yaml").write_text("prd content")
    
    with patch("vibe_tools.ralph.PRD_DIR", prds_dir):
        with patch("vibe_tools.ralph.PROMPTS_DIR", prompts_dir):
            with patch("vibe_tools.ralph.run_command") as mock_run:
                with patch("vibe_tools.ralph.run_ralph_agent") as mock_agent:
                    with patch("vibe_tools.ralph.run_tests_logic") as mock_tests:
                        with patch("vibe_tools.ralph.run_agent") as mock_commit_agent:
                            mock_run.return_value = ("", 0)
                            mock_agent.return_value = "done <promise>DONE</promise>"
                            # First tests fail, then we'll stop
                            mock_tests.side_effect = [("failed", False, []), ("passed", True, [])]
                            mock_commit_agent.return_value = ("committed", 0)
                            
                            with patch("vibe_tools.ralph.STATE_FILE", tmp_path / ".state.json"):
                                with patch("vibe_tools.ralph.MAX_ITERATIONS", 2):
                                    ralph_loop(tests=True, review=False)
                                    
def test_ralph_loop_resuming(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "ralph_base_prompt.txt").write_text("base prompt")
    
    prds_dir = tmp_path / "prds"
    prds_dir.mkdir()
    (prds_dir / "prd_01_test.yaml").write_text("prd content")
    
    state_file = tmp_path / ".ralph_state.json"
    state_data = {
        "completed_prds": [],
        "active_task": {
            "prd_name": "prd_01_test",
            "iteration": 2,
            "phase": "test",
            "output": "previous output",
            "context": "previous context"
        }
    }
    state_file.write_text(json.dumps(state_data))
    
    with patch("vibe_tools.ralph.PRD_DIR", prds_dir):
        with patch("vibe_tools.ralph.PROMPTS_DIR", prompts_dir):
            with patch("vibe_tools.ralph.STATE_FILE", state_file):
                with patch("vibe_tools.ralph.run_command") as mock_run:
                    with patch("vibe_tools.ralph.run_tests_logic") as mock_tests:
                        with patch("vibe_tools.ralph.mark_prd_completed") as mock_completed:
                            with patch("vibe_tools.ralph.run_agent") as mock_agent:
                                mock_run.return_value = ("", 0)
                                mock_tests.return_value = ("passed", True, [])
                                mock_agent.return_value = ("committed", 0)
                                
                                ralph_loop(tests=True, review=False)
                                
                                # Should have started at iteration 2 and phase test
                                mock_tests.assert_called_once()
                                mock_completed.assert_called_once_with("prd_01_test")
                                mock_agent.assert_called_once()
