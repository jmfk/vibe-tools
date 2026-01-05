import atexit
import datetime
import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
import time
from dotenv import load_dotenv, find_dotenv, set_key
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

PRD_DIR = pathlib.Path("prds")
PLANS_DIR = pathlib.Path("plans")
PROJECT_STATE_FILE = pathlib.Path("project-state.json")
STATE_FILE = pathlib.Path(".ralph_state.json")
LOGS_DIR = pathlib.Path("logs")
COSTS_DIR = pathlib.Path("costs")
INSTRUCTIONS_DIR = pathlib.Path("instructions")
CONFIG_FILE = pathlib.Path(".vibe_config.json")
GLOBAL_VIBE_DIR = pathlib.Path.home() / ".vibe"

# Core lifecycle files
ARCHITECTURE = pathlib.Path("architecture.yaml")
ARCHITECTURE_CURRENT = pathlib.Path("architecture-current.yaml")
OVERVIEW = pathlib.Path("project_overview.yaml")
PROJECT_PLAN = pathlib.Path("project-plan.yaml")
PROJECT_PLAN_CURRENT = pathlib.Path("project-plan-current.yaml")
INFRA = pathlib.Path("infrastructure.yaml")
INFRA_CURRENT = pathlib.Path("infrastructure-current.yaml")
CICD = pathlib.Path("cicd.yaml")
CICD_CURRENT = pathlib.Path("cicd-current.yaml")
TESTING_CONFIG = pathlib.Path("testing.yaml")
TESTING_CURRENT = pathlib.Path("testing-current.yaml")
GLOBAL_CONFIG_FILE = GLOBAL_VIBE_DIR / "config.json"
GLOBAL_SERVERS_FILE = GLOBAL_VIBE_DIR / "servers.json"

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
COSTS_DIR.mkdir(exist_ok=True)
GLOBAL_VIBE_DIR.mkdir(exist_ok=True)


def get_project_name():
    """Returns the project name in snake_case based on git remote or directory name."""
    if is_git_repo():
        stdout, code = run_command(["git", "remote", "get-url", "origin"], check=False)
        if code == 0 and stdout.strip():
            # Handle both https and ssh formats
            url = stdout.strip()
            if url.endswith(".git"):
                url = url[:-4]
            project_name = url.split("/")[-1].split(":")[-1]
            return project_name.lower().replace("-", "_").replace(" ", "_")
    
    # Fallback to directory name
    return pathlib.Path.cwd().name.lower().replace("-", "_").replace(" ", "_")


def load_config():
    """Loads and merges global and project-local configuration."""
    config = {}
    
    # Load global config first
    if GLOBAL_CONFIG_FILE.exists():
        try:
            config.update(json.loads(GLOBAL_CONFIG_FILE.read_text()))
        except Exception as e:
            logger.debug(f"Error loading global config: {e}")

    # Merge with local config
    if CONFIG_FILE.exists():
        try:
            local_config = json.loads(CONFIG_FILE.read_text())
            # Deep merge services if they exist in both
            if "services" in local_config and "services" in config:
                config["services"].update(local_config["services"])
                del local_config["services"]
            config.update(local_config)
        except Exception as e:
            logger.debug(f"Error loading local config: {e}")
            
    return config


def save_config(config, global_scope=False):
    """Saves configuration to either local or global file."""
    if global_scope:
        GLOBAL_CONFIG_FILE.write_text(json.dumps(config, indent=2))
    else:
        CONFIG_FILE.write_text(json.dumps(config, indent=2))
        ensure_gitignore(".vibe_config.json")
        ensure_gitignore(".env")
        ensure_gitignore("logs/")
        ensure_gitignore(".vibe_google_creds.json")
        ensure_gitignore(".vibe_client_secrets.json")
        ensure_gitignore(".vibe_authorized_user.json")


def load_project_state() -> Dict[str, Any]:
    """Loads the project state, migrating from legacy if necessary."""
    if not PROJECT_STATE_FILE.exists() and STATE_FILE.exists():
        migrate_legacy_state()

    if PROJECT_STATE_FILE.exists():
        try:
            return json.loads(PROJECT_STATE_FILE.read_text())
        except Exception as e:
            logger.error(f"Error loading project state: {e}")

    # Default state structure
    return {
        "project_name": get_project_name(),
        "phases": {
            "setup": {"status": "pending", "hash": None},
            "normalize": {"status": "pending", "hash": None},
            "plan": {"status": "pending", "hash": None},
            "implement": {"status": "pending", "hash": None},
            "infra": {"status": "pending", "hash": None},
            "cicd": {"status": "pending", "hash": None},
            "testing": {"status": "pending", "hash": None},
            "deploy": {"status": "pending", "hash": None},
        },
        "completed_prds": [],
        "started_prds": [],
        "active_task": None,
        "version": "1.0",
    }


