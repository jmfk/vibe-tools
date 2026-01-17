import pathlib
from unittest.mock import MagicMock, patch

import pytest

from vibe_tools.ralph import RalphLoop, COMPLETION_PROMISE


@pytest.fixture
def mock_prd():
    prd = MagicMock()
    prd.id = "PRD-TEST"
    prd.title = "Test PRD"
    prd.content = "Test Content"
    prd.path = pathlib.Path("product/backlog/PRD-TEST-test.md")
    return prd


def test_ralph_loop_initialization(tmp_path):
    current_file = tmp_path / "test.txt"
    loop = RalphLoop(
        name="Test Loop",
        desired_content="Desired",
        desired_file_name="desired.txt",
        current_file=current_file,
    )
    assert loop.name == "Test Loop"
    assert loop.desired_content == "Desired"
    assert "vibe/test_loop" in loop.branch_name


def test_ralph_loop_sync_check(tmp_path):
    current_file = tmp_path / "test.txt"
    content = "Sync Content"
    current_file.write_text(content)

    loop = RalphLoop(
        name="Test Loop",
        desired_content=content,
        desired_file_name="test.txt",
        current_file=current_file,
    )

    with patch("vibe_tools.ralph._switch_to_branch") as mock_switch:
        assert loop.run() is True
        mock_switch.assert_called_once()


@patch("vibe_tools.ralph.run_agent")
@patch("vibe_tools.ralph.get_agent_command")
@patch("vibe_tools.ralph._switch_to_branch")
@patch("vibe_tools.ralph.is_dirty")
@patch("vibe_tools.ralph.run_command")
def test_ralph_loop_reconciliation(
    mock_run_cmd, mock_is_dirty, mock_switch, mock_get_cmd, mock_run_agent, tmp_path
):
    current_file = tmp_path / "test.txt"
    current_file.write_text("Old Content")

    loop = RalphLoop(
        name="Test Loop",
        desired_content="New Content",
        desired_file_name="test.txt",
        current_file=current_file,
    )

    mock_get_cmd.return_value = ["mock-agent", "prompt"]
    mock_run_agent.return_value = (f"Fixed it! {COMPLETION_PROMISE}", 0)
    mock_is_dirty.return_value = True

    assert loop.run() is True

    # Check if agent was called
    mock_run_agent.assert_called()
    
    # Check if changes were committed
    mock_run_cmd.assert_any_call(["git", "add", "."], check=False)


@patch("vibe_tools.ralph.run_agent")
@patch("vibe_tools.ralph.get_agent_command")
@patch("vibe_tools.ralph._switch_to_branch")
def test_ralph_loop_failure(mock_switch, mock_get_cmd, mock_run_agent, tmp_path):
    current_file = tmp_path / "test.txt"
    current_file.write_text("Old Content")

    # Mock config for max iterations
    with patch("vibe_tools.ralph.load_config", return_value={"iterations": {"reconciliation": 2}}):
        loop = RalphLoop(
            name="Test Loop",
            desired_content="New Content",
            desired_file_name="test.txt",
            current_file=current_file,
        )

        mock_get_cmd.return_value = ["mock-agent", "prompt"]
        mock_run_agent.return_value = ("Incomplete work", 0)

        assert loop.run() is False
        assert mock_run_agent.call_count == 2
