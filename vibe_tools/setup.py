import datetime
import pathlib
import socket
import subprocess
from typing import Any, Dict, Optional

import click
from dotenv import find_dotenv, load_dotenv

# Load environment variables from .env file at startup
load_dotenv(find_dotenv() or ".env")

from vibe_tools.templates import TEMPLATES
from vibe_tools.utils import (
    CONFIG_FILE,
    ensure_dir,
    ensure_gitignore,
    get_agent_command,
    get_automerge_branch,
    get_google_api_key,
    get_main_branch,
    get_project_name,
    load_config,
    load_project_state,
    run_agent,
    run_command,
    save_config,
    save_google_api_key,
    save_project_state,
)

SERVICE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "postgres": {
        "display": "PostgreSQL",
        "default_port": 5432,
        "docker_keywords": [
            "postgres",
            "postgresql",
            "pgvector",
            "pg15",
            "pg16",
            "pg17",
        ],
        "fields": [
            {"name": "host", "prompt": "Postgres host", "default": "localhost"},
            {"name": "port", "prompt": "Postgres port", "type": int, "default": 5432},
            {"name": "user", "prompt": "Postgres user", "default": "postgres"},
            {
                "name": "password",
                "prompt": "Postgres password",
                "default": "postgres",
                "hide_input": True,
            },
            {
                "name": "database",
                "prompt": "Postgres database name",
                "default": get_project_name(),
            },
        ],
    },
    "redis": {
        "display": "Redis",
        "default_port": 6379,
        "docker_keywords": ["redis"],
        "fields": [
            {"name": "host", "prompt": "Redis host", "default": "localhost"},
            {"name": "port", "prompt": "Redis port", "type": int, "default": 6379},
            {
                "name": "password",
                "prompt": "Redis password (leave blank if none)",
                "default": "",
                "hide_input": True,
            },
            {
                "name": "database",
                "prompt": "Redis database number",
                "type": int,
                "default": 0,
            },
        ],
    },
    "rabbitmq": {
        "display": "RabbitMQ",
        "default_port": 5672,
        "docker_keywords": ["rabbitmq"],
        "fields": [
            {"name": "host", "prompt": "RabbitMQ host", "default": "localhost"},
            {
                "name": "port",
                "prompt": "RabbitMQ port",
                "type": int,
                "default": 5672,
            },
            {"name": "user", "prompt": "RabbitMQ username", "default": "guest"},
            {
                "name": "password",
                "prompt": "RabbitMQ password",
                "default": "guest",
                "hide_input": True,
            },
            {
                "name": "virtual_host",
                "prompt": "RabbitMQ virtual host",
                "default": "/",
            },
        ],
    },
    "elasticsearch": {
        "display": "Elasticsearch",
        "default_port": 9200,
        "docker_keywords": ["elasticsearch", "elastic"],
        "fields": [
            {"name": "host", "prompt": "Elasticsearch host", "default": "localhost"},
            {
                "name": "port",
                "prompt": "Elasticsearch port",
                "type": int,
                "default": 9200,
            },
            {"name": "scheme", "prompt": "Elasticsearch scheme", "default": "http"},
            {"name": "username", "prompt": "Elasticsearch username", "default": ""},
            {
                "name": "password",
                "prompt": "Elasticsearch password",
                "default": "",
                "hide_input": True,
            },
        ],
    },
    "mailhog": {
        "display": "MailHog",
        "default_port": 1025,
        "docker_keywords": ["mailhog"],
        "fields": [
            {"name": "host", "prompt": "MailHog host", "default": "localhost"},
            {
                "name": "port",
                "prompt": "MailHog SMTP port",
                "type": int,
                "default": 1025,
            },
            {
                "name": "web_port",
                "prompt": "MailHog Web port",
                "type": int,
                "default": 8025,
            },
        ],
    },
    "s3-linode": {
        "display": "S3 Object Store (MinIO/Linode)",
        "default_port": 9000,
        "docker_keywords": ["minio"],
        "fields": [
            {"name": "host", "prompt": "S3 host", "default": "localhost"},
            {"name": "port", "prompt": "S3 port", "type": int, "default": 9000},
            {"name": "access_key", "prompt": "S3 Access Key", "default": "minioadmin"},
            {
                "name": "secret_key",
                "prompt": "S3 Secret Key",
                "default": "minioadmin",
                "hide_input": True,
            },
            {"name": "region", "prompt": "S3 Region", "default": "us-east-1"},
            {
                "name": "addressing_style",
                "prompt": "Addressing Style (path/virtual)",
                "default": "path",
            },
            {
                "name": "signature_version",
                "prompt": "Signature Version",
                "default": "s3v4",
            },
            {
                "name": "console_port",
                "prompt": "S3 Console port",
                "type": int,
                "default": 9001,
            },
        ],
    },
    "s3-aws": {
        "display": "S3 Object Store (MinIO/AWS)",
        "default_port": 9010,
        "docker_keywords": ["minio"],
        "fields": [
            {"name": "host", "prompt": "S3 host", "default": "localhost"},
            {"name": "port", "prompt": "S3 port", "type": int, "default": 9010},
            {"name": "access_key", "prompt": "S3 Access Key", "default": "minioadmin"},
            {
                "name": "secret_key",
                "prompt": "S3 Secret Key",
                "default": "minioadmin",
                "hide_input": True,
            },
            {"name": "region", "prompt": "S3 Region", "default": "us-east-1"},
            {
                "name": "addressing_style",
                "prompt": "Addressing Style (path/virtual)",
                "default": "virtual",
            },
            {
                "name": "signature_version",
                "prompt": "Signature Version",
                "default": "s3v4",
            },
            {
                "name": "console_port",
                "prompt": "S3 Console port",
                "type": int,
                "default": 9011,
            },
        ],
    },
    "imgproxy": {
        "display": "imgproxy",
        "default_port": 8080,
        "docker_keywords": ["imgproxy"],
        "fields": [
            {"name": "host", "prompt": "imgproxy host", "default": "localhost"},
            {"name": "port", "prompt": "imgproxy port", "type": int, "default": 8080},
        ],
    },
}