def save_project_state(state: Dict[str, Any]):
    """Saves the project state to project-state.json and commits it if in a git repo."""
    PROJECT_STATE_FILE.write_text(json.dumps(state, indent=2))
    
    if is_git_repo():
        # Avoid recursive calls or excessive commits, but ensure state is "safe"
        # We only commit if there's an actual change to the state file
        try:
            # Check if state file is modified or untracked
            stdout, _ = run_command(["git", "status", "--porcelain", str(PROJECT_STATE_FILE)], check=False)
            if stdout.strip():
                logger.debug(f"Committing {PROJECT_STATE_FILE} for safety...")
                run_command(["git", "add", str(PROJECT_STATE_FILE)], check=False)
                run_command(["git", "commit", "-m", "vibe: update project state", "--no-verify"], check=False)
        except Exception as e:
            logger.debug(f"Failed to auto-commit project state: {e}")


def migrate_legacy_state():
    """Migrates data from .ralph_state.json to project-state.json."""
    if not STATE_FILE.exists():
        return

    try:
        legacy_data = json.loads(STATE_FILE.read_text())
        new_state = load_project_state()

        # Migrate completed and started PRDs
        new_state["completed_prds"] = legacy_data.get("completed_prds", [])
        new_state["started_prds"] = legacy_data.get("started_prds", [])
        new_state["active_task"] = legacy_data.get("active_task")

        # Basic heuristic: if there are completed PRDs, maybe setup was done?
        # But we'll stay conservative and let the user run setup.
        
        save_project_state(new_state)
        logger.info(f"✅ Migrated legacy state to {PROJECT_STATE_FILE}")
        # We keep the old file for safety for now, or we could delete it.
        # STATE_FILE.unlink() 
    except Exception as e:
        logger.error(f"Failed to migrate legacy state: {e}")


def load_global_servers() -> Dict[str, Any]:
    """Loads server definitions from the global servers file."""
    if GLOBAL_SERVERS_FILE.exists():
        try:
            return json.loads(GLOBAL_SERVERS_FILE.read_text())
        except Exception as e:
            logger.error(f"Error loading global servers: {e}")
    return {}


def save_global_servers(servers: Dict[str, Any]):
    """Saves server definitions to the global servers file."""
    GLOBAL_SERVERS_FILE.write_text(json.dumps(servers, indent=2))


def get_google_api_key():
    """Retrieves the Google API Key from .env or environment variables."""
    load_dotenv(find_dotenv() or ".env")
    return os.environ.get("GOOGLE_API_KEY")


def save_google_api_key(key):
    """Saves the Google API Key to the .env file."""
    env_file = find_dotenv() or ".env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("")
    set_key(env_file, "GOOGLE_API_KEY", key)
    ensure_gitignore(".env")


# Setup logger
logger = logging.getLogger("vibe")
logger.setLevel(logging.DEBUG)

# Globals to be initialized by setup_logging
LOG_FILE = None
file_handler = None
stream_handler = None


def setup_logging(command_name):
    """Initializes logging for a specific command run."""
    global LOG_FILE, file_handler, stream_handler

    # Generate timestamped log filename with command name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_FILE = LOGS_DIR / f"vibe_{command_name}_{timestamp}.log"

    # File handler
    file_handler = RotatingFileHandler(LOG_FILE, backupCount=5)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    # Stream handler (console)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)

    return LOG_FILE


def set_console_level(level):
    """Sets the console output level."""
    if stream_handler:
        stream_handler.setLevel(level)


# Flag to track if an agent was called
_agent_called = False


def _cleanup_log():
    """Deletes the log file if it's empty."""
    global LOG_FILE, file_handler
    if not LOG_FILE:
        return

    try:
        # Delete only if the file is empty
        if LOG_FILE.exists() and LOG_FILE.stat().st_size == 0:
            # Close handler to release file lock
            if file_handler:
                file_handler.close()
                logger.removeHandler(file_handler)
            if LOG_FILE.exists():
                LOG_FILE.unlink()
    except Exception:
        pass


atexit.register(_cleanup_log)


