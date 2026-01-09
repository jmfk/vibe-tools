import datetime
import json
import os
import pathlib
import yaml
import hashlib
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

ISSUES_DIR = pathlib.Path("issues")
BACKLOG_DIR = ISSUES_DIR / "backlog"
HISTORY_DIR = ISSUES_DIR / "history"
META_DIR = ISSUES_DIR / "meta"
INDEX_FILE = META_DIR / "index.json"

@dataclass
class GitHubInfo:
    repo: str
    number: int
    url: str

@dataclass
class SyncInfo:
    last_synced_at: str
    sync_hash: str

@dataclass
class Issue:
    id: str
    title: str
    status: str  # backlog, in_progress, blocked, done
    severity: str  # low, medium, high, critical
    service: str
    created_at: str
    updated_at: str
    body: str
    github: Optional[GitHubInfo] = None
    sync: Optional[SyncInfo] = None
    comments: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "severity": self.severity,
            "service": self.service,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.github:
            d["github"] = asdict(self.github)
        if self.sync:
            d["sync"] = asdict(self.sync)
        return d

    def to_markdown(self) -> str:
        frontmatter = self.to_dict()
        yaml_content = yaml.dump(frontmatter, sort_keys=False)
        content = f"---\n{yaml_content}---\n\n{self.body}"
        if self.comments:
            content += f"\n\n## External Comments (GitHub)\n{self.comments}"
        return content

    @classmethod
    def from_markdown(cls, content: str) -> "Issue":
        if not content.startswith("---"):
            raise ValueError("Invalid issue format: missing frontmatter")
        
        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("Invalid issue format: missing frontmatter or body")
        
        frontmatter = yaml.safe_load(parts[1])
        rest = parts[2].strip()
        
        body = rest
        comments = ""
        if "## External Comments (GitHub)" in rest:
            body, comments = rest.split("## External Comments (GitHub)", 1)
            body = body.strip()
            comments = comments.strip()
        
        github_data = frontmatter.get("github")
        github_info = GitHubInfo(**github_data) if github_data else None
        
        sync_data = frontmatter.get("sync")
        sync_info = SyncInfo(**sync_data) if sync_data else None
        
        return cls(
            id=frontmatter["id"],
            title=frontmatter["title"],
            status=frontmatter["status"],
            severity=frontmatter["severity"],
            service=frontmatter["service"],
            created_at=frontmatter["created_at"],
            updated_at=frontmatter["updated_at"],
            body=body,
            comments=comments,
            github=github_info,
            sync=sync_info
        )

def get_issue_hash(issue: Issue) -> str:
    # Hash only the fields that are synced (excluding sync info and comments)
    data = {
        "title": issue.title,
        "status": issue.status,
        "severity": issue.severity,
        "service": issue.service,
        "body": issue.body
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def load_index() -> Dict[str, Any]:
    if not INDEX_FILE.exists():
        return {}
    try:
        return json.loads(INDEX_FILE.read_text())
    except json.JSONDecodeError:
        return {}

def save_index(index: Dict[str, Any]):
    META_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2))

def save_issue(issue: Issue):
    target_dir = HISTORY_DIR if issue.status == "done" else BACKLOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = target_dir / f"{issue.id}.md"
    
    # If moving from backlog to history, delete from backlog
    if issue.status == "done":
        backlog_path = BACKLOG_DIR / f"{issue.id}.md"
        if backlog_path.exists():
            backlog_path.unlink()
    else:
        history_path = HISTORY_DIR / f"{issue.id}.md"
        if history_path.exists():
            history_path.unlink()

    file_path.write_text(issue.to_markdown())
    
    # Update index
    index = load_index()
    index[issue.id] = {
        "file": str(file_path),
        "github_number": issue.github.number if issue.github else None,
        "updated_at": issue.updated_at
    }
    save_index(index)

def load_issue_by_id(issue_id: str) -> Optional[Issue]:
    index = load_index()
    if issue_id not in index:
        # Try searching in backlog and history if not in index
        for path in [BACKLOG_DIR / f"{issue_id}.md", HISTORY_DIR / f"{issue_id}.md"]:
            if path.exists():
                return Issue.from_markdown(path.read_text())
        return None
    
    path = pathlib.Path(index[issue_id]["file"])
    if not path.exists():
        return None
    
    return Issue.from_markdown(path.read_text())

def generate_issue_id() -> str:
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    index = load_index()
    
    # Count issues for today
    today_count = 0
    for issue_id in index:
        if issue_id.startswith(f"ISSUE-{date_str}"):
            today_count += 1
            
    return f"ISSUE-{date_str}-{today_count + 1:03d}"
