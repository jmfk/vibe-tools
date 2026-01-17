import pathlib
import re
import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


from vibe_tools.utils import safe_yaml_load, safe_yaml_dump


@dataclass
class PRD:
    id: str
    title: str
    type: str  # FEATURE or ISSUE
    status: str = "backlog"
    group: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: str = ""
    history: str = ""
    path: Optional[pathlib.Path] = None

    @property
    def discussion_id(self) -> Optional[str]:
        return self.metadata.get("discussion_id")

    @discussion_id.setter
    def discussion_id(self, value: str):
        self.metadata["discussion_id"] = value

    @property
    def issue_number(self) -> Optional[int]:
        return self.metadata.get("issue_number")

    @issue_number.setter
    def issue_number(self, value: int):
        self.metadata["issue_number"] = value

    @property
    def last_synced_at(self) -> Optional[str]:
        return self.metadata.get("last_synced_at")

    @last_synced_at.setter
    def last_synced_at(self, value: str):
        self.metadata["last_synced_at"] = value

    @property
    def sync_hash(self) -> Optional[str]:
        return self.metadata.get("sync_hash")

    @sync_hash.setter
    def sync_hash(self, value: str):
        self.metadata["sync_hash"] = value

    @property
    def severity(self) -> Optional[str]:
        return self.metadata.get("severity")

    @severity.setter
    def severity(self, value: str):
        self.metadata["severity"] = value

    @property
    def service(self) -> Optional[str]:
        return self.metadata.get("service")

    @service.setter
    def service(self, value: str):
        self.metadata["service"] = value

    @property
    def impl_code_ready(self) -> bool:
        return self.metadata.get("impl_code_ready", False)

    @impl_code_ready.setter
    def impl_code_ready(self, value: bool):
        self.metadata["impl_code_ready"] = value

    @property
    def impl_tests_passed(self) -> bool:
        return self.metadata.get("impl_tests_passed", False)

    @impl_tests_passed.setter
    def impl_tests_passed(self, value: bool):
        self.metadata["impl_tests_passed"] = value

    @property
    def impl_review_passed(self) -> bool:
        return self.metadata.get("impl_review_passed", False)

    @impl_review_passed.setter
    def impl_review_passed(self, value: bool):
        self.metadata["impl_review_passed"] = value

    def reset_progress(self):
        self.impl_code_ready = False
        self.impl_tests_passed = False
        self.impl_review_passed = False

    def get_hash(self) -> str:
        import hashlib

        return hashlib.sha256(self.content.encode()).hexdigest()

    @classmethod
    def from_markdown(cls, text: str, path: Optional[pathlib.Path] = None) -> "PRD":
        frontmatter = {}
        content = text
        history = ""

        # 1. Try legacy frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter = safe_yaml_load(parts[1]) or {}
                content = parts[2].strip()

        # 2. Try new bottom-of-file metadata
        if "<!-- vibe-id:" in text or "<summary>Metadata</summary>" in text:
            # Extract YAML from <details> block
            yaml_match = re.search(
                r"<details>\s*<summary>Metadata</summary>\s*```(?:yaml)?\s*(.*?)\s*```\s*</details>",
                text,
                re.DOTALL,
            )
            if yaml_match:
                bottom_yaml = yaml_match.group(1)
                new_fm = safe_yaml_load(bottom_yaml)
                if new_fm:
                    # Update frontmatter (prefer bottom metadata if both exist)
                    for k, v in new_fm.items():
                        frontmatter[k] = v

            # Extract vibe-id if present
            id_match = re.search(r"<!-- vibe-id: (.*?) -->", text)
            if id_match and ("id" not in frontmatter or not frontmatter["id"]):
                frontmatter["id"] = id_match.group(1).strip()

            # Clean content/history from the bottom metadata block
            content = re.sub(
                r"\n*---\s*<details>\s*<summary>Metadata</summary>.*?</details>\s*<!-- vibe-id: .*? -->",
                "",
                content,
                flags=re.DOTALL,
            ).strip()
            content = re.sub(
                r"\n*---\s*<details>\s*<summary>Metadata</summary>.*?</details>", "", content, flags=re.DOTALL
            ).strip()
            content = re.sub(
                r"\n*<!-- vibe-id: .*? -->", "", content, flags=re.DOTALL
            ).strip()

        # Extract history section if exists
        if "## Implementation History" in content:
            parts = content.split("## Implementation History", 1)
            content = parts[0].strip()
            history = parts[1].strip()

        # If it's an old Issue format, map the fields
        if "severity" in frontmatter or "service" in frontmatter:
            # This is likely a legacy Issue
            prd_id = frontmatter.get("id", "")
            title = frontmatter.get("title", "")
            prd_type = "ISSUE"
        else:
            prd_id = frontmatter.get("id", frontmatter.get("implementation_id", ""))
            title = frontmatter.get("title", "")
            prd_type = frontmatter.get("type", "FEATURE")

        if not prd_id and path:
            # Try to extract from filename
            match = re.search(r"(PRD-\d+|SRD-[a-z0-9_-]+)", path.name, re.IGNORECASE)
            if match:
                prd_id = match.group(1)
            else:
                # Fallback to stem for SRD if it starts with SRD-
                if path.name.startswith("SRD-"):
                    prd_id = path.stem

        if not title and content:
            # Try to find first H1
            match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if match:
                title = match.group(1).strip()

        return cls(
            id=prd_id,
            title=title,
            type=prd_type,
            status=frontmatter.get("status", "backlog"),
            group=frontmatter.get("group"),
            depends_on=frontmatter.get("depends_on") or [],
            created_at=frontmatter.get(
                "created_at", datetime.datetime.now().isoformat()
            ),
            updated_at=frontmatter.get(
                "updated_at", datetime.datetime.now().isoformat()
            ),
            metadata=frontmatter,
            content=content,
            history=history,
            path=path,
        )

    def to_markdown(self) -> str:
        data = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "group": self.group,
            "depends_on": self.depends_on,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        # Merge with extra metadata but prioritize known fields
        for k, v in self.metadata.items():
            if k not in data:
                data[k] = v

        frontmatter = safe_yaml_dump(data)

        # New format: No frontmatter at the top. Metadata at the bottom.
        text = ""
        if not self.content.startswith("# "):
            text += f"# {self.title}\n\n"
        text += self.content.strip()

        if self.history:
            text += f"\n\n## Implementation History\n\n{self.history.strip()}"

        # Append metadata at the end
        text += f"\n\n---\n<details>\n<summary>Metadata</summary>\n\n```yaml\n{frontmatter.strip()}\n```\n</details>\n"
        text += f"\n<!-- vibe-id: {self.id} -->\n"

        return text

    def save(self, path: Optional[pathlib.Path] = None):
        target_path = path or self.path
        if not target_path:
            raise ValueError("No path provided to save PRD")

        self.updated_at = datetime.datetime.now().isoformat()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(self.to_markdown())

    def append_history(self, note: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"### {timestamp}\n{note}\n"
        if self.history:
            self.history = self.history.strip() + "\n\n" + entry
        else:
            self.history = entry

    def to_yaml_data(self) -> Dict[str, Any]:
        """Convert PRD to structured data for normalization/implementation."""
        # This will be used by the in-memory normalization step
        return {
            "TITLE": self.title,
            "ID": self.id,
            "TYPE": self.type,
            "DEPENDS_ON": self.depends_on,
            "METADATA": self.metadata,
            "CONTENT": self.content,
        }


def load_prd(path: pathlib.Path) -> PRD:
    if not path.exists():
        raise FileNotFoundError(f"PRD file not found: {path}")
    return PRD.from_markdown(path.read_text(), path=path)


def generate_prd_id(base_dir: pathlib.Path) -> str:
    """Generates a new PRD-NNN ID."""
    max_id = 0
    # Scan all directories under product/
    for f in base_dir.rglob("PRD-*.md"):
        match = re.search(r"PRD-(\d+)", f.name)
        if match:
            max_id = max(max_id, int(match.group(1)))

    return f"PRD-{max_id + 1:03d}"


# --- Compatibility Shims for Legacy Commands ---


class PRDMetadata:
    """Legacy PRDMetadata shim."""

    def __init__(self, path: pathlib.Path):
        self.path = path
        self.prd = load_prd(path) if path.exists() else None
        self.sync_info = self.prd.metadata if self.prd else {}
        self.content = self.prd.content if self.prd else ""

    @property
    def title(self):
        return self.prd.title if self.prd else self.path.stem

    @property
    def github_issue_number(self):
        return self.sync_info.get("issue_number")

    @github_issue_number.setter
    def github_issue_number(self, val):
        self.sync_info["issue_number"] = val

    @property
    def github_discussion_url(self):
        return self.sync_info.get("discussion_url")

    @github_discussion_url.setter
    def github_discussion_url(self, val):
        self.sync_info["discussion_url"] = val

    @property
    def last_synced_at(self):
        return self.sync_info.get("last_synced_at")

    @last_synced_at.setter
    def last_synced_at(self, val):
        self.sync_info["last_synced_at"] = val

    @property
    def sync_hash(self):
        return self.sync_info.get("sync_hash")

    @sync_hash.setter
    def sync_hash(self, val):
        self.sync_info["sync_hash"] = val

    def save(self):
        if self.prd:
            self.prd.metadata = self.sync_info
            self.prd.save()

    def to_markdown(self):
        return self.prd.to_markdown() if self.prd else ""

    def get_hash(self):
        import hashlib

        return hashlib.sha256(self.content.encode()).hexdigest()


def get_prd_metadata(path: pathlib.Path) -> PRDMetadata:
    return PRDMetadata(path)
