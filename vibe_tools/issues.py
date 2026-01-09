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
class IssueBody:
    summary: str = ""
    reproduction_steps: str = ""
    expected_behavior: str = ""
    actual_behavior: str = ""
    evidence: str = ""
    acceptance_criteria: str = ""
    investigation_notes: str = ""
    solution_notes: str = ""

    def to_markdown(self) -> str:
        sections = []
        if self.summary:
            sections.append(f"## Summary\n{self.summary}")
        if self.reproduction_steps:
            sections.append(f"## Reproduction Steps\n{self.reproduction_steps}")
        if self.expected_behavior:
            sections.append(f"## Expected Behavior\n{self.expected_behavior}")
        if self.actual_behavior:
            sections.append(f"## Actual Behavior\n{self.actual_behavior}")
        if self.evidence:
            sections.append(f"## Evidence\n{self.evidence}")
        if self.acceptance_criteria:
            sections.append(f"## Acceptance Criteria\n{self.acceptance_criteria}")
        if self.investigation_notes:
            sections.append(f"## Investigation Notes\n{self.investigation_notes}")
        if self.solution_notes:
            sections.append(f"## Solution Notes\n{self.solution_notes}")
        return "\n\n".join(sections)

    @classmethod
    def from_markdown(cls, text: str) -> "IssueBody":
        sections = {
            "Summary": "",
            "Reproduction Steps": "",
            "Expected Behavior": "",
            "Actual Behavior": "",
            "Evidence": "",
            "Acceptance Criteria": "",
            "Investigation Notes": "",
            "Solution Notes": ""
        }
        
        current_section = None
        lines = text.splitlines()
        
        for line in lines:
            if line.startswith("## "):
                title = line[3:].strip()
                if title in sections:
                    current_section = title
                    continue
            
            if current_section:
                sections[current_section] = (sections[current_section] + "\n" + line).strip()
        
        return cls(
            summary=sections["Summary"],
            reproduction_steps=sections["Reproduction Steps"],
            expected_behavior=sections["Expected Behavior"],
            actual_behavior=sections["Actual Behavior"],
            evidence=sections["Evidence"],
            acceptance_criteria=sections["Acceptance Criteria"],
            investigation_notes=sections["Investigation Notes"],
            solution_notes=sections["Solution Notes"]
        )

@dataclass
class Issue:
    id: str
    title: str
    status: str  # backlog, in_progress, blocked, done
    severity: str  # low, medium, high, critical
    service: str
    created_at: str
    updated_at: str
    body: IssueBody
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
        yaml_content = yaml.dump(frontmatter, sort_keys=False, default_flow_style=False)
        body_text = self.body.to_markdown()
        content = f"---\n{yaml_content}---\n\n{body_text}"
        if self.comments:
            content = content.rstrip() + f"\n\n## External Comments (GitHub)\n{self.comments}"
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
        
        comments = ""
        body_text = rest
        if "## External Comments (GitHub)" in rest:
            body_text, comments = rest.split("## External Comments (GitHub)", 1)
            body_text = body_text.strip()
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
            body=IssueBody.from_markdown(body_text),
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
        "body": asdict(issue.body)
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def load_index() -> Dict[str, Any]:
    if not INDEX_FILE.exists():
        return {}
    try:
        content = INDEX_FILE.read_text()
        if not content.strip():
            return {}
        return json.loads(content)
    except json.JSONDecodeError:
        return {}

def save_index(index: Dict[str, Any]):
    META_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2))

def save_issue(issue: Issue):
    # Determine directory based on status
    target_dir = HISTORY_DIR if issue.status == "done" else BACKLOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = target_dir / f"{issue.id}.md"
    
    # If moving between directories, cleanup old ones
    old_backlog = BACKLOG_DIR / f"{issue.id}.md"
    old_history = HISTORY_DIR / f"{issue.id}.md"
    
    if issue.status == "done":
        if old_backlog.exists():
            old_backlog.unlink()
    else:
        if old_history.exists():
            old_history.unlink()

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
    if issue_id in index:
        path = pathlib.Path(index[issue_id]["file"])
        if path.exists():
            return Issue.from_markdown(path.read_text())
    
    # Fallback to direct file search
    for path in [BACKLOG_DIR / f"{issue_id}.md", HISTORY_DIR / f"{issue_id}.md"]:
        if path.exists():
            return Issue.from_markdown(path.read_text())
            
    return None

def generate_issue_id() -> str:
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    index = load_index()
    
    # Count issues for today across all directories
    today_count = 0
    prefix = f"ISSUE-{date_str}-"
    for issue_id in index:
        if issue_id.startswith(prefix):
            try:
                count = int(issue_id.replace(prefix, ""))
                if count > today_count:
                    today_count = count
            except ValueError:
                pass
            
    return f"{prefix}{today_count + 1:03d}"

STATUS_MAPPING = {
    "backlog": {
        "github_state": "open",
        "label": []
    },
    "in_progress": {
        "github_state": "open",
        "label": ["in-progress"]
    },
    "blocked": {
        "github_state": "open",
        "label": ["blocked"]
    },
    "done": {
        "github_state": "closed",
        "label": ["resolved"]
    }
}