def _parse_docker_port_mapping(ports: str, target_port: int) -> Optional[str]:
    if not ports:
        return None
    for candidate in ports.split(","):
        candidate = candidate.strip()
        if "->" not in candidate:
            continue
        host_part, container_part = candidate.split("->", 1)
        container_port = container_part.split("/")[0].strip()
        if not container_port.isdigit():
            continue
        if int(container_port) != target_port:
            continue
        host_port = host_part.split(":")[-1].strip()
        if host_port:
            return host_port
    return None


def detect_docker_service(service_key: str) -> Dict[str, Any]:
    metadata = SERVICE_DEFINITIONS.get(service_key)
    if not metadata:
        return {}

    try:
        output, _ = run_command(
            ["docker", "ps", "--format", "{{.Names}}||{{.Image}}||{{.Ports}}"],
            check=False,
        )
    except FileNotFoundError:
        return {}

    if not output:
        return {}

    candidates = []
    for line in output.splitlines():
        if not line:
            continue
        parts = line.split("||", maxsplit=2)
        if len(parts) != 3:
            continue
        container_name, image, ports = parts
        mapped_port = _parse_docker_port_mapping(ports, metadata["default_port"])

        info = {
            "container_name": container_name,
            "image": image,
            "host": "localhost",
            "port": int(mapped_port) if mapped_port else metadata["default_port"],
            "mapped": bool(mapped_port),
        }

        # Check for keyword match
        searchable = f"{container_name} {image}".lower()
        if any(keyword in searchable for keyword in metadata["docker_keywords"]):
            # Strong match: keyword + port mapping
            if info["mapped"]:
                return info
            # Decent match: keyword match only
            candidates.append(info)
        elif info["mapped"]:
            # Fallback match: port mapping matches service's default_port
            candidates.append(info)

    return candidates[0] if candidates else {}


def prompt_service_config(service_key: str) -> Dict[str, Any]:
    metadata = SERVICE_DEFINITIONS[service_key]
    click.echo(f"\n--- {metadata['display']} Setup ---")

    detection = detect_docker_service(service_key)
    if detection.get("container_name"):
        click.echo(
            f"Detected Docker container '{detection['container_name']}' for {metadata['display']} "
            f"(defaulting to {detection['host']}:{detection['port']})."
        )

    responses: Dict[str, Any] = {}
    for field in metadata["fields"]:
        default_value = detection.get(field["name"])
        if default_value is None:
            default_value = field.get("default")
        prompt_args = {
            "default": default_value,
            "hide_input": field.get("hide_input", False),
            "type": field.get("type", str),
        }
        responses[field["name"]] = click.prompt(field["prompt"], **prompt_args)

    if detection.get("container_name"):
        responses["docker_container_name"] = detection["container_name"]

    return responses


def check_connection(service_key: str, details: Dict[str, Any]) -> bool:
    """Verifies if a service is reachable."""
    host = details.get("host", "localhost")
    port = details.get("port")
    if not port:
        return False

    # Special handling for HTTP-based services
    if service_key == "elasticsearch":
        scheme = details.get("scheme", "http")
        url = f"{scheme}://{host}:{port}"
        try:
            import httpx

            with httpx.Client(timeout=2.0) as client:
                # Basic check for ES - it should return a 200 with JSON
                response = client.get(url)
                return response.status_code == 200
        except Exception:
            # Fall back to socket check if httpx fails or is missing
            pass

    try:
        with socket.create_connection((host, int(port)), timeout=2.0):
            return True
    except (OSError, ValueError):
        return False


