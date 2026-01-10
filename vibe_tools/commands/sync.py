import click
import datetime
import json
import os
from typing import List, Optional
from vibe_tools.issues import (
    Issue, IssueBody, GitHubInfo, SyncInfo, load_index, save_issue, 
    load_issue_by_id, get_issue_hash, generate_issue_id,
    BACKLOG_DIR as ISSUES_BACKLOG_DIR, HISTORY_DIR as ISSUES_HISTORY_DIR, STATUS_MAPPING
)
from vibe_tools.utils import (
    PLANNING_INBOX_DIR, PLANNING_BACKLOG_DIR, PLANNING_HISTORY_DIR, PLANNING_REJECTED_DIR, 
    PRD_DIR, load_project_state, run_command, logger, switch_to_main, get_main_branch
)
from vibe_tools.prds import get_prd_metadata

def get_github_repo_info():
    """Returns (owner, name, repo_id)"""
    repo = get_github_repo()
    if not repo:
        return None, None, None
    
    parts = repo.split("/")
    if len(parts) != 2:
        return None, None, None
    
    owner, name = parts
    
    stdout, code = run_command(["gh", "api", "graphql", "-f", f"query=query {{ repository(owner: \"{owner}\", name: \"{name}\") {{ id }} }}"], check=False)
    if code != 0:
        return owner, name, None
    
    try:
        data = json.loads(stdout)
        repo_id = data["data"]["repository"]["id"]
        return owner, name, repo_id
    except (json.JSONDecodeError, KeyError):
        return owner, name, None

def get_label_id(owner, name, label_name):
    query = """
    query($owner:String!, $name:String!, $labelName:String!) {
      repository(owner:$owner, name:$name) {
        label(name:$labelName) { id }
      }
    }
    """
    cmd = [
        "gh", "api", "graphql",
        "-f", f"query={query}",
        "-f", f"owner={owner}",
        "-f", f"name={name}",
        "-f", f"labelName={label_name}"
    ]
    stdout, code = run_command(cmd, check=False)
    if code == 0:
        try:
            data = json.loads(stdout)
            label = data.get("data", {}).get("repository", {}).get("label")
            if label:
                return label["id"]
        except (json.JSONDecodeError, KeyError):
            pass
    return None

def get_last_sync_info(branch_name: str):
    """Returns (hash, timestamp) of the last 'vibe: sync' commit."""
    # %H for hash, %aI for author date in ISO 8601 format
    stdout, _ = run_command(["git", "log", branch_name, "--grep=vibe: sync", "-n", "1", "--format=%H %aI"], check=False)
    parts = stdout.strip().split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None

def get_files_changed_since(commit_hash: str) -> List[str]:
    """Returns a list of files changed since the given commit hash."""
    # --name-status gives us M, A, D, R etc.
    stdout, _ = run_command(["git", "diff", "--name-status", commit_hash, "HEAD"], check=False)
    changed_files = []
    for line in stdout.strip().splitlines():
        if not line: continue
        parts = line.split()
        if not parts: continue
        status = parts[0]
        if status.startswith('R'): # Renamed
            if len(parts) >= 3:
                changed_files.append(parts[1])
                changed_files.append(parts[2])
        else:
            if len(parts) >= 2:
                changed_files.append(parts[1])
    
    # Also include untracked files
    stdout, _ = run_command(["git", "ls-files", "--others", "--exclude-standard"], check=False)
    if stdout.strip():
        changed_files.extend(stdout.strip().splitlines())
        
    return list(set(changed_files))

def fetch_github_discussions(owner, name):
    query = """
    query($owner:String!, $name:String!) {
      repository(owner:$owner, name:$name) {
        discussions(first:100) {
          nodes {
            id
            number
            title
            body
            updatedAt
            category { name }
            labels(first:10) { nodes { name } }
          }
        }
      }
    }
    """
    cmd = [
        "gh", "api", "graphql",
        "-f", f"query={query}",
        "-f", f"owner={owner}",
        "-f", f"name={name}"
    ]
    stdout, code = run_command(cmd, check=False)
    if code == 0:
        try:
            return json.loads(stdout)["data"]["repository"]["discussions"]["nodes"]
        except (json.JSONDecodeError, KeyError):
            pass
    return []

