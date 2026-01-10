import click
import datetime
import json
import os
from typing import List, Optional
from vibe_tools.issues import (
    Issue, IssueBody, GitHubInfo, SyncInfo, load_index, save_issue, 
    load_issue_by_id, get_issue_hash, generate_issue_id,
    BACKLOG_DIR, HISTORY_DIR, STATUS_MAPPING
)
from vibe_tools.utils import run_command, logger, switch_to_main, get_main_branch

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
    cmd = ["gh", "issue", "list", "--repo", repo, "--json", "number,title,body,state,labels,updatedAt,url"]
    if not open_only:
        cmd.append("--state")
        cmd.append("all")
    if since:
        cmd.append("--since")
        cmd.append(since)
    if label:
        cmd.append("--label")
        cmd.append(label)
    
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

def push_local_issues(repo: str):
    index = load_index()
    for local_id in index:
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

def register_sync(cli):
    @click.command(name="sync")
    @click.option("--dry-run", is_flag=True)
    @click.option("--full", is_flag=True)
    @click.option("--since", help="Pull issues updated since date")
    @click.option("--open-only", is_flag=True, default=True)
    @click.option("--label", help="Filter by label (e.g. vibe-managed)")
    def sync_command(dry_run, full, since, open_only, label):
        """Synchronize local issues with GitHub."""
        repo = get_github_repo()
        if not repo:
            click.echo("Error: Not a GitHub repository.")
            return

        if dry_run:
            click.echo(f"Dry run: Would sync with {repo}")
            return

        # Remember current branch to switch back later
        stdout, _ = run_command(["git", "branch", "--show-current"], check=False)
        current_branch = stdout.strip()
        main_branch = get_main_branch()

        # Switch to main branch for syncing issues as requested
        if current_branch != main_branch:
            click.echo(f"Switching to {main_branch} for issue sync...")
            switch_to_main()
            
            # Verify we are on main
            stdout, _ = run_command(["git", "branch", "--show-current"], check=False)
            if stdout.strip() != main_branch:
                click.echo(f"Error: Could not switch to {main_branch}. Sync aborted.")
                return

        click.echo(f"Syncing issues with {repo}...")
        
        # If --full is specified, we pull everything since ever and don't limit to open only
        if full:
            pull_github_issues(repo, open_only=False, since=None, label=label)
        else:
            pull_github_issues(repo, open_only=open_only, since=since, label=label)
        
        push_local_issues(repo)
        
        # Commit changes to main
        run_command(["git", "add", "issues/"], check=False)
        # Check if there are staged changes
        _, diff_code = run_command(["git", "diff", "--cached", "--quiet"], check=False)
        if diff_code != 0:
            click.echo("Committing issue changes to main...")
            run_command(["git", "commit", "-m", "vibe: sync issues"], check=False)
        
        # Switch back if necessary
        if current_branch and current_branch != main_branch:
            click.echo(f"Switching back to {current_branch}...")
            run_command(["git", "checkout", current_branch], check=False)

        click.echo("Sync complete.")
    cli.add_command(sync_command)
