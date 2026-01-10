import pathlib
import yaml
import re
from typing import Optional, Dict, Any

class PRDMetadata:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.is_yaml = path.suffix.lower() in ('.yaml', '.yml')
        self.data: Dict[str, Any] = {}
        self.content: str = ""
        self.sync_info: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            return

        raw_content = self.path.read_text()
        if self.is_yaml:
            try:
                self.data = yaml.safe_load(raw_content) or {}
                self.sync_info = self.data.get('_vibe_sync', {})
            except yaml.YAMLError:
                self.data = {}
        else:
            # Markdown with potential frontmatter
            if raw_content.startswith('---'):
                parts = raw_content.split('---', 2)
                if len(parts) >= 3:
                    try:
                        self.sync_info = yaml.safe_load(parts[1]) or {}
                        self.content = parts[2].strip()
                    except yaml.YAMLError:
                        self.content = raw_content.strip()
                else:
                    self.content = raw_content.strip()
            else:
                self.content = raw_content.strip()

    def save(self):
        if self.is_yaml:
            if self.sync_info:
                self.data['_vibe_sync'] = self.sync_info
            elif '_vibe_sync' in self.data:
                del self.data['_vibe_sync']
            
            content = yaml.dump(self.data, sort_keys=False, default_flow_style=False)
            self.path.write_text(content)
        else:
            if self.sync_info:
                frontmatter = yaml.dump(self.sync_info, sort_keys=False, default_flow_style=False)
                new_content = f"---\n{frontmatter}---\n\n{self.content}"
            else:
                new_content = self.content
            
            self.path.write_text(new_content)

    @property
    def github_discussion_url(self) -> Optional[str]:
        return self.sync_info.get('discussion_url')

    @github_discussion_url.setter
    def github_discussion_url(self, url: str):
        self.sync_info['discussion_url'] = url

    @property
    def github_issue_number(self) -> Optional[int]:
        return self.sync_info.get('issue_number')

    @github_issue_number.setter
    def github_issue_number(self, number: int):
        self.sync_info['issue_number'] = number

    @property
    def title(self) -> str:
        # Try to find a title in the PRD
        if self.is_yaml:
            # Maybe it's in a key like 'title' or 'NAME'
            for key in ['title', 'name', 'TITLE', 'NAME']:
                if key in self.data:
                    return str(self.data[key])
            # Fallback to stem
            return self.path.stem.replace('prd_', '').replace('_', ' ').title()
        else:
            # Try to find first H1
            match = re.search(r'^#\s+(.+)$', self.content, re.MULTILINE)
            if match:
                return match.group(1).strip()
            return self.path.stem.title()

    def to_markdown(self) -> str:
        if not self.is_yaml:
            return self.content

        # Convert YAML to a readable Markdown format
        lines = []
        lines.append(f"# {self.title}")
        lines.append("")

        for key, value in self.data.items():
            if key == '_vibe_sync':
                continue
            
            lines.append(f"## {key.replace('_', ' ').title()}")
            if isinstance(value, list):
                for item in value:
                    lines.append(f"- {item}")
            elif isinstance(value, dict):
                for k, v in value.items():
                    lines.append(f"### {k.replace('_', ' ').title()}")
                    if isinstance(v, list):
                        for item in v:
                            lines.append(f"  - {item}")
                    else:
                        lines.append(f"  {v}")
            else:
                lines.append(str(value))
            lines.append("")

        return "\n".join(lines).strip()

    def get_hash(self) -> str:
        import hashlib
        import json
        # Calculate hash of content only (excluding sync info)
        content_to_hash = self.content
        if self.is_yaml:
            # For YAML, hash the data without the sync info key
            data_copy = self.data.copy()
            if '_vibe_sync' in data_copy:
                del data_copy['_vibe_sync']
            content_to_hash = json.dumps(data_copy, sort_keys=True)
        
        return hashlib.sha256(content_to_hash.encode()).hexdigest()

def get_prd_metadata(path: pathlib.Path) -> PRDMetadata:
    return PRDMetadata(path)
