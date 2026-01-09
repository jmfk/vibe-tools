import click
import datetime
import json
import subprocess
from typing import List, Optional
from vibe_tools.issues import (
    Issue, GitHubInfo, SyncInfo, load_index, save_issue, 
    load_issue_by_id, get_issue_hash, generate_issue_id,
    BACKLOG_DIR, HISTORY_DIR
)
from vibe_tools.utils import run_command, logger

STATUS_MAPPING = {
    "backlog": {"github_state": "open", "labels": []},
    "in_progress": {"github_state": "open", "labels": ["in-progress"]},
    "blocked": {"github_state": "open", "labels": ["blocked"]},
    "done": {"github_state": "closed", "labels": ["resolved"]},
}

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
    else:
        repo = url.replace("https://github.com/", "").replace(".git", "")
    return repo

def pull_github_issues(repo: str, open_only: bool = True, since: Optional[str] = None):
    cmd = ["gh", "issue", "list", "--repo", repo, "--json", "number,title,body,state,labels,updatedAt,url"]
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
            # Update existing local issue
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
                issue.body += f"\n\n## CONFLICT\nRemote changes detected on GitHub at {gh_updated_at}. Local changes also exist. Please resolve manually."
                save_issue(issue)
                continue

            if is_remote_changed and not is_local_changed:
                # Local hasn't changed, safe to update from GH
                issue.title = gh_issue["title"]
                
                # Fetch comments
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

                issue.comments = comments_body
                issue.body = gh_issue["body"]
                issue.updated_at = gh_updated_at
                # Map status
                if gh_issue["state"] == "CLOSED":
                    issue.status = "done"
                else:
                    # Try to map labels
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
            
            # Better status mapping from labels
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
                severity="medium", # Default
                service="unknown", # Default
                created_at=gh_issue["updatedAt"], # Close enough for new pulls
                updated_at=gh_issue["updatedAt"],
                body=gh_issue["body"],
                github=GitHubInfo(
                    repo=repo,
                    number=gh_number,
                    url=gh_issue["url"]
                ),
                sync=SyncInfo(
                    last_synced_at=gh_issue["updatedAt"],
                    sync_hash="" # Will be set on save
                )
            )
            issue.sync.sync_hash = get_issue_hash(issue)
            save_issue(issue)
            logger.info(f"Pulled new issue {gh_number} as {local_id}")

def push_local_issues(repo: str):
    # Scan backlog and history for issues that need pushing
    index = load_index()
    for local_id in index:
        issue = load_issue_by_id(local_id)
        if not issue:
            continue
        
        current_hash = get_issue_hash(issue)
        if issue.sync and issue.sync.sync_hash == current_hash:
            # Nothing changed locally since last sync
            continue
        
        if issue.status == "blocked":
            # Don't push blocked issues (potential conflicts)
            continue

        if not issue.github:
            # Create on GitHub
            cmd = [
                "gh", "issue", "create",
                "--repo", repo,
                "--title", issue.title,
                "--body", issue.body
            ]
            # Add labels
            mapping = STATUS_MAPPING.get(issue.status, STATUS_MAPPING["backlog"])
            for label in mapping["labels"]:
                cmd.extend(["--label", label])
            
            stdout, code = run_command(cmd, check=False)
            if code == 0:
                # gh issue create returns the URL
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
                logger.error(f"Failed to create GitHub issue for {local_id}: {stdout}")
        else:
            # Update on GitHub
            gh_number = str(issue.github.number)
            cmd = [
                "gh", "issue", "edit", gh_number,
                "--repo", repo,
                "--title", issue.title,
                "--body", issue.body
            ]
            
            # Update state and labels
            mapping = STATUS_MAPPING.get(issue.status, STATUS_MAPPING["backlog"])
            for label in mapping["labels"]:
                cmd.extend(["--add-label", label])
            
            stdout, code = run_command(cmd, check=False)
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
                logger.error(f"Failed to update GitHub issue {gh_number}: {stdout}")

def register_sync(cli):
    @click.command(name="sync")
    @click.option("--dry-run", is_flag=True)
    @click.option("--full", is_flag=True)
    @click.option("--since", help="Pull issues updated since date")
    @click.option("--open-only", is_flag=True, default=True)
    def sync_command(dry_run, full, since, open_only):
        """Synchronize local issues with GitHub."""
        repo = get_github_repo()
        if not repo:
            click.echo("Error: Not a GitHub repository.")
            return

        if dry_run:
            click.echo(f"Dry run: Would sync with {repo}")
            return

        click.echo(f"Syncing issues with {repo}...")
        
        # 1. Pull from GitHub
        pull_github_issues(repo, open_only=open_only, since=since)
        
        # 2. Push local changes
        push_local_issues(repo)
        
        click.echo("Sync complete.")
    cli.add_command(sync_command)