def configure_service(service_key: str):
    metadata = SERVICE_DEFINITIONS[service_key]
    config = load_config()
    details = prompt_service_config(service_key)

    click.echo(f"Checking connection to {metadata['display']}...")
    if check_connection(service_key, details):
        click.echo("✅ Connection successful!")
    else:
        click.echo(
            f"⚠️  Warning: Could not connect to {metadata['display']} at {details.get('host')}:{details.get('port')}."
        )
        if not click.confirm("Save configuration anyway?", default=True):
            click.echo("Aborted.")
            return

    services = config.setdefault("services", {})
    services[service_key] = details
    save_config(config)
    click.echo(f"✅ {metadata['display']} configuration saved to {CONFIG_FILE}")

    # Sync .env after any service configuration
    from vibe_tools.utils import sync_env_file

    sync_env_file()


def maybe_init_git():
    from vibe_tools.utils import is_git_repo

    if not is_git_repo():
        if click.confirm(
            "\nNo git repository found. Would you like to initialize one?", default=True
        ):
            try:
                subprocess.run(["git", "init"], check=True)
                click.echo("✅ Initialized empty Git repository.")
                ensure_gitignore(".vibe_config.json")
                ensure_gitignore("logs/")
            except Exception as e:
                click.echo(f"❌ Failed to initialize Git repository: {e}")


@click.group()
def setup_cli():
    """Setup and configuration tools for vibe."""
    pass


@setup_cli.command()
def test():
    """Verify connectivity for all configured services."""
    config = load_config()
    services = config.get("services", {})

    if not services:
        click.echo("No services configured. Run 'vibe-setup <service>' first.")
        return

    click.echo("\n--- Service Connectivity Test ---")
    for service_key, details in services.items():
        metadata = SERVICE_DEFINITIONS.get(service_key, {})
        display = metadata.get("display", service_key.capitalize())

        click.echo(f"{display:<15}: ", nl=False)
        if check_connection(service_key, details):
            click.echo("✅ Connected")
        else:
            host = details.get("host", "unknown")
            port = details.get("port", "unknown")
            click.echo(f"❌ Failed (could not reach {host}:{port})")


@setup_cli.command()
@click.pass_context
def dspy(ctx):
    """Verify DSPy integration and LLM connectivity."""
    click.echo("\n--- DSPy Integration Test ---")

    api_key = get_google_api_key()
    if not api_key:
        click.echo("❌ Google API Key is missing.")
        if click.confirm("Would you like to configure it now?", default=True):
            ctx.invoke(api)
            # Reload environment after saving key
            from dotenv import load_dotenv, find_dotenv

            load_dotenv(find_dotenv() or ".env", override=True)
            api_key = get_google_api_key()
        else:
            click.echo("Aborted.")
            return

    if not api_key:
        click.echo("❌ Still no API key found. Cannot proceed with test.")
        return

    click.echo("⏳ Making test call to LLM via DSPy library...")
    try:
        from vibe_tools.utils import run_llm

        test_prompt = "Hello, this is a connectivity test. Please respond with the word 'READY' and nothing else."
        response = run_llm(test_prompt)

        click.echo(f"🤖 Agent Response: {response}")
        if "READY" in response.upper():
            click.echo("✅ DSPy Integration: SUCCESS")
        else:
            click.echo(
                "⚠️  DSPy Integration: PARTIAL (Response received but didn't match expectation)"
            )

    except Exception as e:
        click.echo(f"❌ DSPy Integration: FAILED")
        click.echo(f"\nError Details:\n{str(e)}")

        # Check for common issues
        if "quota" in str(e).lower():
            click.echo("\n💡 Hint: Your Google AI Studio quota might be exceeded.")
        elif "api_key" in str(e).lower() or "unauthorized" in str(e).lower():
            click.echo(
                "\n💡 Hint: Your API key might be invalid. Run 'vibe-setup api' to reset it."
            )
        elif "module" in str(e).lower():
            click.echo("\n💡 Hint: Ensure 'dspy-ai' is installed in your environment.")


@setup_cli.command()
def api():
    """Configure API keys for LLM access."""
    click.echo("\n--- API Key Configuration ---")

    current_google_key = get_google_api_key() or ""
    new_google_key = click.prompt(
        "Enter Google API Key (for Gemini/DSPy)",
        default=current_google_key,
        hide_input=True,
    )

    if new_google_key:
        save_google_api_key(new_google_key)
        # Also ensure it's removed from the old location in .vibe_config.json if present
        config = load_config()
        if "google_api_key" in config:
            del config["google_api_key"]
            save_config(config)
        click.echo(
            "✅ Google API Key saved to .env (and removed from .vibe_config.json)"
        )
    else:
        click.echo("⏩ Google API Key skipped.")


