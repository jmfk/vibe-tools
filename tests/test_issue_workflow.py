import pytest
from click.testing import CliRunner
from vibe_tools.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_issue_workflow(runner, tmp_path, monkeypatch):
    # Setup temporary directories
    product_dir = tmp_path / "product"
    product_dir.mkdir()
    (product_dir / "backlog").mkdir()
    (product_dir / "inbox").mkdir()
    (product_dir / "history").mkdir()
    (product_dir / "in_progress").mkdir()

    monkeypatch.setattr("vibe_tools.utils.PRODUCT_DIR", product_dir)
    monkeypatch.setattr("vibe_tools.utils.PRODUCT_BACKLOG_DIR", product_dir / "backlog")
    monkeypatch.setattr(
        "vibe_tools.utils.PRODUCT_IN_PROGRESS_DIR", product_dir / "in_progress"
    )
    monkeypatch.setattr("vibe_tools.utils.PRODUCT_HISTORY_DIR", product_dir / "history")
    monkeypatch.setattr("vibe_tools.utils.PLANNING_INBOX_DIR", product_dir / "inbox")

    # 1. Add an issue
    with monkeypatch.context() as m:
        m.setattr(
            "vibe_tools.commands.plan.run_llm",
            lambda x: '{"title": "Test Issue", "summary": "Test Summary", "severity": "high", "service": "core"}',
        )
        result = runner.invoke(cli, ["plan", "add", "Test prompt"])
        assert result.exit_code == 0
        assert "Issue created successfully" in result.output

    # Check if file exists in inbox
    inbox_files = list((product_dir / "inbox").glob("*.md"))
    assert len(inbox_files) == 1
    issue_path = inbox_files[0]
    assert "PRD-001" in issue_path.name

    # 2. List issues
    result = runner.invoke(cli, ["issue", "list"])
    assert result.exit_code == 0
    assert "PRD-001" in result.output
    assert "Test Issue" in result.output

    # 3. Solve issue (this will transition status and move file)
    # Mock implementation_loop to avoid running agent
    with monkeypatch.context() as m:
        m.setattr(
            "vibe_tools.commands.solve.implementation_loop",
            lambda agent, stream=False: True,
        )
        result = runner.invoke(cli, ["solve", "PRD-001"])
        assert result.exit_code == 0
        assert "Starting solve mode" in result.output

    # Check if moved to in_progress
    in_progress_files = list((product_dir / "in_progress").glob("*.md"))
    assert len(in_progress_files) == 1
    assert not (product_dir / "inbox" / issue_path.name).exists()

    # 4. Close issue
    result = runner.invoke(cli, ["issue", "close", "PRD-001"])
    assert result.exit_code == 0
    assert "marked as done and moved to history" in result.output

    # Check if moved to history
    history_files = list((product_dir / "history").glob("*.md"))
    assert len(history_files) == 1
    assert not (product_dir / "in_progress" / issue_path.name).exists()