def enable_console_debug():
    """Sets the console output level to DEBUG."""
    if stream_handler:
        stream_handler.setLevel(logging.DEBUG)
        logger.debug("Console debug logging enabled.")


def rotate_log():
    """Rotates the log file if it exists and is not empty."""
    if LOG_FILE and LOG_FILE.exists() and LOG_FILE.stat().st_size > 0:
        if file_handler:
            file_handler.doRollover()


def is_merged(branch_name):
    """Checks if a branch is merged into main."""
    main_branch = get_main_branch()
    _, code = run_command(["git", "merge-base", "--is-ancestor", branch_name, main_branch], check=False)
    return code == 0


def run_command(cmd, check=True, caffeinate=False):
    """Utility to run a command and return its output."""
    if caffeinate:
        cmd = ["caffeinate", "-dimsu"] + cmd

    # Use logger.debug for the "Running command" message so it's hidden by default
    logger.debug(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Debug level logging for full command output
    logger.debug(f"Command finished with return code: {result.returncode}")
    if result.stdout:
        logger.debug(f"STDOUT:\n{result.stdout.strip()}")
    if result.stderr:
        logger.debug(f"STDERR:\n{result.stderr.strip()}")

    if check and result.returncode != 0:
        logger.error(f"Error running command: {' '.join(cmd)}")
        if not logger.isEnabledFor(logging.DEBUG):
            # If not in debug mode, at least log the error output to info/error
            logger.error(f"STDOUT: {result.stdout.strip()}")
            logger.error(f"STDERR: {result.stderr.strip()}")
        return result.stdout.strip(), result.returncode
    return result.stdout.strip(), result.returncode


def run_agent(cmd, caffeinate=False, stream=False):
    """Runs an agent with a live progress indicator or streaming output."""
    global _agent_called
    _agent_called = True
    if caffeinate:
        cmd = ["caffeinate", "-dimsu"] + cmd

    # Use logger.debug for the "Running agent" message
    logger.debug(f"Running agent: {' '.join(cmd)}")

    # Use process groups to ensure children are killed on interrupt (Unix only)
    popen_kwargs: Dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if os.name != "nt":
        popen_kwargs["preexec_fn"] = os.setsid

    process = subprocess.Popen(cmd, **popen_kwargs)
    full_output, start_time = [], time.time()

    assert process.stdout is not None
    try:
        for line in iter(process.stdout.readline, ""):
            full_output.append(line)
            elapsed = int(time.time() - start_time)
            preview = line.strip()[:80]
            
            if stream:
                # Direct streaming to stdout
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                # Live progress to stdout (bypassing file log for spammy progress)
                sys.stdout.write(f"\r\033[K⏳ Agent working ({elapsed}s)... {preview}")
                sys.stdout.flush()
            
            # Also log to debug file immediately
            logger.debug(f"AGENT_LIVE: {line.strip()}")
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user. Cleaning up agent process...")
        if os.name != "nt":
            try:
                pgid = os.getpgid(process.pid)
                os.killpg(pgid, signal.SIGTERM)
                # Wait a bit for graceful exit then force kill if needed
                time.sleep(0.5)
                if process.poll() is None:
                    os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.terminate()
        process.wait()
        sys.stdout.write("\n")
        raise
    finally:
        if process.stdout:
            process.stdout.close()
        process.wait()

    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

    output = "".join(full_output)
    logger.info(f"Agent finished with exit code: {process.returncode}")

    # Log full agent output to debug level (which goes to file)
    logger.debug(f"\n--- AGENT OUTPUT START ---\n{output}\n--- AGENT OUTPUT END ---\n")

    return output, process.returncode


def cleanup_stale_processes():
    """Kills stale pytest, cursor-agent, and caffeinate processes."""
    logger.info("Cleaning up stale processes associated with vibe-tools...")

    targets = ["pytest", "cursor-agent", "claude", "antigravity", "caffeinate -dimsu"]

    for target in targets:
        logger.info(f"Killing '{target}' processes...")
        # Use pkill with full string matching
        subprocess.run(["pkill", "-f", target], check=False)

    logger.info("Cleanup complete.")


def get_agent_command(agent_type, prompt):
    """Returns the command list for the specified agent and prompt."""
    if agent_type == "cursor-agent":
        return [
            "cursor-agent",
            "--model",
            "gemini-3-flash",
            "--print",
            "--force",
            "--approve-mcps",
            prompt,
        ]
    elif agent_type == "claude":
        # Assuming 'claude' command for Claude Code
        return ["claude", "-p", prompt]
    elif agent_type == "antigravity":
        # Assuming 'antigravity' command
        return ["antigravity", prompt]
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")


def ensure_dir(path: pathlib.Path):
    if not path.exists():
        logger.info(f"Creating directory: {path}")
        path.mkdir(parents=True, exist_ok=True)


def check_env_health() -> bool:
    """Checks if the current environment is healthy and correctly configured."""
    config = load_config()
    env_config = config.get("env")
    
    # 1. Check if backend is importable
    try:
        import backend
        logger.debug("✅ 'backend' package is importable.")
    except ImportError:
        logger.warning("❌ 'backend' package is NOT importable. Project structure may be broken.")
        return False

    # 2. Check for essential tools
    missing_tools = []
    
    # Backend tools
    for tool in ["python3", "pip", "ruff", "pytest"]:
        _, code = run_command([tool, "--version"], check=False)
        if code != 0:
            missing_tools.append(tool)
            
    # Frontend tools (if frontend directory exists)
    if pathlib.Path("frontend").exists():
        for tool in ["node", "npm", "npx"]:
            _, code = run_command([tool, "--version"], check=False)
            if code != 0:
                missing_tools.append(tool)
                
    if missing_tools:
        logger.warning(f"❌ Missing essential tools: {', '.join(missing_tools)}")
        return False

    # 3. Check for package structure
    if pathlib.Path("backend").exists() and not (pathlib.Path("backend") / "__init__.py").exists():
        logger.warning("❌ Missing 'backend/__init__.py'.")
        return False
        
    if not pathlib.Path("vibe_data").exists():
        logger.warning("❌ Missing local data directory 'vibe_data/'.")
        return False

    # 4. If managed env is configured, check if we're in it
    if env_config:
        venv_name = env_config.get("venv_name")
        if venv_name:
            current_prefix = sys.prefix
            # If we are running via pipx, the sys.prefix will be the pipx venv
            # but we want to know if the *active* pyenv environment is correct
            # or if we are at least in a context where the project venv is intended
            if "pipx" in current_prefix:
                # We are running globally via pipx. We should check if the 
                # user has activated their project venv or if we are in the project dir
                # For now, let's look at the PYENV_VERSION or similar env vars
                import os
                pyenv_version = os.environ.get("PYENV_VERSION") or os.environ.get("VIRTUAL_ENV")
                if venv_name not in str(pyenv_version) and venv_name not in current_prefix:
                    logger.warning(f"⚠️  Managed environment '{venv_name}' is configured but not active.")
                    logger.warning(f"   Note: You are running 'vibe' via pipx global install.")
                    logger.warning(f"   Please run 'pyenv activate {venv_name}' or ensure it's set in .python-version")
                    return False
            elif venv_name not in current_prefix:
                logger.warning(f"⚠️  Managed environment '{venv_name}' is configured but not active.")
                logger.warning(f"   Current environment: {current_prefix}")
                return False
            
            logger.debug(f"✅ Environment check passed.")

    return True


def get_file_hash(filepath: pathlib.Path) -> Optional[str]:
    """Returns the SHA256 hash of a file."""
    if not filepath.exists():
        return None
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def is_git_repo():
    try:
        # Check if we are inside a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # git command not found
        return False


def get_main_branch():
    """Returns 'main' or 'master' depending on which one exists."""
    _, code = run_command(["git", "rev-parse", "--verify", "main"], check=False)
    if code == 0:
        return "main"
    _, code = run_command(["git", "rev-parse", "--verify", "master"], check=False)
    if code == 0:
        return "master"
    return "main"  # Default fallback


def get_changed_files(base_branch=None):
    """Returns files changed relative to the base branch."""
    if not is_git_repo():
        return []

    if base_branch is None:
        base_branch = get_main_branch()
    if code != 0:
        merge_base = base_branch
    else:
        merge_base = stdout.strip() or base_branch

    stdout, code = run_command(["git", "diff", "--name-only", merge_base], check=False)
    if code != 0:
        changed = []
    else:
        changed = stdout.strip().splitlines() if stdout.strip() else []

    stdout, code = run_command(["git", "ls-files", "--others", "--exclude-standard"], check=False)
    if code == 0 and stdout.strip():
        changed.extend(stdout.strip().splitlines())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for path in changed:
        if path and path not in seen:
            seen.add(path)
            unique.append(path)

    return unique


def is_dirty():
    """Checks if the repository has uncommitted changes or untracked files."""
    if not is_git_repo():
        return False
    # Check for tracked changes
    _, code = run_command(["git", "diff", "--quiet"], check=False)
    if code != 0:
        return True
    _, code = run_command(["git", "diff", "--cached", "--quiet"], check=False)
    if code != 0:
        return True
    # Check for untracked files
    stdout, code = run_command(
        ["git", "ls-files", "--others", "--exclude-standard"], check=False
    )
    return bool(stdout.strip())


def ensure_gitignore(entry: str):
    """Ensures that a specific entry exists in .gitignore."""
    gitignore = pathlib.Path(".gitignore")
    if not gitignore.exists():
        gitignore.write_text(f"{entry}\n")
        logger.info(f"Added {entry} to new .gitignore")
        return

    content = gitignore.read_text()
    if entry not in content.splitlines():
        with gitignore.open("a") as f:
            f.write(f"\n{entry}\n")
        logger.info(f"Added {entry} to .gitignore")


def sync_env_file():
    """Generates or updates the .env file based on the current configuration."""
    config = load_config()
    services = config.get("services", {})
    env_lines = []

    # 1. Database (Postgres)
    pg = services.get("postgres")
    if pg:
        env_lines.append(f"DB_HOST={pg.get('host', 'localhost')}")
        env_lines.append(f"DB_PORT={pg.get('port', 5432)}")
        env_lines.append(f"DB_USER={pg.get('user', 'postgres')}")
        env_lines.append(f"DB_PASSWORD={pg.get('password', 'postgres')}")
        env_lines.append(f"DB_NAME={pg.get('database', get_project_name())}")
        # Tortoise-ORM compatible URL
        db_url = f"postgres://{pg.get('user')}:{pg.get('password')}@{pg.get('host')}:{pg.get('port')}/{pg.get('database')}"
        env_lines.append(f"DATABASE_URL={db_url}")
        env_lines.append("")

    # 2. Redis
    redis = services.get("redis")
    if redis:
        env_lines.append(f"REDIS_HOST={redis.get('host', 'localhost')}")
        env_lines.append(f"REDIS_PORT={redis.get('port', 6379)}")
        password = redis.get('password', '')
        env_lines.append(f"REDIS_PASSWORD={password}")
        env_lines.append(f"REDIS_DB={redis.get('database', 0)}")
        redis_url = f"redis://{':' + password + '@' if password else ''}{redis.get('host')}:{redis.get('port')}/{redis.get('database')}"
        env_lines.append(f"REDIS_URL={redis_url}")
        env_lines.append("")

    # 3. Google API Key
    google_key = get_google_api_key()
    if google_key:
        env_lines.append(f"GOOGLE_API_KEY={google_key}")
        env_lines.append("")

    # 4. Local Storage
    vibe_data = pathlib.Path("vibe_data")
    if vibe_data.exists():
        env_lines.append(f"VIBE_DATA_DIR={vibe_data.absolute()}")
        env_lines.append("")

    # 5. S3 / Object Store
    s3_linode = services.get("s3-linode")
    s3_aws = services.get("s3-aws")
    s3 = s3_linode or s3_aws
    if s3:
        env_lines.append(f"S3_HOST={s3.get('host')}")
        env_lines.append(f"S3_PORT={s3.get('port')}")
        env_lines.append(f"S3_ACCESS_KEY={s3.get('access_key')}")
        env_lines.append(f"S3_SECRET_KEY={s3.get('secret_key')}")
        env_lines.append(f"S3_REGION={s3.get('region')}")
        env_lines.append("")

    # 5. RabbitMQ
    rmq = services.get("rabbitmq")
    if rmq:
        env_lines.append(f"RABBITMQ_HOST={rmq.get('host')}")
        env_lines.append(f"RABBITMQ_PORT={rmq.get('port')}")
        env_lines.append(f"RABBITMQ_USER={rmq.get('user')}")
        env_lines.append(f"RABBITMQ_PASSWORD={rmq.get('password')}")
        env_lines.append("")

    # Write to .env
    env_file = pathlib.Path(".env")
    if env_lines:
        content = "# Generated by vibe-setup\n" + "\n".join(env_lines)
        env_file.write_text(content)
        ensure_gitignore(".env")
        logger.info(f"✅ Updated {env_file} with current service configuration.")


def collect_prd_files():
    """Returns all PRD files in PRD_DIR starting with prd_."""
    return sorted(list(PRD_DIR.glob("prd_*.yaml")), key=lambda path: path.name)


def get_instructions_context():
    """Reads all files in INSTRUCTIONS_DIR and returns them as a formatted string."""
    if not INSTRUCTIONS_DIR.exists():
        return ""

    sections = []
    for f in sorted(INSTRUCTIONS_DIR.glob("*")):
        if f.is_file():
            content = f.read_text().strip()
            if content:
                sections.append(f"--- {f.name} ---\n{content}")

    if not sections:
        return ""

    return "INSTRUCTIONS:\n" + "\n\n".join(sections)


def get_latest_context_file(pattern):
    """Finds the latest file matching the pattern in PRD_DIR recursively."""
    # Handle the pattern to be more flexible (e.g. "infra_*.yaml" -> "prd_infra_*.yaml")
    search_pattern = pattern
    if not search_pattern.startswith("prd_") and not search_pattern.startswith("*"):
        search_pattern = f"prd_{search_pattern}"

    files = list(PRD_DIR.rglob(search_pattern))
    if not files:
        return "NOT FOUND"

    # Sort by name (which includes the ## prefix)
    latest = sorted(files)[-1]
    return latest.read_text()


def get_vibe_status_report():
    """Generates a comprehensive status report of the system."""
    import click
    from vibe_tools.cost import get_total_cost
    from vibe_tools.servers import get_server_configs, get_container_status
    
    state = load_project_state()
    report = []
    report.append(click.style("\n=== VIBE PROJECT STATUS ===", fg="cyan", bold=True))

    # 1. Lifecycle Progress
    report.append(click.style("\nLIFECYCLE PROGRESS:", fg="yellow", bold=True))
    phases = state.get("phases", {})
    order = ["setup", "normalize", "plan", "implement", "infra", "cicd", "testing", "deploy"]
    
    next_action = None
    for phase_id in order:
        phase = phases.get(phase_id, {})
        status = phase.get("status", "pending")
        
        if status == "completed":
            status_display = click.style("✅ DONE", fg="green")
        elif status == "in_progress":
            status_display = click.style("⏳ IN_PROGRESS", fg="blue")
            if not next_action:
                next_action = f"vibe {phase_id}"
        else:
            status_display = click.style("⚪ PENDING", fg="white", dim=True)
            if not next_action:
                next_action = f"vibe {phase_id}"
        
        report.append(f"  - {phase_id:<15} {status_display}")

    # 2. Next Steps
    if next_action:
        report.append(click.style("\nNEXT SUGGESTED ACTION:", fg="green", bold=True))
        report.append(f"  > {next_action}")

    # 3. Project Info
    project_name = state.get("project_name", get_project_name())
    report.append(f"\n{click.style('PROJECT:', bold=True)} {project_name}")
    report.append(f"{click.style('DIRECTORY:', bold=True)} {pathlib.Path.cwd()}")

    # 4. PRD Progress (Detailed)
    report.append(click.style("\nPRD FILES:", fg="yellow", bold=True))
    all_prds = collect_prd_files()
    completed_prds = state.get("completed_prds", [])
    started_prds = state.get("started_prds", [])

    if not all_prds:
        report.append("  No PRDs found in prds/")
    else:
        for prd in all_prds:
            name = prd.stem
            if name in completed_prds:
                status = click.style("✅ DONE", fg="green")
            elif name in started_prds:
                status = click.style("⏳ IN_PROGRESS", fg="blue")
            else:
                status = click.style("⚪ PENDING", fg="white", dim=True)
            report.append(f"  - {name:<40} {status}")

    # 5. Costs
    total_cost = get_total_cost()
    report.append(click.style("\nCOSTS:", fg="yellow", bold=True))
    report.append(f"  Total Estimated Project Cost: {click.style(f'${total_cost:.4f} USD', fg='green')}")

    # 6. Services
    report.append(click.style("\nSERVICES:", fg="yellow", bold=True))
    configs = get_server_configs()
    if not configs:
        report.append("  No services configured.")
    else:
        for name, config in configs.items():
            status = get_container_status(config["container_name"])
            if status == "running":
                status_display = click.style("✅ Running", fg="green")
            elif status == "exited":
                status_display = click.style("🛑 Stopped", fg="red")
            else:
                status_display = click.style("⚪ Not Installed", fg="white", dim=True)
            
            ports = ", ".join([f"{v}" for k, v in config.get("ports", {}).items()])
            report.append(f"  - {name:<15} {status_display:<20} {ports}")

    report.append("")
    return "\n".join(report)

    report.append("")
    return "\n".join(report)