@setup_cli.command()
def google():
    """Set up Google Sheets connection for cost logging."""
    click.echo("\n--- Google Sheets Setup ---")

    config = load_config()
    current_use = config.get("use_google_sheets", False)

    use_google = click.confirm(
        "Enable logging costs to Google Sheets?", default=current_use
    )
    config["use_google_sheets"] = use_google

    if not use_google:
        save_config(config)
        click.echo("✅ Google Sheets logging disabled.")
        return

    click.echo("\nTo log costs to Google Sheets, you need to configure access.")

    current_id = config.get("google_sheet_id", "")
    click.echo("\nThe Sheet ID is the long string in the Google Sheet URL:")
    click.echo("https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit")
    new_id = click.prompt(
        "Enter Google Sheet ID (or the Sheet Name)", default=current_id
    )

    if not new_id:
        click.echo("Operation cancelled.")
        return

    config["google_sheet_id"] = new_id
    save_config(config)
    click.echo(f"✅ Google Sheet ID saved to {CONFIG_FILE}")

    click.echo("\nChoose authentication method:")
    click.echo("1. Browser Login (Recommended - uses your Google account)")
    click.echo("2. Service Account (Requires JSON key file)")

    choice = click.prompt("Select option", type=int, default=1)

    if choice == 1:
        click.echo("\n--- Browser Login Setup ---")
        client_secrets_path = pathlib.Path(".vibe_client_secrets.json")
        authorized_user_path = pathlib.Path(".vibe_authorized_user.json")

        if not client_secrets_path.exists():
            click.echo(
                "1. Go to Google Cloud Console (https://console.cloud.google.com)."
            )
            click.echo("2. Create a Project (or select an existing one).")
            click.echo(
                "3. In 'APIs & Services' > 'Library', enable 'Google Sheets API'."
            )
            click.echo(
                "4. In 'APIs & Services' > 'Google Auth Platform' (or OAuth consent screen):"
            )
            click.echo("   - Under 'Branding': Set your App Name and support email.")
            click.echo(
                "   - Under 'Audience': Set User Type (External) and add your email to 'Test users'."
            )
            click.echo(
                "   - Under 'Data Access': Add the 'Google Sheets API' scope (../auth/spreadsheets)."
            )
            click.echo("5. Under 'Clients': Click 'Create Client' > 'OAuth client ID'.")
            click.echo("6. Choose 'Desktop App', name it, and download the JSON file.")
            click.echo(
                f"7. Rename it to '{client_secrets_path}' and place it in this directory."
            )

            if not click.confirm("\nHave you placed the file?", default=False):
                click.echo("Aborted. Please place the file and run again.")
                return

        if client_secrets_path.exists():
            try:
                import gspread

                click.echo("\nAttempting browser login...")
                # This will open the browser for authentication
                gspread.oauth(
                    credentials_filename=str(client_secrets_path),
                    authorized_user_filename=str(authorized_user_path),
                )
                click.echo(
                    f"✅ Browser login successful. Tokens saved to {authorized_user_path}"
                )
            except Exception as e:
                click.echo(f"❌ Login failed: {e}")
        else:
            click.echo(f"❌ {client_secrets_path} not found.")

    elif choice == 2:
        click.echo("\n--- Service Account Setup ---")
        click.echo("1. A Google Cloud Project with the Google Sheets API enabled.")
        click.echo(
            "2. A Service Account with a JSON key saved as '.vibe_google_creds.json'."
        )
        click.echo(
            "3. The Service Account email shared with the Google Sheet (Editor access)."
        )

        creds_path = pathlib.Path(".vibe_google_creds.json")
        if not creds_path.exists():
            click.echo(
                f"\n⚠️  Reminder: Please place your service account key at {creds_path}"
            )
        else:
            click.echo(f"✅ Found {creds_path}")
    else:
        click.echo("Invalid choice.")


def ensure_infrastructure():
    """Ensure that the required project infrastructure (directories and files) exists."""
    from vibe_tools.utils import VIBE_DATA_DIR, ensure_gitignore

    # 1. Create storage directory
    if not VIBE_DATA_DIR.exists():
        click.echo(f"Creating storage directory: {VIBE_DATA_DIR}")
        VIBE_DATA_DIR.mkdir(parents=True, exist_ok=True)
        ensure_gitignore(str(VIBE_DATA_DIR) + "/*")