def add_discussion_labels(discussion_id, label_ids):
    if not label_ids:
        return
    query = """
    mutation($discussionId:ID!, $labelIds:[ID!]!) {
      addLabelsToLabelable(input:{labelableId:$discussionId, labelIds:$labelIds}) {
        clientMutationId
      }
    }
    """
    cmd = [
        "gh", "api", "graphql",
        "-f", f"query={query}",
        "-f", f"discussionId={discussion_id}",
    ]
    for lid in label_ids:
        cmd.extend(["-f", f"labelIds[]={lid}"])
    run_command(cmd, check=False)

def remove_discussion_labels(discussion_id, label_ids):
    if not label_ids:
        return
    query = """
    mutation($discussionId:ID!, $labelIds:[ID!]!) {
      removeLabelsFromLabelable(input:{labelableId:$discussionId, labelIds:$labelIds}) {
        clientMutationId
      }
    }
    """
    cmd = [
        "gh", "api", "graphql",
        "-f", f"query={query}",
        "-f", f"discussionId={discussion_id}",
    ]
    for lid in label_ids:
        cmd.extend(["-f", f"labelIds[]={lid}"])
    run_command(cmd, check=False)

def get_discussion_category_id(owner, name, category_name="Ideas"):
    stdout, code = run_command(["gh", "api", "graphql", "-f", f"query=query {{ repository(owner: \"{owner}\", name: \"{name}\") {{ discussionCategories(first: 10) {{ nodes {{ id name }} }} }} }}"], check=False)
    if code != 0:
        return None
    
    try:
        data = json.loads(stdout)
        for node in data["data"]["repository"]["discussionCategories"]["nodes"]:
            if node["name"] == category_name:
                return node["id"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None

def sync_prd_discussions(repo_owner, repo_name, repo_id, dry_run=False, relevant_files=None):
    category_id = get_discussion_category_id(repo_owner, repo_name)
    if not category_id:
        logger.warning("Could not find 'Ideas' discussion category. Skipping discussion sync.")
        return

    from vibe_tools.utils import PRODUCT_DIR
    
    # 1. Fetch current GitHub discussions
    gh_discussions = fetch_github_discussions(repo_owner, repo_name)
    gh_by_title = {d["title"]: d for d in gh_discussions}
    gh_by_id = {d["id"]: d for d in gh_discussions}
    
    # Define labels we manage
    vibe_labels = ["inbox", "backlog", "history", "rejected", "system"]
    
    # Define directories and their labels
    sync_dirs = {
        PLANNING_INBOX_DIR: "inbox",
        PLANNING_BACKLOG_DIR: "backlog",
        PLANNING_HISTORY_DIR: "history",
        PLANNING_REJECTED_DIR: "rejected",
    }

    # Also handle system files in product root
    system_files = ["architecture.md", "infrastructure.md", "cicd.md", "testing.md", "build.md"]
    
    # Ensure all labels exist
    repo = f"{repo_owner}/{repo_name}"
    for label in vibe_labels:
        ensure_github_label(repo, label)
    
    # Now get label IDs after ensuring they exist
    label_ids = {l: get_label_id(repo_owner, repo_name, l) for l in vibe_labels}

    # 2. Sync directories
    for directory, label in sync_dirs.items():
        if not directory.exists():
            continue
        
        is_inbox = label == "inbox"
        is_backlog = label == "backlog"
        
        for prd_path in directory.glob("*.md"):
            if relevant_files is not None:
                if str(prd_path) not in relevant_files and not is_inbox and not is_backlog:
                    continue

            meta = get_prd_metadata(prd_path)
            title = f"[PRD] {meta.title}"
            body = meta.to_markdown()
            
            gh_disc = None
            if meta.sync_info.get('discussion_id'):
                gh_disc = gh_by_id.get(meta.sync_info['discussion_id'])
            
            if not gh_disc:
                gh_disc = gh_by_title.get(title)
            
            if not gh_disc:
                # Create discussion
                if dry_run:
                    logger.info(f"[DRY RUN] Would create GitHub Discussion for {prd_path.name} with label '{label}'")
                    continue
                
                cmd = [
                    "gh", "api", "graphql",
                    "-f", f"query=mutation($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {{ createDiscussion(input: {{ repositoryId: $repoId, categoryId: $categoryId, title: $title, body: $body }}) {{ discussion {{ id url }} }} }}",
                    "-f", f"repoId={repo_id}",
                    "-f", f"categoryId={category_id}",
                    "-f", f"title={title}",
                    "-f", f"body={body}"
                ]
                stdout, code = run_command(cmd, check=False)
                if code == 0:
                    try:
                        data = json.loads(stdout)
                        disc = data["data"]["createDiscussion"]["discussion"]
                        meta.sync_info['discussion_id'] = disc["id"]
                        meta.github_discussion_url = disc["url"]
                        meta.last_synced_at = datetime.datetime.now().isoformat()
                        meta.sync_hash = meta.get_hash()
                        meta.save()
                        
                        # Add to local cache to prevent duplicates in same run
                        gh_by_id[disc["id"]] = disc
                        gh_by_title[title] = disc
                        
                        if label_ids[label]:
                            add_discussion_labels(disc["id"], [label_ids[label]])
                            
                        logger.info(f"Created GitHub Discussion for {prd_path.name} with label '{label}'")
                    except (json.JSONDecodeError, KeyError):
                        logger.error(f"Failed to parse discussion creation response for {prd_path.name}")
                else:
                    logger.error(f"Failed to create GitHub Discussion for {prd_path.name}: {stdout}")
            else:
                # Sync existing discussion
                gh_updated_at = gh_disc["updatedAt"]
                gh_body = gh_disc["body"]
                
                # Update metadata if not present
                if not meta.sync_info.get('discussion_id'):
                    meta.sync_info['discussion_id'] = gh_disc["id"]
                    if 'discussion_url' not in meta.sync_info:
                         meta.github_discussion_url = gh_disc.get("url") or f"https://github.com/{repo_owner}/{repo_name}/discussions/{gh_disc['number']}"
                    meta.save()

                # Check for bidirectional sync for inbox
                if is_inbox:
                    # Compare updatedAt
                    local_mtime = datetime.datetime.fromtimestamp(prd_path.stat().st_mtime, tz=datetime.timezone.utc)
                    gh_time = datetime.datetime.fromisoformat(gh_updated_at.replace("Z", "+00:00"))
                    
                    if gh_time > local_mtime and gh_body != body:
                        # GitHub is newer, pull
                        if dry_run:
                            logger.info(f"[DRY RUN] Would pull GitHub Discussion updates for {prd_path.name}")
                        else:
                            meta.content = gh_body
                            meta.last_synced_at = gh_updated_at
                            meta.sync_hash = meta.get_hash()
                            meta.save()
                            logger.info(f"Pulled updates for {prd_path.name} from GitHub")
                        continue # Skip push
                
                # One-way push (vibe-tools -> GitHub) or local is newer in bidirectional
                if gh_body != body:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would update GitHub Discussion for {prd_path.name}")
                        continue
                        
                    cmd = [
                        "gh", "api", "graphql",
                        "-f", f"query=mutation($id: ID!, $title: String!, $body: String!) {{ updateDiscussion(input: {{ discussionId: $id, title: $title, body: $body }}) {{ discussion {{ id url }} }} }}",
                        "-f", f"id={gh_disc['id']}",
                        "-f", f"title={title}",
                        "-f", f"body={body}"
                    ]
                    stdout, code = run_command(cmd, check=False)
                    if code == 0:
                        meta.last_synced_at = datetime.datetime.now().isoformat()
                        meta.sync_hash = meta.get_hash()
                        meta.save()
                        logger.info(f"Updated GitHub Discussion for {prd_path.name}")
                    else:
                        logger.error(f"Failed to update GitHub Discussion for {prd_path.name}: {stdout}")
                
                # Manage labels: ensure correct one is there, remove others
                gh_labels = [l["name"] for l in gh_disc["labels"]["nodes"]]
                if label not in gh_labels:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would add label '{label}' to GitHub Discussion {gh_disc['number']}")
                    elif label_ids[label]:
                        add_discussion_labels(gh_disc["id"], [label_ids[label]])
                        logger.info(f"Added label '{label}' to GitHub Discussion {gh_disc['number']}")
                
                # Remove other status labels
                to_remove_labels = [l for l in vibe_labels if l in gh_labels and l != label]
                if to_remove_labels:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would remove labels {to_remove_labels} from GitHub Discussion {gh_disc['number']}")
                    else:
                        to_remove_ids = [label_ids[l] for l in to_remove_labels if label_ids[l]]
                        if to_remove_ids:
                            remove_discussion_labels(gh_disc["id"], to_remove_ids)
                            logger.info(f"Removed old status labels from GitHub Discussion {gh_disc['number']}")

    # 3. Handle System files
    for filename in system_files:
        prd_path = PRODUCT_DIR / filename
        if not prd_path.exists():
            continue
            
        if relevant_files is not None:
            if str(prd_path) not in relevant_files:
                continue

        meta = get_prd_metadata(prd_path)
        title = f"[SYSTEM] {meta.title}"
        body = meta.to_markdown()
        label = "system"
        
        gh_disc = None
        if meta.sync_info.get('discussion_id'):
            gh_disc = gh_by_id.get(meta.sync_info['discussion_id'])
        
        if not gh_disc:
            gh_disc = gh_by_title.get(title)
        
        if not gh_disc:
            if dry_run:
                logger.info(f"[DRY RUN] Would create GitHub Discussion for system spec {filename}")
                continue
            
            # Create
            cmd = [
                "gh", "api", "graphql",
                "-f", f"query=mutation($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {{ createDiscussion(input: {{ repositoryId: $repoId, categoryId: $categoryId, title: $title, body: $body }}) {{ discussion {{ id url }} }} }}",
                "-f", f"repoId={repo_id}",
                "-f", f"categoryId={category_id}",
                "-f", f"title={title}",
                "-f", f"body={body}"
            ]
            stdout, code = run_command(cmd, check=False)
            if code == 0:
                data = json.loads(stdout)
                disc = data["data"]["createDiscussion"]["discussion"]
                
                meta.sync_info['discussion_id'] = disc["id"]
                meta.github_discussion_url = disc["url"]
                meta.last_synced_at = datetime.datetime.now().isoformat()
                meta.sync_hash = meta.get_hash()
                meta.save()

                # Add to local cache
                gh_by_id[disc["id"]] = disc
                gh_by_title[title] = disc

                if label_ids[label]:
                    add_discussion_labels(disc["id"], [label_ids[label]])
                logger.info(f"Created GitHub Discussion for system spec {filename}")
        else:
            # Update metadata if not present
            if not meta.sync_info.get('discussion_id'):
                meta.sync_info['discussion_id'] = gh_disc["id"]
                if 'discussion_url' not in meta.sync_info:
                    meta.github_discussion_url = gh_disc.get("url") or f"https://github.com/{repo_owner}/{repo_name}/discussions/{gh_disc['number']}"
                meta.save()

            # Update (One-way)
            if gh_disc["body"] != body:
                if dry_run:
                    logger.info(f"[DRY RUN] Would update GitHub Discussion for system spec {filename}")
                    continue
                    
                cmd = [
                    "gh", "api", "graphql",
                    "-f", f"query=mutation($id: ID!, $title: String!, $body: String!) {{ updateDiscussion(input: {{ discussionId: $id, title: $title, body: $body }}) {{ discussion {{ id url }} }} }}",
                    "-f", f"id={gh_disc['id']}",
                    "-f", f"title={title}",
                    "-f", f"body={body}"
                ]
                stdout, code = run_command(cmd, check=False)
                if code == 0:
                    meta.last_synced_at = datetime.datetime.now().isoformat()
                    meta.sync_hash = meta.get_hash()
                    meta.save()
                    logger.info(f"Updated GitHub Discussion for system spec {filename}")
            
            # Ensure label
            gh_labels = [l["name"] for l in gh_disc["labels"]["nodes"]]
            if label not in gh_labels:
                if dry_run:
                    logger.info(f"[DRY RUN] Would add label '{label}' to GitHub Discussion {gh_disc['number']}")
                elif label_ids[label]:
                    add_discussion_labels(gh_disc["id"], [label_ids[label]])
                    logger.info(f"Added label '{label}' to GitHub Discussion {gh_disc['number']}")
            
            # Remove other status labels
            to_remove_labels = [l for l in vibe_labels if l in gh_labels and l != label]
            if to_remove_labels:
                if dry_run:
                    logger.info(f"[DRY RUN] Would remove labels {to_remove_labels} from GitHub Discussion {gh_disc['number']}")
                else:
                    to_remove_ids = [label_ids[l] for l in to_remove_labels if label_ids[l]]
                    if to_remove_ids:
                        remove_discussion_labels(gh_disc["id"], to_remove_ids)
                        logger.info(f"Removed old status labels from GitHub Discussion {gh_disc['number']}")

    # 4. Pull new inbox discussions from GitHub
    if not dry_run:
        for gh_disc in gh_discussions:
            gh_labels = [l["name"] for l in gh_disc["labels"]["nodes"]]
            if "inbox" in gh_labels and gh_disc["title"] not in [f"[PRD] {get_prd_metadata(p).title}" for p in PLANNING_INBOX_DIR.glob("*.md")]:
                # New discussion in inbox category, pull it
                title = gh_disc["title"]
                if title.startswith("[PRD] "):
                    clean_title = title[6:]
                    filename = clean_title.lower().replace(" ", "-") + ".md"
                    # Avoid duplicates by checking all directories
                    exists = False
                    for d in sync_dirs:
                        if (d / filename).exists():
                            exists = True
                            break
                    if not exists:
                        prd_path = PLANNING_INBOX_DIR / filename
                        meta = get_prd_metadata(prd_path)
                        meta.content = gh_disc["body"]
                        meta.sync_info['discussion_id'] = gh_disc["id"]
                        meta.github_discussion_url = f"https://github.com/{repo_owner}/{repo_name}/discussions/{gh_disc['number']}"
                        meta.last_synced_at = gh_disc["updatedAt"]
                        meta.sync_hash = meta.get_hash()
                        meta.save()
                        logger.info(f"Pulled new GitHub Discussion '{title}' into inbox")

def sync_prd_issues(repo_owner, repo_name, repo_id, dry_run=False, relevant_files=None):
    from vibe_tools.utils import PRD_DIR, load_project_state, REJECTED_DIR
    state = load_project_state()
    started_prds = state.get("started_prds", [])
    
    backlog_dir = PRD_DIR / "backlog"
    history_dir = PRD_DIR / "history"
    rejected_dir = REJECTED_DIR

    repo = f"{repo_owner}/{repo_name}"
    
    # System files to ignore for issues
    system_files = ["architecture.yaml", "infrastructure.yaml", "cicd.yaml", "testing.yaml", "build.yaml"]

    if not dry_run:
        # Ensure 'prd' label exists
        ensure_github_label(repo, "prd")

    for directory in [backlog_dir, history_dir, rejected_dir]:
        if not directory.exists():
            continue
        
        is_history = directory.name == "history"
        is_backlog = directory.name == "backlog"
        
        for prd_path in directory.glob("*.yaml"):
            if prd_path.name in system_files:
                continue
            
            if relevant_files is not None:
                if str(prd_path) not in relevant_files and not is_backlog:
                    continue

            meta = get_prd_metadata(prd_path)
            title = f"[PRD] {meta.title}"
            body = meta.to_markdown()
            
            if dry_run:
                logger.info(f"[DRY RUN] Would sync GitHub Issue for normalized PRD {prd_path.name}")
                continue

            issue_number = meta.github_issue_number
            
            # Determine labels
            labels = ["prd"]
            prd_id = prd_path.stem
            if prd_id.startswith("prd_"):
                prd_id = prd_id[4:]
                
            if prd_id in started_prds:
                labels.append("in-progress")
            
            # Ensure labels exist
            for label in labels:
                ensure_github_label(repo, label)

            if not issue_number:
                # Create issue
                cmd = [
                    "gh", "issue", "create",
                    "--repo", repo,
                    "--title", title,
                    "--body", body
                ]
                for label in labels:
                    cmd.extend(["--label", label])
                
                stdout, code, stderr = _run_command_with_stderr(cmd)
                if code == 0:
                    try:
                        url = stdout.strip()
                        number = int(url.split("/")[-1])
                        meta.github_issue_number = number
                        meta.save()
                        logger.info(f"Created GitHub Issue for {prd_path.name}")
                        
                        if is_history:
                            run_command(["gh", "issue", "close", str(number), "--repo", repo], check=False)
                    except (ValueError, IndexError):
                        logger.error(f"Failed to parse issue URL for {prd_path.name}: {url}")
                else:
                    logger.error(f"Failed to create GitHub Issue for {prd_path.name}: {stderr or stdout}")
            else:
                # Update issue (One-way vibe-tools -> GitHub)
                cmd = [
                    "gh", "issue", "edit", str(issue_number),
                    "--repo", repo,
                    "--title", title,
                    "--body", body
                ]
                for label in labels:
                    cmd.extend(["--add-label", label])
                
                stdout, code, stderr = _run_command_with_stderr(cmd)
                if code == 0:
                    if is_history:
                        run_command(["gh", "issue", "close", str(issue_number), "--repo", repo], check=False)
                    else:
                        run_command(["gh", "issue", "reopen", str(issue_number), "--repo", repo], check=False)
                    logger.info(f"Updated GitHub Issue for {prd_path.name}")
                else:
                    logger.error(f"Failed to update GitHub Issue {issue_number} for {prd_path.name}: {stderr or stdout}")

GITHUB_TO_LOCAL_STATUS = {
    "OPEN": "backlog",
    "CLOSED": "done",
}

def get_github_repo():
    stdout, code = run_command(["git", "remote", "get-url", "origin"], check=False)
    if code != 0:
        return None
    url = stdout.strip()
    if not url:
        return None
        
    if "github.com" not in url:
        return None
    
    # Handle both ssh and https
    if url.startswith("git@github.com:"):
        repo = url.replace("git@github.com:", "").replace(".git", "")
    elif url.startswith("https://github.com/"):
        repo = url.replace("https://github.com/", "").replace(".git", "")
    else:
        # Fallback for other formats
        parts = url.split("github.com/")
        if len(parts) > 1:
            repo = parts[1].replace(".git", "")
        else:
            return None
    return repo

def fetch_gh_issue_comments(gh_number: int, repo: str) -> str:
    comments_stdout, _ = run_command(["gh", "issue", "view", str(gh_number), "--repo", repo, "--json", "comments"], check=False)
    comments_body = ""
    if comments_stdout:
        try:
            comments_data = json.loads(comments_stdout)
            if comments_data.get("comments"):
                for comment in comments_data["comments"]:
                    author = comment["author"]["login"]
                    body = comment["body"]
                    created = comment["createdAt"]
                    comments_body += f"\n### {author} at {created}\n{body}\n"
        except json.JSONDecodeError:
            pass
    return comments_body

def pull_github_issues(repo: str, open_only: bool = True, since: Optional[str] = None, label: Optional[str] = None):
    # Default to fetching 'issue' labeled items if no label specified
    target_label = label or "issue"
    cmd = ["gh", "issue", "list", "--repo", repo, "--label", target_label, "--json", "number,title,body,state,labels,updatedAt,url"]
    if not open_only:
        cmd.append("--state")
        cmd.append("all")
    if since:
        cmd.append("--since")
        cmd.append(since)
    
    stdout, code = run_command(cmd, check=False)
    if code != 0:
        logger.error(f"Failed to fetch GitHub issues: {stdout}")
        return

    gh_issues = json.loads(stdout)
    index = load_index()
    
    # Map gh_number to local_id
    gh_to_local = {v["github_number"]: k for k, v in index.items() if v.get("github_number")}

    for gh_issue in gh_issues:
        gh_number = gh_issue["number"]
        gh_updated_at = gh_issue["updatedAt"]
        
        if gh_number in gh_to_local:
            local_id = gh_to_local[gh_number]
            issue = load_issue_by_id(local_id)
            if not issue:
                continue
            
            current_hash = get_issue_hash(issue)
            
            # Conflict detection
            is_local_changed = issue.sync and current_hash != issue.sync.sync_hash
            is_remote_changed = issue.sync and gh_updated_at > issue.sync.last_synced_at

            if is_local_changed and is_remote_changed:
                logger.warning(f"Conflict detected for {local_id} (GH#{gh_number}). Marking as blocked.")
                issue.status = "blocked"
                conflict_note = f"- CONFLICT at {datetime.datetime.now().isoformat()}: Remote changes detected on GitHub at {gh_updated_at}. Local changes also exist. Please resolve manually."
                if conflict_note not in issue.body.investigation_notes:
                    issue.body.investigation_notes = (issue.body.investigation_notes + "\n" + conflict_note).strip()
                save_issue(issue)
                continue

            if is_remote_changed and not is_local_changed:
                # Local hasn't changed, safe to update from GH
                issue.title = gh_issue["title"]
                issue.comments = fetch_gh_issue_comments(gh_number, repo)
                issue.body = IssueBody.from_markdown(gh_issue["body"])
                issue.updated_at = gh_updated_at
                
                # Map status
                if gh_issue["state"] == "CLOSED":
                    issue.status = "done"
                else:
                    labels = [l["name"] for l in gh_issue["labels"]]
                    if "in-progress" in labels:
                        issue.status = "in_progress"
                    elif "blocked" in labels:
                        issue.status = "blocked"
                    else:
                        issue.status = "backlog"
                
                issue.sync = SyncInfo(
                    last_synced_at=gh_updated_at,
                    sync_hash=get_issue_hash(issue)
                )
                save_issue(issue)
                logger.info(f"Updated {local_id} from GitHub issue {gh_number}")
        else:
            # Create new local issue
            local_id = generate_issue_id()
            status = GITHUB_TO_LOCAL_STATUS.get(gh_issue["state"], "backlog")
            
            labels = [l["name"] for l in gh_issue["labels"]]
            if status == "backlog":
                if "in-progress" in labels:
                    status = "in_progress"
                elif "blocked" in labels:
                    status = "blocked"

            issue = Issue(
                id=local_id,
                title=gh_issue["title"],
                status=status,
                severity="medium",
                service="unknown",
                created_at=gh_issue["updatedAt"],
                updated_at=gh_issue["updatedAt"],
                body=IssueBody.from_markdown(gh_issue["body"]),
                github=GitHubInfo(
                    repo=repo,
                    number=gh_number,
                    url=gh_issue["url"]
                ),
                sync=SyncInfo(
                    last_synced_at=gh_issue["updatedAt"],
                    sync_hash=""
                )
            )
            issue.comments = fetch_gh_issue_comments(gh_number, repo)
            issue.sync.sync_hash = get_issue_hash(issue)
            save_issue(issue)
            logger.info(f"Pulled new issue {gh_number} as {local_id}")

def _run_command_with_stderr(cmd):
    import subprocess
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode, result.stderr.strip()

def ensure_github_label(repo: str, label: str):
    """Ensures a label exists on GitHub, creating it if necessary."""
    _, code, _ = _run_command_with_stderr(["gh", "label", "view", label, "--repo", repo])
    if code != 0:
        logger.info(f"Creating missing label '{label}' on GitHub...")
        # Use a default color (blue-ish)
        run_command(["gh", "label", "create", label, "--repo", repo, "--color", "0075ca"], check=False)

def push_local_issues(repo: str, relevant_files=None):
    index = load_index()
    for local_id in index:
        issue_path = index[local_id]["file"]
        if relevant_files is not None:
            # Issues in backlog are always relevant for status updates
            is_backlog = "issues/backlog" in issue_path
            if issue_path not in relevant_files and not is_backlog:
                continue

        issue = load_issue_by_id(local_id)
        if not issue:
            continue
        
        current_hash = get_issue_hash(issue)
        if issue.sync and issue.sync.sync_hash == current_hash:
            continue
        
        if issue.status == "blocked":
            logger.info(f"Skipping blocked issue {local_id}")
            continue

        mapping = STATUS_MAPPING.get(issue.status, STATUS_MAPPING["backlog"])
        
        # Ensure labels exist before trying to use them
        for label in mapping["label"]:
            ensure_github_label(repo, label)

        if not issue.github:
            # Create on GitHub
            cmd = [
                "gh", "issue", "create",
                "--repo", repo,
                "--title", issue.title,
                "--body", issue.body.to_markdown()
            ]
            for label in mapping["label"]:
                cmd.extend(["--label", label])
            
            stdout, code, stderr = _run_command_with_stderr(cmd)
            if code == 0:
                url = stdout.strip()
                try:
                    number = int(url.split("/")[-1])
                    issue.github = GitHubInfo(repo=repo, number=number, url=url)
                    issue.sync = SyncInfo(
                        last_synced_at=datetime.datetime.now().isoformat(),
                        sync_hash=get_issue_hash(issue)
                    )
                    save_issue(issue)
                    logger.info(f"Created GitHub issue {number} for {local_id}")
                except (ValueError, IndexError):
                    logger.error(f"Failed to parse GitHub issue URL: {url}")
            else:
                logger.error(f"Failed to create GitHub issue for {local_id}: {stderr or stdout}")
        else:
            # Update on GitHub
            gh_number = str(issue.github.number)
            cmd = [
                "gh", "issue", "edit", gh_number,
                "--repo", repo,
                "--title", issue.title,
                "--body", issue.body.to_markdown()
            ]
            
            # Remove all possible status labels first (GitHub CLI doesn't have an easy way to clear labels,
            # so we'd have to know what labels were there. Simplified for now: just add the correct one)
            for label in mapping["label"]:
                cmd.extend(["--add-label", label])
            
            stdout, code, stderr = _run_command_with_stderr(cmd)
            if code == 0:
                if mapping["github_state"] == "closed":
                    run_command(["gh", "issue", "close", gh_number, "--repo", repo], check=False)
                elif mapping["github_state"] == "open":
                    run_command(["gh", "issue", "reopen", gh_number, "--repo", repo], check=False)

                issue.sync = SyncInfo(
                    last_synced_at=datetime.datetime.now().isoformat(),
                    sync_hash=get_issue_hash(issue)
                )
                save_issue(issue)
                logger.info(f"Updated GitHub issue {gh_number} for {local_id}")
            else:
                logger.error(f"Failed to update GitHub issue {gh_number}: {stderr or stdout}")

def pull_github_prds(repo: str, dry_run: bool = False):
    """Placeholder for pulling PRD updates from GitHub discussions/issues back to local files.
    For now, we mainly push local -> remote for PRDs.
    """
    pass

def sync_issues(quiet: bool = False):
    """Helper to sync local issues to GitHub."""
    repo = get_github_repo()
    if repo:
        if not quiet:
            click.echo(f"Syncing issues with {repo}...")
        push_local_issues(repo)
    elif not quiet:
        click.echo("Warning: Not a GitHub repository. Skipping sync.")

def register_sync(cli):
    @click.command(name="sync")
    @click.option("--dry-run", is_flag=True)
    @click.option("--full", is_flag=True)
    @click.option("--since", help="Pull updates since date")
    @click.option("--issues/--no-issues", default=True, help="Sync issues (default: true)")
    @click.option("--prds/--no-prds", default=True, help="Sync PRDs (default: true)")
    @click.option("--open-only", is_flag=True, default=True)
    @click.option("--label", help="Filter by label")
    def sync_command(dry_run, full, since, issues, prds, open_only, label):
        """Synchronize local issues and PRDs with GitHub."""
        repo = get_github_repo()
        if not repo:
            click.echo("Error: Not a GitHub repository.")
            return

        if dry_run:
            click.echo(f"Dry run: Would sync with {repo}")

        # Remember current branch to switch back later
        stdout, _ = run_command(["git", "branch", "--show-current"], check=False)
        current_branch = stdout.strip()
        main_branch = get_main_branch()

        # Switch to main branch for syncing
        if current_branch != main_branch:
            click.echo(f"Switching to {main_branch} for sync...")
            switch_to_main()
            
            # Verify we are on main
            stdout, _ = run_command(["git", "branch", "--show-current"], check=False)
            if stdout.strip() != main_branch:
                click.echo(f"Error: Could not switch to {main_branch}. Sync aborted.")
                return

        owner, name, repo_id = get_github_repo_info()

        # Determine relevant files for optimization
        relevant_files = None
        last_sync_time = since
        
        if not full:
            last_hash, last_time = get_last_sync_info(main_branch)
            if last_hash:
                relevant_files = set(get_files_changed_since(last_hash))
                if not last_sync_time:
                    last_sync_time = last_time
                click.echo(f"Optimizing sync using git diff since last sync ({last_hash[:8]})")

        if prds:
            if owner and name and repo_id:
                click.echo(f"Syncing PRDs with {repo}...")
                sync_prd_discussions(owner, name, repo_id, dry_run=dry_run, relevant_files=relevant_files)
                sync_prd_issues(owner, name, repo_id, dry_run=dry_run, relevant_files=relevant_files)
                pull_github_prds(repo, dry_run=dry_run)
            else:
                click.echo("Warning: Could not get full GitHub repo info. Skipping PRD sync.")

        if issues:
            click.echo(f"Syncing issues with {repo}...")
            # If --full is specified, we pull everything since ever and don't limit to open only
            if full:
                pull_github_issues(repo, open_only=False, since=None, label=label)
            else:
                pull_github_issues(repo, open_only=open_only, since=last_sync_time, label=label)
            
            push_local_issues(repo, relevant_files=relevant_files)
        
        if not dry_run:
            # Commit changes to main
            run_command(["git", "add", "issues/", "product/", "implementation/"], check=False)
            # Check if there are staged changes
            _, diff_code = run_command(["git", "diff", "--cached", "--quiet"], check=False)
            if diff_code != 0:
                click.echo("Committing changes to main...")
                run_command(["git", "commit", "-m", "vibe: sync issues and prds"], check=False)
        
        # Switch back if necessary
        if current_branch and current_branch != main_branch:
            click.echo(f"Switching back to {current_branch}...")
            run_command(["git", "checkout", current_branch], check=False)

        click.echo("Sync complete.")
    cli.add_command(sync_command)
