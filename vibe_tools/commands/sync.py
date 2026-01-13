import datetime
import json
import pathlib
import re
from typing import List, Optional, Dict, Any, Set

import click

from vibe_tools.prds import PRD, load_prd, generate_prd_id
from vibe_tools.utils import (
    PRODUCT_DIR,
    PRODUCT_BACKLOG_DIR,
    PRODUCT_IN_PROGRESS_DIR,
    PRODUCT_HISTORY_DIR,
    PLANNING_REJECTED_DIR,
    get_main_branch,
    load_project_state,
    logger,
    run_command,
    switch_to_main,
)

ENSURED_LABELS = set()

# Mapping local status to GitHub state and labels
STATUS_GITHUB_MAPPING = {
    "backlog": {"state": "open", "labels": []},
    "in_progress": {"state": "open", "labels": ["in-progress"]},
    "done": {"state": "closed", "labels": ["resolved"]},
    "rejected": {"state": "closed", "labels": ["rejected"]},
}

def get_github_repo_info():
    """Returns (owner, name, repo_id, discussions_enabled)"""
    repo = get_github_repo()
    if not repo:
        return None, None, None, False

    parts = repo.split("/")
    if len(parts) != 2:
        return None, None, None, False

    owner, name = parts

    query = """
    query($owner:String!, $name:String!) {
      repository(owner:$owner, name:$name) {
        id
        hasDiscussionsEnabled
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
    if code != 0:
        return owner, name, None, False

    try:
        data = json.loads(stdout)
        repo_data = data["data"]["repository"]
        repo_id = repo_data["id"]
        has_discussions = repo_data.get("hasDiscussionsEnabled", False)
        return owner, name, repo_id, has_discussions
    except (json.JSONDecodeError, KeyError):
        return owner, name, None, False

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
    stdout, _ = run_command(["git", "log", branch_name, "--grep=vibe: sync", "-n", "1", "--format=%H %aI"], check=False)
    parts = stdout.strip().split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None

def get_files_changed_since(commit_hash: str) -> List[str]:
    """Returns a list of files changed since the given commit hash."""
    stdout, _ = run_command(["git", "diff", "--name-status", commit_hash], check=False)
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

    stdout, _ = run_command(["git", "ls-files", "--others", "--exclude-standard"], check=False)
    if stdout.strip():
        changed_files.extend(stdout.strip().splitlines())

    return list(set(changed_files))

def fetch_github_discussions(owner, name):
    all_discussions = []
    has_next_page = True
    after = None

    while has_next_page:
        query = """
        query($owner:String!, $name:String!, $after:String) {
          repository(owner:$owner, name:$name) {
            discussions(first:100, after:$after) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                id
                number
                title
                body
                updatedAt
                isClosed
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
            "-f", f"name={name}",
        ]
        if after:
            cmd.extend(["-f", f"after={after}"])
            
        stdout, code = run_command(cmd, check=False)
        if code != 0:
            break

        try:
            data = json.loads(stdout)
            discussions = data["data"]["repository"]["discussions"]
            all_discussions.extend(discussions["nodes"])
            has_next_page = discussions["pageInfo"]["hasNextPage"]
            after = discussions["pageInfo"]["endCursor"]
        except (json.JSONDecodeError, KeyError, TypeError):
            break

    return all_discussions

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
    stdout, code = run_command(["gh", "api", "graphql", "-f", f"query=query {{ repository(owner: \"{owner}\", name: \"{name}\") {{ discussionCategories(first: 20) {{ nodes {{ id name }} }} }} }}"], check=False)
    if code != 0:
        return None

    try:
        data = json.loads(stdout)
        categories = data["data"]["repository"]["discussionCategories"]["nodes"]
        for node in categories:
            if node["name"] == category_name:
                return node["id"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None

def ensure_github_label(repo: str, label: str, color: str = "0075ca"):
    """Ensures a label exists on GitHub, creating it if necessary."""
    cache_key = f"{repo}:{label}"
    if cache_key in ENSURED_LABELS:
        return

    _, code, _ = _run_command_with_stderr(["gh", "label", "view", label, "--repo", repo])
    if code != 0:
        logger.info(f"Creating missing label '{label}' on GitHub...")
        run_command(["gh", "label", "create", label, "--repo", repo, "--color", color], check=False)

    ENSURED_LABELS.add(cache_key)

def _run_command_with_stderr(cmd):
    import subprocess
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode, result.stderr.strip()

def get_github_repo():
    stdout, code = run_command(["git", "remote", "get-url", "origin"], check=False)
    if code != 0:
        return None
    url = stdout.strip()
    if not url:
        return None

    if "github.com" not in url:
        return None

    if url.startswith("git@github.com:"):
        repo = url.replace("git@github.com:", "").replace(".git", "")
    elif url.startswith("https://github.com/"):
        repo = url.replace("https://github.com/", "").replace(".git", "")
    else:
        parts = url.split("github.com/")
        if len(parts) > 1:
            repo = parts[1].replace(".git", "")
        else:
            return None
    return repo

def sync_unified_prds(repo_owner, repo_name, repo_id, has_discussions, dry_run=False, relevant_files=None):
    """Sync all PRDs (Features and Issues) with GitHub."""
    repo = f"{repo_owner}/{repo_name}"
    
    # 1. Fetch current remote state
    gh_discussions = fetch_github_discussions(repo_owner, repo_name) if has_discussions else []
    gh_disc_by_id = {d["id"]: d for d in gh_discussions}
    gh_disc_by_title = {d["title"]: d for d in gh_discussions}
    
    # Fetch issues in bulk to optimize state checks
    gh_issues = []
    # Fetch more issues and include body for robust matching
    cmd = ["gh", "issue", "list", "--repo", repo, "--label", "prd", "--state", "all", "--limit", "1000", "--json", "number,state,title,body"]
    stdout, code = run_command(cmd, check=False)
    if code == 0:
        try:
            gh_issues = json.loads(stdout)
        except Exception: pass
    gh_issue_by_number = {i["number"]: i for i in gh_issues}
    
    # 2. Iterate through all local PRDs
    all_local_paths = list(PRODUCT_DIR.rglob("*.md"))
    
    # Skip system files
    system_stems = ["architecture", "infrastructure", "cicd", "testing", "dev_environment", "project_overview", "setup"]
    
    for path in all_local_paths:
        if path.stem in system_stems:
            continue
            
        if relevant_files is not None and str(path) not in relevant_files:
            continue
            
        try:
            prd = load_prd(path)
            if prd.type == "FEATURE" and has_discussions:
                sync_feature_prd(prd, repo_owner, repo_name, repo_id, gh_disc_by_id, gh_disc_by_title, dry_run)
            elif prd.type == "ISSUE":
                # Find matching issue if not known by number
                match = gh_issue_by_number.get(prd.issue_number)
                if not match:
                    vibe_id_comment = f"<!-- vibe-id: {prd.id} -->"
                    for ish in gh_issues:
                        if vibe_id_comment in (ish.get("body") or ""):
                            match = ish
                            break
                sync_issue_prd(prd, repo, dry_run, match)
        except Exception as e:
            logger.error(f"Failed to sync {path.name}: {e}")

def sync_feature_prd(prd: PRD, owner, name, repo_id, gh_by_id, gh_by_title, dry_run):
    """Sync a FEATURE PRD with GitHub Discussions."""
    title = f"[PRD] {prd.title}"
    body = prd.to_markdown()
    category_id = get_discussion_category_id(owner, name)
    
    gh_disc = None
    if prd.discussion_id:
        gh_disc = gh_by_id.get(prd.discussion_id)
    
    if not gh_disc:
        gh_disc = gh_by_title.get(title)
        
    if not gh_disc:
        # Robust matching by hidden ID
        vibe_id_comment = f"<!-- vibe-id: {prd.id} -->"
        for disc in gh_by_id.values():
            if vibe_id_comment in (disc.get("body") or ""):
                gh_disc = disc
                break
        
    if not gh_disc:
        if dry_run:
            logger.info(f"[DRY RUN] Would create GitHub Discussion for {prd.id}")
            return
            
        cmd = [
            "gh", "api", "graphql",
            "-f", "query=mutation($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) { createDiscussion(input: { repositoryId: $repoId, categoryId: $categoryId, title: $title, body: $body }) { discussion { id url } } }",
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
                prd.discussion_id = disc["id"]
                prd.last_synced_at = datetime.datetime.now().isoformat()
                prd.sync_hash = prd.get_hash()
                prd.save()
                update_gh_labels(prd, disc["id"], f"{owner}/{name}", is_discussion=True)
                logger.info(f"Created GitHub Discussion for {prd.id}")
            except Exception:
                logger.error(f"Failed to parse discussion creation for {prd.id}")
    else:
        # Sync existing
        if not prd.discussion_id:
            prd.discussion_id = gh_disc["id"]
            prd.save()
            
        current_hash = prd.get_hash()
        if gh_disc["body"] != body or prd.sync_hash != current_hash:
            if dry_run:
                logger.info(f"[DRY RUN] Would update GitHub Discussion for {prd.id}")
            else:
                cmd = [
                    "gh", "api", "graphql",
                    "-f", "query=mutation($id: ID!, $title: String!, $body: String!) { updateDiscussion(input: { discussionId: $id, title: $title, body: $body }) { discussion { id url } } }",
                    "-f", f"id={gh_disc['id']}",
                    "-f", f"title={title}",
                    "-f", f"body={body}"
                ]
                run_command(cmd, check=False)
                prd.last_synced_at = datetime.datetime.now().isoformat()
                prd.sync_hash = current_hash
                prd.save()
                logger.info(f"Updated GitHub Discussion for {prd.id}")
        
        # Close/Reopen based on status
        mapping = STATUS_GITHUB_MAPPING.get(prd.status, STATUS_GITHUB_MAPPING["backlog"])
        should_close = mapping["state"] == "closed"
        is_closed = gh_disc.get("isClosed", False)

        if should_close and not is_closed:
            if not dry_run:
                close_reason = "RESOLVED" if prd.status == "done" else "OUTDATED"
                cmd = [
                    "gh", "api", "graphql",
                    "-f", "query=mutation($id: ID!, $reason: DiscussionCloseReason) { closeDiscussion(input: { discussionId: $id, reason: $reason }) { discussion { id } } }",
                    "-f", f"id={gh_disc['id']}",
                    "-f", f"reason={close_reason}"
                ]
                run_command(cmd, check=False)
                logger.info(f"Closed GitHub Discussion for {prd.id} ({close_reason})")
            else:
                logger.info(f"[DRY RUN] Would close GitHub Discussion for {prd.id}")
        elif not should_close and is_closed:
            if not dry_run:
                cmd = [
                    "gh", "api", "graphql",
                    "-f", "query=mutation($id: ID!) { reopenDiscussion(input: { discussionId: $id }) { discussion { id } } }",
                    "-f", f"id={gh_disc['id']}"
                ]
                run_command(cmd, check=False)
                logger.info(f"Reopened GitHub Discussion for {prd.id}")
            else:
                logger.info(f"[DRY RUN] Would reopen GitHub Discussion for {prd.id}")

        update_gh_labels(prd, gh_disc["id"], f"{owner}/{name}", is_discussion=True, current_labels=[l["name"] for l in gh_disc["labels"]["nodes"]])

def sync_issue_prd(prd: PRD, repo, dry_run, gh_issue=None):
    """Sync an ISSUE PRD with GitHub Issues."""
    title = f"[ISSUE] {prd.title}"
    body = prd.to_markdown()
    
    if not prd.issue_number and gh_issue:
        prd.issue_number = gh_issue["number"]
        prd.save()

    if not prd.issue_number:
        if dry_run:
            logger.info(f"[DRY RUN] Would create GitHub Issue for {prd.id}")
            return
            
        cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
        stdout, code, stderr = _run_command_with_stderr(cmd)
        if code == 0:
            url = stdout.strip()
            number = int(url.split("/")[-1])
            prd.issue_number = number
            prd.last_synced_at = datetime.datetime.now().isoformat()
            prd.sync_hash = prd.get_hash()
            prd.save()
            update_gh_labels(prd, str(number), repo, is_discussion=False)
            logger.info(f"Created GitHub Issue #{number} for {prd.id}")
    else:
        # Update existing
        current_hash = prd.get_hash()
        
        # Determine if we need to update body
        remote_body = (gh_issue.get("body") or "") if gh_issue else ""
        
        if prd.sync_hash != current_hash or (remote_body and remote_body != body):
            if dry_run:
                logger.info(f"[DRY RUN] Would update GitHub Issue #{prd.issue_number}")
            else:
                cmd = ["gh", "issue", "edit", str(prd.issue_number), "--repo", repo, "--title", title, "--body", body]
                run_command(cmd, check=False)
                prd.last_synced_at = datetime.datetime.now().isoformat()
                prd.sync_hash = current_hash
                prd.save()
                logger.info(f"Updated GitHub Issue #{prd.issue_number}")
        
        # Check if we need to close/reopen
        mapping = STATUS_GITHUB_MAPPING.get(prd.status, STATUS_GITHUB_MAPPING["backlog"])
        should_close = mapping["state"] == "closed"
        
        # Determine current state if available
        is_closed = False
        if gh_issue:
            is_closed = gh_issue.get("state") in ["CLOSED", "closed"]
        
        if should_close and not is_closed:
            if not dry_run:
                run_command(["gh", "issue", "close", str(prd.issue_number), "--repo", repo], check=False)
                logger.info(f"Closed GitHub Issue #{prd.issue_number}")
            else:
                logger.info(f"[DRY RUN] Would close GitHub Issue #{prd.issue_number}")
        elif not should_close and is_closed:
            if not dry_run:
                run_command(["gh", "issue", "reopen", str(prd.issue_number), "--repo", repo], check=False)
                logger.info(f"Reopened GitHub Issue #{prd.issue_number}")
            else:
                logger.info(f"[DRY RUN] Would reopen GitHub Issue #{prd.issue_number}")
            
        update_gh_labels(prd, str(prd.issue_number), repo, is_discussion=False)

def update_gh_labels(prd: PRD, remote_id: str, repo: str, is_discussion: bool, current_labels: List[str] = None):
    """Ensure remote labels match PRD type, status, and group."""
    repo_owner, repo_name = repo.split("/")
    
    # 1. Determine desired labels
    labels = ["prd"]
    labels.append(prd.type.lower()) # 'feature' or 'issue'
    
    mapping = STATUS_GITHUB_MAPPING.get(prd.status, STATUS_GITHUB_MAPPING["backlog"])
    labels.extend(mapping["labels"])
    
    if prd.group:
        labels.append(f"group:{prd.group}")
        
    # 2. Ensure all exist
    for l in labels:
        ensure_github_label(repo, l)
        
    # 3. Apply labels
    if is_discussion:
        if current_labels is not None:
            to_add = [l for l in labels if l not in current_labels]
            if to_add:
                label_ids = [get_label_id(repo_owner, repo_name, l) for l in to_add]
                add_discussion_labels(remote_id, [lid for lid in label_ids if lid])
    else:
        # For Issues, we can just use gh issue edit
        cmd = ["gh", "issue", "edit", remote_id, "--repo", repo]
        for l in labels:
            cmd.extend(["--add-label", l])
        run_command(cmd, check=False)

def pull_github_content(repo_owner, repo_name, repo_id, has_discussions, full=False):
    """Pull new content from GitHub into product/backlog/."""
    repo = f"{repo_owner}/{repo_name}"
    
    # 1. Pull Issues labeled 'prd'
    cmd = ["gh", "issue", "list", "--repo", repo, "--label", "prd", "--json", "number,title,body,updatedAt,state,labels"]
    stdout, code = run_command(cmd, check=False)
    if code == 0:
        issues = json.loads(stdout)
        for ish in issues:
            process_remote_item(ish, is_discussion=False)
            
    # 2. Pull Discussions labeled 'prd'
    if has_discussions:
        discs = fetch_github_discussions(repo_owner, repo_name)
        for disc in discs:
            labels = [l["name"] for l in disc["labels"]["nodes"]]
            if "prd" in labels:
                process_remote_item(disc, is_discussion=True)

def process_remote_item(item: Dict[str, Any], is_discussion: bool):
    """Process a remote GitHub item and update/create local PRD."""
    # Find local match by discussion_id or issue_number
    all_local_paths = list(PRODUCT_DIR.rglob("*.md"))
    matched_prd = None
    
    remote_id = item["id"] if is_discussion else item["number"]
    
    for path in all_local_paths:
        try:
            prd = load_prd(path)
            if is_discussion and prd.discussion_id == remote_id:
                matched_prd = prd
                break
            elif not is_discussion and prd.issue_number == remote_id:
                matched_prd = prd
                break
        except Exception: continue
        
    if matched_prd:
        # Potential update from remote? 
        # For now we prioritize local, but could add bidirectional logic here
        return
        
    # Create new if it looks like a Vibe PRD
    if not item["title"].startswith("[PRD]") and not item["title"].startswith("[ISSUE]"):
        return
        
    new_id = generate_prd_id(PRODUCT_DIR)
    title = item["title"].replace("[PRD] ", "").replace("[ISSUE] ", "")
    prd_type = "FEATURE" if is_discussion else "ISSUE"
    
    new_prd = PRD(
        id=new_id,
        title=title,
        type=prd_type,
        status="backlog",
        content=item["body"]
    )
    
    if is_discussion: new_prd.discussion_id = remote_id
    else: new_prd.issue_number = remote_id
    
    new_prd.last_synced_at = item["updatedAt"]
    
    filename = f"{new_id}-{re.sub(r'[^a-z0-9]+', '-', title.lower())}.md"
    new_prd.save(PRODUCT_BACKLOG_DIR / filename)
    logger.info(f"Pulled new {prd_type} from GitHub: {new_id}")

def delete_github_discussion(discussion_id):
    query = """
    mutation($id: ID!) {
      deleteDiscussion(input: {id: $id}) {
        clientMutationId
      }
    }
    """
    cmd = [
        "gh", "api", "graphql",
        "-f", f"query={query}",
        "-f", f"id={discussion_id}"
    ]
    run_command(cmd, check=False)

def reset_remote_state(owner, name, has_discussions):
    repo = f"{owner}/{name}"
    click.echo(f"🗑️ Resetting remote state for {repo}...")
    
    # 1. Close all issues labeled 'prd'
    cmd = ["gh", "issue", "list", "--repo", repo, "--label", "prd", "--state", "open", "--json", "number"]
    stdout, code = run_command(cmd, check=False)
    if code == 0:
        issues = json.loads(stdout)
        for ish in issues:
            click.echo(f"  Closing issue #{ish['number']}...")
            run_command(["gh", "issue", "close", str(ish["number"]), "--repo", repo], check=False)
            
    # 2. Delete all discussions labeled 'prd'
    if has_discussions:
        discs = fetch_github_discussions(owner, name)
        for disc in discs:
            labels = [l["name"] for l in disc["labels"]["nodes"]]
            if "prd" in labels:
                click.echo(f"  Deleting discussion {disc['id']}...")
                delete_github_discussion(disc["id"])

    # 3. Clear local sync metadata
    all_local_paths = list(PRODUCT_DIR.rglob("*.md"))
    for path in all_local_paths:
        try:
            # We don't want to load system files
            system_stems = ["architecture", "infrastructure", "cicd", "testing", "dev_environment", "project_overview", "setup"]
            if path.stem in system_stems:
                continue
                
            prd = load_prd(path)
            if prd.discussion_id or prd.issue_number:
                prd.discussion_id = None
                prd.issue_number = None
                prd.last_synced_at = None
                prd.sync_hash = None
                prd.save()
        except Exception: continue

def register_sync(cli):
    @click.command(name="sync")
    @click.option("--dry-run", is_flag=True)
    @click.option("--full", is_flag=True)
    @click.option("--local", is_flag=True, help="Sync local files and state only")
    @click.option("--reset-remote", is_flag=True, help="Close all remote PRD issues and delete PRD discussions")
    def sync_command(dry_run, full, local, reset_remote):
        """Synchronize local PRDs/Issues with GitHub and align state."""
        from vibe_tools.commands.migrate import run_reconciliation
        
        # 1. Local Alignment
        click.echo("🔄 Aligning local PRD files and state...")
        run_reconciliation(quiet=True)
        
        if local:
            click.echo("Local sync complete.")
            return

        repo_info = get_github_repo_info()
        owner, name, repo_id, has_discussions = repo_info
        
        if not owner or not name:
            click.echo("Error: Not a GitHub repository or could not get info.")
            return

        if reset_remote:
            reset_remote_state(owner, name, has_discussions)
            click.echo("✅ Remote reset complete.")
            return

        # 2. Pull Remote
        click.echo(f"📥 Pulling updates from {owner}/{name}...")
        pull_github_content(owner, name, repo_id, has_discussions, full=full)
        
        # 3. Push Local
        click.echo(f"📤 Pushing local changes to {owner}/{name}...")
        sync_unified_prds(owner, name, repo_id, has_discussions, dry_run=dry_run)
        
        if not dry_run:
            # Commit sync changes
            run_command(["git", "add", "product/"], check=False)
            _, diff_code = run_command(["git", "diff", "--cached", "--quiet"], check=False)
            if diff_code != 0:
                click.echo("Committing sync updates...")
                run_command(["git", "-c", "user.name=vibe-bot", "-c", "user.email=bot@vibe.tools", "commit", "-m", "vibe: sync metadata"], check=False)

        click.echo("✅ Sync complete.")

    cli.add_command(sync_command)
