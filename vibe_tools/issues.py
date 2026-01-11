import datetime
import hashlib
import json
import pathlib
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import yaml

from vibe_tools.utils import safe_yaml_dump, safe_yaml_load


ISSUES_DIR = pathlib.Path("issues")
BACKLOG_DIR = ISSUES_DIR / "backlog"
HISTORY_DIR = ISSUES_DIR / "history"
FAILS_DIR = ISSUES_DIR / "fails"
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

        current_section = "Summary"  # Default to Summary
        lines = text.splitlines()

        # Check if it has any headers at all
        has_headers = any(line.startswith("## ") for line in lines)

        if not has_headers:
            return cls(summary=text.strip())

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
    summary: str
    created_at: str
    updated_at: str
    body: IssueBody
    github: Optional[GitHubInfo] = None
    sync: Optional[SyncInfo] = None
    comments: str = ""

    def __post_init__(self):
        if isinstance(self.body, str):
            self.body = IssueBody.from_markdown(self.body)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "severity": self.severity,
            "service": self.service,
            "summary": self.summary,
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
        yaml_content = safe_yaml_dump(frontmatter)
        body_text = self.body.to_markdown()
        # If body has summary, it might be redundant, but IssueBody.to_markdown handles it.
        # We'll keep them separate for now as per PRD.
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

        frontmatter = safe_yaml_load(parts[1])
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
            summary=frontmatter.get("summary", ""),
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
        "updated_at": issue.updated_at
    }
    if issue.github:
        index[issue.id]["github_number"] = issue.github.number
    save_index(index)

def load_index() -> Dict[str, Any]:
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text())
        except Exception:
            pass
    return {}

def save_index(index: Dict[str, Any]):
    META_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2))

def load_issue_by_id(issue_id: str) -> Optional[Issue]:
    # Search in known directories
    for directory in [BACKLOG_DIR, HISTORY_DIR]:
        path = directory / f"{issue_id}.md"
        if path.exists():
            return Issue.from_markdown(path.read_text())
    return None

def generate_issue_id() -> str:
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    
    # Count issues for today across all directories
    today_count = 0
    prefix = f"ISSUE-{date_str}-"
    
    for directory in [BACKLOG_DIR, HISTORY_DIR]:
        if directory.exists():
            for file in directory.glob(f"{prefix}*.md"):
                issue_id = file.stem
                try:
                    count = int(issue_id.replace(prefix, ""))
                    if count > today_count:
                        today_count = count
                except ValueError:
                    pass

    return f"{prefix}{today_count + 1:03d}"

def load_all_issues() -> List[Issue]:
    issues = []
    for directory in [BACKLOG_DIR, HISTORY_DIR]:
        if directory.exists():
            for file in directory.glob("*.md"):
                try:
                    issue = Issue.from_markdown(file.read_text())
                    issues.append(issue)
                except Exception:
                    continue

    # Sort by created_at, then by id for stability
    issues.sort(key=lambda x: (x.created_at, x.id))

    return issues

STATUS_MAPPING = {
    "backlog": {
        "github_state": "open",
        "label": ["issue"]
    },
    "in_progress": {
        "github_state": "open",
        "label": ["issue", "in-progress"]
    },
    "blocked": {
        "github_state": "open",
        "label": ["issue", "blocked"]
    },
    "done": {
        "github_state": "closed",
        "label": ["issue", "resolved"]
    }
}