def install_deps():
    """Logic to install required Python and Frontend dependencies."""
    # Ensure basic infrastructure is present
    ensure_infrastructure()

    # If we are on main branch, switch to a dependencies branch
    current_branch, _ = run_command(["git", "branch", "--show-current"], check=False)
    main_branch = get_main_branch()

    config = load_config()
    deps_branch_enabled = config.get("setup", {}).get("deps_branch_enabled", True)

    if current_branch.strip() == main_branch and deps_branch_enabled:
        from vibe_tools.ralph import _switch_to_branch

        if config.get("ralph", {}).get("auto_merge", False):
            target_branch = get_automerge_branch(config)
        else:
            target_branch = "vibe/dependencies"

        _switch_to_branch(target_branch, agent="internal", project_name="dependencies")

    click.echo("\n--- Installing Dependencies ---")

    # 1. Always install essential tools for the loop
    click.echo("Installing essential tools (ruff, pytest, mypy)...")
    run_command(
        ["pip", "install", "ruff", "pytest", "pytest-cov", "mypy"], caffeinate=True
    )

    # 2. Project-specific Python dependencies
    if pathlib.Path("pyproject.toml").exists():
        click.echo("Found pyproject.toml. Installing in editable mode...")
        run_command(["pip", "install", "-e", "."], caffeinate=True)
    elif pathlib.Path("backend/requirements.txt").exists():
        click.echo("Found backend/requirements.txt. Installing...")
        run_command(
            ["pip", "install", "-r", "backend/requirements.txt"], caffeinate=True
        )
    elif pathlib.Path("requirements.txt").exists():
        click.echo("Found requirements.txt. Installing...")
        run_command(["pip", "install", "-r", "requirements.txt"], caffeinate=True)

    # 3. Frontend dependencies
    if pathlib.Path("frontend/package.json").exists():
        click.echo("Found frontend/package.json. Installing npm dependencies...")
        run_command(["npm", "install", "--prefix", "frontend"], caffeinate=True)

    # Update project state to mark deps as completed
    state = load_project_state()
    state["phases"]["deps"]["status"] = "completed"
    save_project_state(state)


@setup_cli.command()
def deps():
    """Install required Python and Frontend dependencies."""
    install_deps()
    click.echo("✅ Dependencies installed.")


