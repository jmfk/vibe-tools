import os
import pathlib
import json
import pytest
from vibe_tools.issues import Issue, save_issue, load_issue_by_id, generate_issue_id, ISSUES_DIR, BACKLOG_DIR, HISTORY_DIR, get_issue_hash

def test_issue_serialization():
    issue = Issue(
        id="ISSUE-2026-01-09-001",
        title="Test Issue",
        status="backlog",
        severity="medium",
        service="core",
        created_at="2026-01-09T10:00:00Z",
        updated_at="2026-01-09T10:00:00Z",
        body="## Summary\nTest body"
    )
    
    markdown = issue.to_markdown()
    assert "id: ISSUE-2026-01-09-001" in markdown
    assert "status: backlog" in markdown
    assert "## Summary" in markdown
    
    loaded = Issue.from_markdown(markdown)
    assert loaded.id == issue.id
    assert loaded.title == issue.title
    assert loaded.body.to_markdown() == "## Summary\nTest body"

def test_save_and_load_issue(tmp_path, monkeypatch):
    # Setup temporary issues directory
    issues_dir = tmp_path / "issues"
    monkeypatch.setattr("vibe_tools.issues.ISSUES_DIR", issues_dir)
    monkeypatch.setattr("vibe_tools.issues.BACKLOG_DIR", issues_dir / "backlog")
    monkeypatch.setattr("vibe_tools.issues.HISTORY_DIR", issues_dir / "history")
    monkeypatch.setattr("vibe_tools.issues.META_DIR", issues_dir / "meta")
    monkeypatch.setattr("vibe_tools.issues.INDEX_FILE", issues_dir / "meta" / "index.json")

    issue = Issue(
        id="ISSUE-2026-01-09-001",
        title="Test Issue",
        status="backlog",
        severity="medium",
        service="core",
        created_at="2026-01-09T10:00:00Z",
        updated_at="2026-01-09T10:00:00Z",
        body="## Summary\nTest body"
    )
    
    save_issue(issue)
    
    # Check if file exists in backlog
    assert (issues_dir / "backlog" / f"{issue.id}.md").exists()
    
    # Load back
    loaded = load_issue_by_id(issue.id)
    assert loaded is not None
    assert loaded.id == issue.id
    
    # Transition to done
    issue.status = "done"
    save_issue(issue)
    
    assert not (issues_dir / "backlog" / f"{issue.id}.md").exists()
    assert (issues_dir / "history" / f"{issue.id}.md").exists()
    
    loaded_done = load_issue_by_id(issue.id)
    assert loaded_done.status == "done"

def test_issue_hash():
    issue = Issue(
        id="ISSUE-1",
        title="Title",
        status="backlog",
        severity="low",
        service="svc",
        created_at="now",
        updated_at="now",
        body="Body"
    )
    
    h1 = get_issue_hash(issue)
    
    issue.title = "New Title"
    h2 = get_issue_hash(issue)
    assert h1 != h2
    
    issue.title = "Title"
    assert h1 == get_issue_hash(issue)
    
    # Changing updated_at should NOT change hash
    issue.updated_at = "later"
    assert h1 == get_issue_hash(issue)

def test_generate_issue_id(tmp_path, monkeypatch):
    issues_dir = tmp_path / "issues"
    monkeypatch.setattr("vibe_tools.issues.ISSUES_DIR", issues_dir)
    monkeypatch.setattr("vibe_tools.issues.BACKLOG_DIR", issues_dir / "backlog")
    monkeypatch.setattr("vibe_tools.issues.HISTORY_DIR", issues_dir / "history")
    monkeypatch.setattr("vibe_tools.issues.META_DIR", issues_dir / "meta")
    monkeypatch.setattr("vibe_tools.issues.INDEX_FILE", issues_dir / "meta" / "index.json")
    
    id1 = generate_issue_id()
    assert id1.startswith("ISSUE-")
    
    # Save an issue to increment count
    issue = Issue(
        id=id1,
        title="T", status="backlog", severity="l", service="s",
        created_at="n", updated_at="n", body="B"
    )
    save_issue(issue)
    
    id2 = generate_issue_id()
    assert id2 != id1
    assert id2.endswith("002")