@setup_cli.command()
@click.option("--python-version", default="3.11.10", help="Python version to install")
def env(python_version):
    """Set up and verify a managed Python environment."""
    click.echo(f"\n--- Environment Setup & Verification (Python {python_version}) ---")

    config = load_config()
    env_config = config.get("env")

    # If env is already configured, verify it
    if env_config:
        from vibe_tools.utils import check_env_health

        if check_env_health():
            click.echo("✅ Current environment is healthy and correctly configured.")
            if not click.confirm("Re-run full setup anyway?", default=False):
                return
        else:
            click.echo("⚠️  Current environment verification failed.")
            if not click.confirm(
                "Attempt to fix/re-setup the environment?", default=True
            ):
                return

    # 1. Check for Homebrew
    try:
        subprocess.run(["brew", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo("❌ Homebrew not found. Please install it from https://brew.sh/")
        return

    # 2. Check for pyenv
    try:
        subprocess.run(["pyenv", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        if click.confirm("pyenv not found. Install it via Homebrew?", default=True):
            run_command(["brew", "install", "pyenv"])
        else:
            return

    # 3. Check for pyenv-virtualenv
    try:
        subprocess.run(
            ["pyenv", "virtualenv", "--version"], check=True, capture_output=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        if click.confirm(
            "pyenv-virtualenv not found. Install it via Homebrew?", default=True
        ):
            run_command(["brew", "install", "pyenv-virtualenv"])
        else:
            return

    # 4. Install Python version
    click.echo(f"Checking for Python {python_version}...")
    output, code = run_command(["pyenv", "versions"], check=False)
    if python_version not in output:
        click.echo(
            f"Installing Python {python_version} (this may take a few minutes)..."
        )
        run_command(["pyenv", "install", python_version], caffeinate=True)
    else:
        click.echo(f"✅ Python {python_version} already installed.")

    # 5. Create Virtualenv
    project_name = get_project_name().replace("_", "-")
    venv_name = f"{project_name}-{python_version}"

    output, code = run_command(["pyenv", "virtualenvs"], check=False)
    if venv_name not in output:
        click.echo(f"Creating virtualenv '{venv_name}'...")
        run_command(["pyenv", "virtualenv", python_version, venv_name])
    else:
        click.echo(f"✅ Virtualenv '{venv_name}' already exists.")

    # 6. Set local version
    click.echo(f"Setting local python version to {venv_name}...")
    run_command(["pyenv", "local", venv_name])

    # 7. Initialize Project Infrastructure
    ensure_infrastructure()

    # 8. Install dependencies
    click.echo("\nInstalling dependencies...")
    # Call the deps command directly
    try:
        install_deps()
    except Exception as e:
        click.echo(f"⚠️ Warning: Failed to install dependencies: {e}")

    # 9. Record in config
    config = load_config()
    config["env"] = {
        "type": "pyenv-virtualenv",
        "python_version": python_version,
        "venv_name": venv_name,
        "path": str(pathlib.Path.cwd()),
        "last_setup": datetime.datetime.now().isoformat(),
    }
    save_config(config)

    # 9. Sync .env file
    from vibe_tools.utils import sync_env_file

    sync_env_file()

    click.echo(f"\n✅ Environment setup complete and recorded in {CONFIG_FILE}")
    click.echo(f"Virtualenv: {venv_name}")
    click.echo(
        "\nTo ensure your shell is configured for pyenv, add these to your ~/.zshrc or ~/.bash_profile:"
    )
    click.echo('  export PYENV_ROOT="$HOME/.pyenv"')
    click.echo('  [[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"')
    click.echo('  eval "$(pyenv init -)"')
    click.echo('  eval "$(pyenv virtualenv-init -)"')


@setup_cli.command()
def postgres():
    """Collect PostgreSQL connection details."""
    configure_service("postgres")


@setup_cli.command()
def redis():
    """Collect Redis connection details."""
    configure_service("redis")


@setup_cli.command()
def rabbitmq():
    """Collect RabbitMQ connection details."""
    configure_service("rabbitmq")


@setup_cli.command()
def elasticsearch():
    """Collect Elasticsearch connection details."""
    configure_service("elasticsearch")


@setup_cli.command()
def mailhog():
    """Collect MailHog connection details."""
    configure_service("mailhog")


@setup_cli.command()
def s3_linode():
    """Collect S3 Linode Object Store connection details."""
    configure_service("s3-linode")


@setup_cli.command()
def s3_aws():
    """Collect S3 AWS Object Store connection details."""
    configure_service("s3-aws")


@setup_cli.command()
def imgproxy():
    """Collect imgproxy connection details."""
    configure_service("imgproxy")


@setup_cli.command(name="eject-prompts")
def eject_prompts():
    """Extract all system prompts from templates.py and save them to the prompts/ directory."""
    prompts_dir = pathlib.Path("prompts")
    ensure_dir(prompts_dir)

    click.echo(f"\n--- Ejecting Prompts to {prompts_dir}/ ---")

    count = 0
    for filename, content in TEMPLATES.items():
        if filename in [
            "dummy_backend_test",
            "dummy_frontend_test",
            "Makefile",
            "README",
        ]:
            continue

        file_path = prompts_dir / filename
        if file_path.exists():
            click.echo(f"⏩ Skipping {filename} (already exists)")
            continue

        click.echo(f"✅ Ejecting {filename}...")
        file_path.write_text(content)
        count += 1

    click.echo(
        f"\nFinished! {count} prompts ejected. You can now edit them in the 'prompts/' directory."
    )
    click.echo(
        "Files in 'prompts/' will override the system defaults in 'templates.py'."
    )


@setup_cli.command()
@click.pass_context
def scaffold(ctx):
    """Generate build scaffolding (build.md, build.yaml, Makefile, Dockerfiles, etc.)."""
    from vibe_tools.utils import (
        ARCHITECTURE_SPEC,
        BUILD,
        BUILD_SPEC,
        ensure_dir,
        get_agent_command,
        run_agent,
    )
    from vibe_tools.normalize import normalize_prd

    click.echo("\n--- Build Scaffolding Setup ---")

    # Ensure project structure
    ensure_infrastructure()

    # Get agent settings (defaults if not in context)
    agent = getattr(ctx.obj, "agent", "cursor-agent") if ctx.obj else "cursor-agent"
    stream = getattr(ctx.obj, "stream", False) if ctx.obj else False
    caffeinate = getattr(ctx.obj, "caffeinate", False) if ctx.obj else False

    # Check if build.md already exists
    if BUILD_SPEC.exists():
        click.echo(f"✅ {BUILD_SPEC} already exists.")
        if not click.confirm("Regenerate build.md?", default=False):
            click.echo("Skipping build.md generation.")
        else:
            # Regenerate
            _generate_build_spec(agent, stream)
    else:
        # Generate build.md from architecture
        if not ARCHITECTURE_SPEC.exists():
            click.echo(
                f"❌ {ARCHITECTURE_SPEC} not found. Please create it first using 'vibe architect'."
            )
            return

        _generate_build_spec(agent, stream)

    # Normalize build.md to build.yaml if needed
    if BUILD_SPEC.exists() and not BUILD.exists():
        click.echo("🔄 Normalizing build.md to build.yaml...")

        normalize_prd(
            agent=agent,
            input_file=str(BUILD_SPEC),
            auto_overwrite=True,
            caffeinate=caffeinate,
            stream=stream,
        )

        if BUILD.exists():
            click.echo("✅ Build specification normalized successfully.")
        else:
            click.echo(
                "❌ Normalization failed. Please review and fix build.md, then run 'vibe normalize' manually."
            )
            return

    # Check and install build tools
    _check_and_install_build_tools()

    click.echo("\n✅ Build scaffolding complete.")
    click.echo("Next steps:")
    click.echo("  - Review specs/build.md and project/build.yaml")
    click.echo("  - Run 'vibe build' to build and test the application")


def _generate_build_spec(agent, stream):
    """Generate build.md from architecture.md."""
    from vibe_tools.utils import (
        ARCHITECTURE_SPEC,
        BUILD_SPEC,
        ensure_dir,
        get_agent_command,
        run_agent,
    )

    if not ARCHITECTURE_SPEC.exists():
        click.echo(
            f"❌ {ARCHITECTURE_SPEC} not found. Please create it first using 'vibe architect'."
        )
        return

    click.echo("📋 Generating build.md from architecture.md...")

    # Read architecture.md
    arch_content = ARCHITECTURE_SPEC.read_text()

    # Generate build.md using agent
    prompt = f"""You are generating a build specification based on the architecture.

Analyze the architecture and create a comprehensive build.md file that specifies:
- How to build each application part (backend, frontend, etc.)
- Build dependencies and requirements
- Build commands and scripts
- Development environment setup
- How to start the application in development mode
- Build artifacts and outputs
- Services that need to be started for development

IMPORTANT REQUIREMENTS:
1. **Makefile Targets**: ALWAYS include a comprehensive set of Makefile targets for:
   - Building: `make build`, `make build-backend`, `make build-frontend`
   - Testing: `make test`, `make test-backend`, `make test-frontend`
   - Development: `make dev`, `make dev-start`, `make dev-stop`, `make dev-restart`
   - Linting: `make lint`, `make lint-backend`, `make lint-frontend`
   - Coverage: `make coverage`, `make coverage-backend`, `make coverage-frontend`
   - Cleanup: `make clean`, `make clean-backend`, `make clean-frontend`

2. **Skaffold and Helm**: If the architecture uses Kubernetes or container orchestration:
   - Include Skaffold configuration for local Kubernetes development
   - Include Helm charts for deployment
   - Document how to use `skaffold dev` for local development
   - Document Helm chart structure and values
   - IMPORTANT: When generating skaffold.yaml, ensure it includes `defaultRepo: ""` under the `build:` section to prevent push access errors
   - IMPORTANT: If generating frontend Dockerfiles (e.g., deployment/Dockerfile.frontend), use node:20-slim or node:22-slim (not node:18-slim) to support modern Vite versions (7.3.0+ requires Node.js 20.19+ or 22.12+)

3. **Logging Solution**: ALWAYS include a comprehensive logging solution:
   - **Log Aggregation**: Set up a log aggregation service (e.g., Loki, ELK stack, or simpler file-based logging)
   - **Log Storage**: Configure log storage location (local files, centralized service, or cloud logging)
   - **Log Viewing**: Include tools/commands to view logs (e.g., `make logs`, `make logs-backend`, `make logs-frontend`, `make logs-follow`)
   - **Log Management**: Add Makefile targets for log management:
     * `make logs` - View all application logs
     * `make logs-backend` - View backend logs
     * `make logs-frontend` - View frontend logs
     * `make logs-follow` - Follow logs in real-time
     * `make logs-clean` - Clean old log files
   - **Service Integration**: Ensure all services output logs in a structured format (JSON recommended)
   - **Development Logging**: Configure development environment to output logs to both console and log files
   - **Log Levels**: Document log level configuration (DEBUG, INFO, WARNING, ERROR)
   - If using Docker/Kubernetes: Configure log drivers and log collection
   - If using Skaffold: Include logging configuration in skaffold.yaml

4. **Services Section**: Clearly list all services/components that need to run in development mode with their startup commands.

The architecture specification is in specs/architecture.md:

{arch_content}

Generate a complete build.md file following this structure:

# Build Specification

## 1. Overview
[High-level overview of the build system and how different parts are built. Mention if using Skaffold/Helm for Kubernetes-based development.]

## 2. Build Components
[For each component (backend, frontend, etc.), specify:
- Build commands
- Dependencies
- Build outputs/artifacts
- How to verify the build succeeded]

## 3. Development Environment

### 3.1 Services Required
[List all services that must be running for development (PostgreSQL, Redis, etc.)]

### 3.2 Environment Variables
[Required environment variables and .env file setup]

### 3.3 Startup Commands
[Detailed startup commands for each service/component. Include both manual commands and Makefile targets.]

### 3.4 Logging
[Comprehensive logging solution setup:
- Log aggregation service and configuration
- Log storage location and retention policies
- How to view logs (commands and tools)
- Log format and structure
- Log level configuration
- Integration with services]

### 3.5 Verification
[How to verify the development environment is running correctly]

## 4. Build System

### 4.1 Makefile Targets
[COMPREHENSIVE list of all Makefile targets. MUST include:
- Build targets: build, build-backend, build-frontend
- Test targets: test, test-backend, test-frontend, test-integration
- Development targets: dev, dev-start, dev-stop, dev-restart
- Lint targets: lint, lint-backend, lint-frontend
- Coverage targets: coverage, coverage-backend, coverage-frontend
- Clean targets: clean, clean-backend, clean-frontend
- Install targets: install, install-backend, install-frontend
- Log targets: logs, logs-backend, logs-frontend, logs-follow, logs-clean]

### 4.2 Container Orchestration
[If using Kubernetes:
- Skaffold configuration and usage (`skaffold dev`, `skaffold run`)
- Helm chart structure and deployment
- Local cluster setup (Minikube/Kind) instructions]

### 4.3 Docker Builds
[Docker build commands and Dockerfile locations if applicable]

### 4.4 CI/CD Build Steps
[CI/CD pipeline steps and automation]

Output ONLY the markdown content for build.md, starting with the title and ending with the last section. Do not include code fences or explanations.
"""

    cmd = get_agent_command(agent, prompt)
    output, code = run_agent(cmd, stream=stream)

    if code != 0 or not output.strip():
        click.echo(
            "❌ Failed to generate build.md. Please create it manually using 'vibe architect'."
        )
        return

    # Clean output (remove code fences if present)
    clean_output = output.strip()
    if clean_output.startswith("```"):
        lines = clean_output.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_output = "\n".join(lines).strip()

    # Write build.md
    ensure_dir(BUILD_SPEC.parent)
    BUILD_SPEC.write_text(clean_output)
    click.echo(f"✅ Generated {BUILD_SPEC}")


def _check_and_install_build_tools():
    """Check for required build tools (skaffold, helm) and install if missing."""
    import platform
    import shutil
    import subprocess

    from vibe_tools.utils import run_command

    required_tools = {}

    # Check if skaffold.yaml exists
    skaffold_yaml = pathlib.Path("skaffold.yaml")
    if skaffold_yaml.exists():
        required_tools["skaffold"] = {
            "check_cmd": ["skaffold", "version"],
            "install_cmd_brew": ["brew", "install", "skaffold"],
            "install_cmd_linux": [
                "curl",
                "-Lo",
                "skaffold",
                "https://storage.googleapis.com/skaffold/releases/latest/skaffold-linux-amd64",
                "&&",
                "sudo",
                "install",
                "skaffold",
                "/usr/local/bin/",
            ],
            "description": "Skaffold (Kubernetes development tool)",
        }

    # Check if helm charts exist
    helm_paths = [
        pathlib.Path("deployment/helm"),
        pathlib.Path("helm"),
        pathlib.Path("charts"),
    ]
    has_helm = any(p.exists() for p in helm_paths)

    if has_helm:
        required_tools["helm"] = {
            "check_cmd": ["helm", "version"],
            "install_cmd_brew": ["brew", "install", "helm"],
            "install_cmd_linux": [
                "curl",
                "https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3",
                "|",
                "bash",
            ],
            "description": "Helm (Kubernetes package manager)",
        }

    if not required_tools:
        return

    click.echo("🔍 Checking for required build tools...")

    for tool_name, tool_info in required_tools.items():
        # Check if tool is installed
        try:
            result = run_command(tool_info["check_cmd"], check=False)
            if result[1] == 0:
                click.echo(f"  ✅ {tool_info['description']} is installed")
                continue
        except Exception:
            pass

        # Tool is not installed
        click.echo(f"  ⚠️  {tool_info['description']} is not installed")

        # Determine OS and install method
        system = platform.system().lower()
        is_macos = system == "darwin"

        if is_macos:
            # Try brew first
            if shutil.which("brew"):
                click.echo(f"  📦 Installing {tool_name} using Homebrew...")
                try:
                    install_cmd = tool_info["install_cmd_brew"]
                    result = run_command(install_cmd, check=False)
                    if result[1] == 0:
                        click.echo(f"  ✅ {tool_name} installed successfully")
                        continue
                    else:
                        click.echo(f"  ⚠️  Homebrew installation failed: {result[0]}")
                except Exception as e:
                    click.echo(f"  ⚠️  Installation error: {e}")
            else:
                click.echo(f"  💡 Install {tool_name} manually:")
                click.echo(f"     brew install {tool_name}")
        else:
            # Linux - provide manual instructions
            click.echo(f"  💡 Install {tool_name} manually:")
            if tool_name == "skaffold":
                click.echo(
                    "     curl -Lo skaffold https://storage.googleapis.com/skaffold/releases/latest/skaffold-linux-amd64"
                )
                click.echo("     sudo install skaffold /usr/local/bin/")
            elif tool_name == "helm":
                click.echo(
                    "     curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
                )

        # Verify installation
        click.echo(f"  🔍 Verifying {tool_name} installation...")
        try:
            result = run_command(tool_info["check_cmd"], check=False)
            if result[1] == 0:
                click.echo(f"  ✅ {tool_name} is now available")
            else:
                click.echo(f"  ⚠️  {tool_name} installation verification failed")
                click.echo(
                    f"     Please install it manually and run 'vibe-setup scaffold' again"
                )
        except Exception:
            click.echo(f"  ⚠️  Could not verify {tool_name} installation")


if __name__ == "__main__":
    setup_cli()
