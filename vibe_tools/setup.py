import os
import pathlib
import re
import shutil
import socket
import subprocess
import tempfile
import time
import datetime
import json
from typing import Any, Dict, List, Optional

import click
from dotenv import find_dotenv, load_dotenv

from vibe_tools.templates import TEMPLATES
from vibe_tools.utils import (
    CONFIG_FILE,
    ensure_dir,
    get_agent_command,
    get_automerge_branch,
    get_cursor_api_key,
    get_google_api_key,
    get_main_branch,
    get_project_name,
    is_tool_available,
    load_config,
    run_agent,
    run_command,
    save_config,
    save_google_api_key,
    save_cursor_api_key,
    safe_yaml_dump,
    check_and_install_build_tools,
    ensure_project_structure,
)

# Load environment variables from .env file at startup
load_dotenv(find_dotenv() or ".env")

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


def check_prerequisites() -> Dict[str, Dict[str, Any]]:
    """Checks for all system prerequisites and returns a status map."""
    from vibe_tools.utils import run_command

    results = {
        "git": {"status": False, "message": "Not installed"},
        "gh": {"status": False, "message": "Not installed"},
        "gemini": {"status": False, "message": "API Key missing"},
        "agent": {
            "status": False,
            "message": "No agent found (cursor-agent or claude)",
        },
    }

    # 1. Check Git
    if is_tool_available("git"):
        name, _ = run_command(["git", "config", "user.name"], check=False)
        email, _ = run_command(["git", "config", "user.email"], check=False)
        if name.strip() and email.strip():
            results["git"] = {"status": True, "message": f"Found ({name.strip()})"}
        else:
            results["git"] = {
                "status": False,
                "message": "Git installed but not configured (user.name/email)",
            }

    # 2. Check GitHub CLI
    if is_tool_available("gh"):
        stdout, code = run_command(["gh", "auth", "status"], check=False)
        if code == 0 and "Logged in" in stdout:
            results["gh"] = {"status": True, "message": "Logged in"}
        else:
            results["gh"] = {
                "status": False,
                "message": "Installed but not authenticated",
            }

    # 3. Check Gemini API Key
    api_key = get_google_api_key()
    if api_key:
        results["gemini"] = {"status": True, "message": "API Key configured"}

    # 4. Check Agents
    agents = []
    if is_tool_available("cursor-agent"):
        agents.append("cursor-agent")
    if is_tool_available("claude"):
        agents.append("claude")

    if agents:
        results["agent"] = {"status": True, "message": f"Found: {', '.join(agents)}"}

    return results


def guide_setup():
    """Interactively guides the user to set up missing prerequisites."""
    click.echo(click.style("\n🔍 Checking system prerequisites...", fg="cyan"))

    while True:
        prereqs = check_prerequisites()
        all_pass = True

        click.echo("")
        for key, info in prereqs.items():
            icon = (
                click.style("✅", fg="green")
                if info["status"]
                else click.style("❌", fg="red")
            )
            click.echo(f"  {icon} {key.upper():<10} : {info['message']}")
            if not info["status"]:
                all_pass = False

        if all_pass:
            click.echo(
                click.style("\n✨ All prerequisites met!", fg="green", bold=True)
            )
            return True

        click.echo(
            click.style(
                "\n⚠️  Some prerequisites are missing or misconfigured.", fg="yellow"
            )
        )

        if not prereqs["git"]["status"]:
            if prereqs["git"]["message"] == "Not installed":
                click.echo(
                    "  - Git is required. Please install it: https://git-scm.com/"
                )
            else:
                if click.confirm(
                    "  - Configure Git user name and email now?", default=True
                ):
                    name = click.prompt("    Enter your name")
                    email = click.prompt("    Enter your email")
                    run_command(["git", "config", "--global", "user.name", name])
                    run_command(["git", "config", "--global", "user.email", email])
                    continue

        if not prereqs["gh"]["status"]:
            if prereqs["gh"]["message"] == "Not installed":
                click.echo("  - GitHub CLI is recommended. Install it: brew install gh")
            else:
                if click.confirm("  - Login to GitHub now?", default=True):
                    subprocess.run(["gh", "auth", "login"])
                    continue

        if not prereqs["gemini"]["status"]:
            if click.confirm("  - Configure Google Gemini API Key now?", default=True):
                api_key = click.prompt("    Enter Gemini API Key", hide_input=True)
                if api_key:
                    save_google_api_key(api_key)
                    continue

        if not prereqs["agent"]["status"]:
            click.echo("  - An AI agent is required for most features.")
            click.echo("    Install cursor-agent: npm install -g @cursor-agent/cli")
            click.echo("    Or Claude Code: npm install -g @anthropic-ai/claude-code")

        if not click.confirm(
            "\nPrerequisites are still missing. Try again after fixing?", default=True
        ):
            return False


def sync_makefile(agent: str = "cursor-agent", stream: bool = False):
    """Sync the Makefile with the development environment and architecture specifications."""
    # Early health check for the agent
    from vibe_tools.agent import verify_agent_auth
    success, message = verify_agent_auth(agent)
    if not success:
        click.echo(click.style(message, fg="red", bold=True))
        return

    from vibe_tools.utils import (
        ARCHITECTURE_SPEC,
        DEV_SPEC,
        run_llm,
    )

    if not DEV_SPEC.exists():
        click.echo(f"⚠️  {DEV_SPEC} not found. Skipping Makefile sync.")
        return

    click.echo("🔄 Syncing Makefile with project specifications (via Gemini)...")

    dev_spec_content = DEV_SPEC.read_text()
    arch_spec_content = (
        ARCHITECTURE_SPEC.read_text() if ARCHITECTURE_SPEC.exists() else ""
    )

    # Check if Makefile exists, if not use template
    makefile_path = pathlib.Path("Makefile")
    current_makefile = ""
    if makefile_path.exists():
        current_makefile = makefile_path.read_text()
    else:
        from vibe_tools.templates import TEMPLATES

        current_makefile = TEMPLATES.get("Makefile", "")

    prompt = f"""You are a Makefile Expert and Project Scaffolder. 
Your task is to generate a clean, professional Makefile that focuses on build, test, lint, and development environment management.

RELEVANT SPECIFICATIONS:
---
DEVELOPMENT ENVIRONMENT:
{dev_spec_content}

ARCHITECTURE & CORE COMMANDS:
{arch_spec_content}
---

CURRENT MAKEFILE (for reference only):
---
{current_makefile}
---

TASK:
1. Create a definitive Makefile that includes targets for building, testing, and running the development environment.
2. Mandatory sections to include:
   - .PHONY declaration for all targets.
   - Build targets (e.g., build, build-cli, build-desktop).
   - Test targets (e.g., test, test-cli, test-desktop).
   - Development targets (e.g., dev, dev-desktop, install-deps).
   - Linting & Quality targets.
   - Utility targets (e.g., clean, logs).
3. EXCLUDE: Do NOT add simple wrappers for 'vibe' commands (e.g., do not add 'pm: vibe pm'). These are already available via the CLI.
4. Ensure a top-level 'help' target exists that dynamically lists all targets using '##' comments.
5. Set 'help' as the default target (via '.DEFAULT_GOAL := help').
6. All targets MUST have a '##' description on the same line to be picked up by the help command.
7. Target Naming: Use concise, intuitive names.
8. CRITICAL: Avoid any redundancy. Each target should appear exactly once.
9. CRITICAL: Do NOT simply append to the current Makefile. Produce a fresh, unified output.
10. Use standard Makefile syntax (tabs for indentation).
11. Output ONLY the raw Makefile content. No markdown code fences, no '```makefile' tags, no headers.

Output ONLY the raw Makefile content.
"""

    output = run_llm(prompt)

    if output and output.strip():
        # Extraction logic: find the first .PHONY or first target
        # If the agent is messy, we try to find the cleanest block
        clean_output = output.strip()

        # Remove any leading/trailing garbage common in messy LLM outputs
        if "--- FINAL RESULT ---" in clean_output:
            clean_output = clean_output.split("--- FINAL RESULT ---")[-1].strip()

        if "```" in clean_output:
            # Extract content between code fences if present
            match = re.search(
                r"```(?:makefile)?\s*([\s\S]*?)\s*```", clean_output, re.IGNORECASE
            )
            if match:
                clean_output = match.group(1).strip()
            else:
                # Fallback: just strip the fences
                clean_output = (
                    clean_output.replace("```makefile", "").replace("```", "").strip()
                )

        # Final sanitization: ensure it looks like a Makefile (starts with .PHONY or a target)
        lines = clean_output.splitlines()
        valid_start = -1
        for i, line in enumerate(lines):
            if line.startswith(".PHONY:") or (
                ":" in line and not line.startswith("\t") and not line.startswith(" ")
            ):
                valid_start = i
                break

        if valid_start != -1:
            clean_output = "\n".join(lines[valid_start:]).strip()

        makefile_path.write_text(clean_output)
        click.echo("✅ Makefile updated successfully.")
    else:
        click.echo("❌ Failed to sync Makefile.")


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
        click.echo("No services configured. Run 'vibe config <service>' first.")
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


@setup_cli.command(name="llm")
@click.pass_context
def llm(ctx):
    """Verify Gemini integration and LLM connectivity."""
    click.echo("\n--- Gemini Integration Test ---")

    api_key = get_google_api_key()
    if not api_key:
        click.echo("❌ Google API Key is missing.")
        if click.confirm("Would you like to configure it now?", default=True):
            ctx.invoke(api)
            # Reload environment after saving key
            from dotenv import find_dotenv, load_dotenv

            load_dotenv(find_dotenv() or ".env", override=True)
            api_key = get_google_api_key()
        else:
            click.echo("Aborted.")
            return

    if not api_key:
        click.echo("❌ Still no API key found. Cannot proceed with test.")
        return

    click.echo("⏳ Making test call to LLM via google-genai library...")
    try:
        from vibe_tools.utils import run_llm

        test_prompt = "Hello, this is a connectivity test. Please respond with the word 'READY' and nothing else."
        response = run_llm(test_prompt)

        click.echo(f"🤖 Agent Response: {response}")
        if "READY" in response.upper():
            click.echo("✅ Gemini Integration: SUCCESS")
        else:
            click.echo(
                "⚠️  Gemini Integration: PARTIAL (Response received but didn't match expectation)"
            )

    except Exception as e:
        click.echo("❌ Gemini Integration: FAILED")
        click.echo(f"\nError Details:\n{str(e)}")

        # Check for common issues
        if "quota" in str(e).lower():
            click.echo("\n💡 Hint: Your Google AI Studio quota might be exceeded.")
        elif "api_key" in str(e).lower() or "unauthorized" in str(e).lower():
            click.echo(
                "\n💡 Hint: Your API key might be invalid. Run 'vibe config api' to reset it."
            )
        elif "module" in str(e).lower():
            click.echo(
                "\n💡 Hint: Ensure 'google-genai' is installed in your environment."
            )


@setup_cli.command(name="dspy", hidden=True)
@click.pass_context
def dspy_alias(ctx):
    """Alias for 'llm' command."""
    ctx.invoke(llm)


@setup_cli.command()
def api():
    """Configure API keys for LLM access."""
    click.echo("\n--- API Key Configuration ---")

    # 1. Google API Key
    current_google_key = get_google_api_key() or ""
    new_google_key = click.prompt(
        "Enter Google API Key (for Gemini/google-genai)",
        default=current_google_key,
        hide_input=True,
    )

    if new_google_key:
        save_google_api_key(new_google_key)
        # Also ensure it's removed from the old location in config.json if present
        config = load_config()
        if "google_api_key" in config:
            del config["google_api_key"]
            save_config(config)
        click.echo("✅ Google API Key saved to .env")
    else:
        click.echo("⏩ Google API Key skipped.")

    # 2. Cursor API Key
    current_cursor_key = get_cursor_api_key() or ""
    new_cursor_key = click.prompt(
        "Enter Cursor API Key (for direct usage/stats)",
        default=current_cursor_key,
        hide_input=True,
    )

    if new_cursor_key:
        save_cursor_api_key(new_cursor_key)
        click.echo("✅ Cursor API Key saved to .env")
    else:
        click.echo("⏩ Cursor API Key skipped.")


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
    from vibe_tools.utils import VIBE_DATA_DIR

    # 1. Create storage directory
    if not VIBE_DATA_DIR.exists():
        click.echo(f"Creating storage directory: {VIBE_DATA_DIR}")
        VIBE_DATA_DIR.mkdir(parents=True, exist_ok=True)


def install_deps(
    only_makefile: bool = False,
    only_python: bool = False,
    only_frontend: bool = False,
):
    """Logic to install required Python and Frontend dependencies."""
    # If any specific flag is set, we only run those
    run_all = not (only_makefile or only_python or only_frontend)

    # 1. Sync Makefile
    if run_all or only_makefile:
        sync_makefile()
        if only_makefile:
            return

    # Ensure basic infrastructure is present
    click.echo("📁 Ensuring project infrastructure...")
    ensure_infrastructure()

    # If we are on main branch, switch to a dependencies branch
    current_branch, _ = run_command(["git", "branch", "--show-current"], check=False)
    main_branch = get_main_branch()

    config = load_config()
    deps_branch_enabled = config.get("setup", {}).get("deps_branch_enabled", True)

    if current_branch.strip() == main_branch and deps_branch_enabled:
        click.echo(f"🌿 On {main_branch} branch. Switching to a dependency management branch...")
        from vibe_tools.ralph import _switch_to_branch

        if config.get("ralph", {}).get("auto_merge", False):
            target_branch = get_automerge_branch(config)
        else:
            target_branch = "vibe/dependencies"

        _switch_to_branch(target_branch, agent="internal", project_name="dependencies")

    click.echo("\n--- Installing Dependencies ---")

    # 2. Always install essential tools for the loop
    if run_all or only_python:
        click.echo("Installing essential tools (ruff, pytest, mypy)...")
        run_command(["pip", "install", "ruff", "pytest", "pytest-cov", "mypy"])

    # Project-specific Python dependencies
    if pathlib.Path("pyproject.toml").exists():
        standalone = config.get("setup", {}).get("standalone", True)
        if standalone:
            click.echo("Found pyproject.toml. Installing in standalone mode...")
            run_command(["pip", "install", "."])
        else:
            click.echo("Found pyproject.toml. Installing in editable mode...")
            run_command(["pip", "install", "-e", "."])
    elif pathlib.Path("requirements.txt").exists():
        click.echo("Found requirements.txt. Installing...")
        run_command(["pip", "install", "-r", "requirements.txt"])

    # 3. Frontend dependencies
    if run_all or only_frontend:
        if pathlib.Path("frontend/package.json").exists():
            click.echo("Found frontend/package.json. Installing npm dependencies...")

            # Ensure TypeScript configuration exists if missing
            tsconfig = pathlib.Path("frontend/tsconfig.json")
            tsconfig_node = pathlib.Path("frontend/tsconfig.node.json")

            if not tsconfig.exists():
                click.echo("Creating missing frontend/tsconfig.json...")
                tsconfig.write_text(TEMPLATES.get("tsconfig.json", ""))

            if not tsconfig_node.exists():
                click.echo("Creating missing frontend/tsconfig.node.json...")
                tsconfig_node.write_text(TEMPLATES.get("tsconfig.node.json", ""))

            # Using --legacy-peer-deps to handle common React 18 ecosystem conflicts
            run_command(
                ["npm", "install", "--prefix", "frontend", "--legacy-peer-deps"]
            )


@setup_cli.command()
@click.option("--name", default="local", help="Name of the environment to set up")
@click.option("--python-version", default="3.11.10", help="Python version to install")
def env(name, python_version):
    """Set up and verify a managed Python environment."""
    click.echo(
        f"\n--- Environment Setup & Verification: {name} (Python {python_version}) ---"
    )

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
            _run_infra_cmd(["brew", "install", "pyenv"])
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
            _run_infra_cmd(["brew", "install", "pyenv-virtualenv"])
        else:
            return

    # 4. Install Python version
    click.echo(f"Checking for Python {python_version}...")
    output, code = run_command(["pyenv", "versions"], check=False)
    if python_version not in output:
        click.echo(
            f"Installing Python {python_version} (this may take a few minutes)..."
        )
        run_command(["pyenv", "install", python_version])
    else:
        click.echo(f"✅ Python {python_version} already installed.")

    # 5. Create Virtualenv
    project_name = get_project_name().replace("_", "-")
    venv_name = f"{project_name}-{python_version}-{name}"

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

    click.echo(f"\n✅ Environment setup complete: {name}")
    click.echo(f"Virtualenv: {venv_name}")
    click.echo(
        "\nTo ensure your shell is configured for pyenv (safer macOS config), add these to your ~/.zshrc:"
    )
    click.echo('  export PYENV_ROOT="$HOME/.pyenv"')
    click.echo('  [[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"')
    click.echo('  eval "$(pyenv init --path)"')
    click.echo('  eval "$(pyenv init -)"')
    click.echo(
        '  # Note: Avoid "pyenv virtualenv-init" on macOS to prevent fork exhaustion.'
    )


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


@setup_cli.command(name="desktop-init")
def desktop_init():
    """Initialize the global ~/.vibe-tools directory and default files."""
    from vibe_tools.utils import (
        GLOBAL_VIBE_TOOLS_DIR,
        PROJECTS_REGISTRY_FILE,
        GlobalProjectRegistry,
    )

    click.echo(f"\n--- Global Environment Setup (~/.vibe-tools) ---")

    # 1. Ensure directory exists
    ensure_dir(GLOBAL_VIBE_TOOLS_DIR)
    click.echo(f"✅ Directory exists: {GLOBAL_VIBE_TOOLS_DIR}")

    # 2. Ensure projects.json exists
    if not PROJECTS_REGISTRY_FILE.exists():
        GlobalProjectRegistry.save({"projects": [], "last_active_project_id": None})
        click.echo(f"✅ Created projects registry: {PROJECTS_REGISTRY_FILE}")
    else:
        click.echo(f"✅ Projects registry already exists: {PROJECTS_REGISTRY_FILE}")

    # 3. Setup default templates
    templates_dir = GLOBAL_VIBE_TOOLS_DIR / "templates"
    ensure_dir(templates_dir)

    # Eject some basic prompts if they don't exist
    from vibe_tools.templates import TEMPLATES

    count = 0
    for filename, content in TEMPLATES.items():
        if filename.endswith(".txt"):
            target_file = templates_dir / filename
            if not target_file.exists():
                target_file.write_text(content)
                count += 1

    if count > 0:
        click.echo(f"✅ Initialized {count} default templates in {templates_dir}")
    else:
        click.echo(f"✅ Templates already exist in {templates_dir}")

    click.echo("\n✨ Global setup complete!")


@setup_cli.command()
@click.pass_context
def scaffold(ctx):
    """Generate development environment scaffolding (SRD-dev_environment.md, Makefile, Dockerfiles, etc.)."""
    from vibe_tools.utils import (
        ARCHITECTURE_SPEC,
        DEV_SPEC,
    )

    click.echo("\n--- Development Environment Scaffolding Setup ---")

    # Ensure project structure
    ensure_infrastructure()

    # Get agent settings (defaults if not in context)
    agent = getattr(ctx.obj, "agent", "cursor-agent") if ctx.obj else "cursor-agent"
    stream = getattr(ctx.obj, "stream", False) if ctx.obj else False

    # Detect architecture to customize scaffolding
    arch_info = _detect_architecture(agent, stream)
    is_k8s = arch_info["type"] == "kubernetes"

    if is_k8s:
        click.echo(click.style("🌐 Kubernetes architecture detected.", fg="cyan"))
    elif arch_info["type"] == "tauri":
        click.echo(click.style("🖥️  Tauri architecture detected.", fg="cyan"))
    else:
        click.echo(
            click.style(
                f"🛠️  {arch_info['type'].capitalize()} architecture detected.", fg="cyan"
            )
        )

    # Check if SRD-dev_environment.md already exists
    if DEV_SPEC.exists():
        click.echo(f"\n✅ {DEV_SPEC} already exists.")
        if not click.confirm(
            f"Regenerate SRD-dev_environment.md? (This will overwrite your current file with {arch_info['type']}-optimized instructions)",
            default=False,
        ):
            click.echo("Aborted.")
            return

        # Regenerate
        _generate_dev_spec(agent, stream, arch_info)
    else:
        # Generate SRD-dev_environment.md from architecture
        if not ARCHITECTURE_SPEC.exists():
            click.echo(
                f"❌ {ARCHITECTURE_SPEC} not found. Please create it first using 'vibe architect'."
            )
            return

        _generate_dev_spec(agent, stream, arch_info)

    # Conditionally install build tools if docker/k8s is involved
    if is_k8s or "docker" in arch_info["capabilities"]:
        check_and_install_build_tools()

    # Setup logging infrastructure ONLY if Kubernetes is detected
    if is_k8s:
        try:
            _setup_logging_infrastructure()
        except click.ClickException as e:
            click.echo(f"\n❌ Logging infrastructure setup failed: {e}")
            click.echo(
                "   Continuing with scaffold, but logging will not be available."
            )
        except Exception as e:
            click.echo(f"\n⚠️  Logging infrastructure setup encountered an error: {e}")
            click.echo(
                "   Continuing with scaffold, but logging may not be fully configured."
            )
    else:
        click.echo("\nℹ️  Skipping K8s logging setup (not a Kubernetes project).")

    # Sync Makefile with the newly generated SRD-dev_environment.md
    sync_makefile(agent=agent, stream=stream)

    click.echo("\n✅ Development environment scaffolding complete.")
    click.echo("Next steps:")
    click.echo(f"  - Review {DEV_SPEC}")
    click.echo("  - Run 'vibe build' to build and test the application")


def _detect_architecture(agent, stream) -> Dict[str, Any]:
    """Analyze SRD-architecture.md to detect project type and required capabilities."""
    from vibe_tools.utils import ARCHITECTURE_SPEC, run_llm

    if not ARCHITECTURE_SPEC.exists():
        return {"type": "unknown", "capabilities": []}

    arch_content = ARCHITECTURE_SPEC.read_text()

    prompt = f"""Analyze the following architecture specification and categorize the project.
Return a JSON object with two fields:
1. "type": One of ["kubernetes", "tauri", "cli", "web-standard", "other"]
2. "capabilities": A list of specific technologies detected (e.g., ["python", "react", "docker", "postgresql", "rust"])

ARCHITECTURE:
---
{arch_content}
---

Output ONLY valid JSON.
"""

    response = run_llm(prompt)
    if not response:
        return {"type": "unknown", "capabilities": []}

    # Extract JSON from response
    try:
        # Simple extraction in case of markdown fences
        json_match = re.search(r"(\{.*\})", response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        return json.loads(response)
    except (json.JSONDecodeError, AttributeError):
        # Fallback to simple keyword detection if LLM fails or returns garbage
        capabilities = []
        project_type = "cli"

        lower_content = arch_content.lower()
        if "kubernetes" in lower_content or "skaffold" in lower_content:
            project_type = "kubernetes"
        elif "tauri" in lower_content:
            project_type = "tauri"
        elif "react" in lower_content or "next.js" in lower_content:
            project_type = "web-standard"

        if "python" in lower_content:
            capabilities.append("python")
        if "rust" in lower_content:
            capabilities.append("rust")
        if "react" in lower_content:
            capabilities.append("react")
        if "docker" in lower_content:
            capabilities.append("docker")

        return {"type": project_type, "capabilities": capabilities}


def _generate_dev_spec(agent, stream, arch_info: Dict[str, Any]):
    """Generate SRD-dev_environment.md from SRD-architecture.md."""
    from vibe_tools.utils import (
        ARCHITECTURE_SPEC,
        DEV_SPEC,
        ensure_dir,
    )

    if not ARCHITECTURE_SPEC.exists():
        click.echo(
            f"❌ {ARCHITECTURE_SPEC} not found. Please create it first using 'vibe architect'."
        )
        return

    click.echo(
        f"📋 Generating SRD-dev_environment.md for {arch_info['type']} project..."
    )

    # Read SRD-architecture.md
    arch_content = ARCHITECTURE_SPEC.read_text()

    # Build specialized prompt instructions based on architecture type
    type_instructions = ""
    if arch_info["type"] == "kubernetes":
        type_instructions = """
2. **Skaffold and Helm**:
   - Include Skaffold configuration for local Kubernetes development
   - Include Helm charts for deployment
   - Document how to use `skaffold dev` for local development
   - IMPORTANT: When generating skaffold.yaml, ensure it includes `defaultRepo: ""` under the `build:` section
   - IMPORTANT: If generating frontend Dockerfiles, use node:20-slim or node:22-slim.

3. **Logging Solution (K8s-optimized)**:
   - **Quick Log Streaming (Stern)**: `stern .` to tail logs from all pods.
   - **Centralized Log Aggregation (Loki + Grafana)**: Aggregation service running in Kubernetes.
   - **AI-Queryable Logs**: Grafana HTTP API endpoint details.
"""
    elif arch_info["type"] == "tauri":
        type_instructions = """
2. **Tauri Development**:
   - Focus on `cargo tauri dev` for local development.
   - Specify build requirements for both Rust (Cargo) and Frontend (npm/pnpm/yarn).
   - Document how to handle sidecars if specified in the architecture.
   - Testing: Specify dual-test harness using `cargo test` and `vitest`.

3. **Logging Solution (Desktop/Local)**:
   - Focus on standard output and local log files.
   - Document where application logs are stored on different OS platforms.
   - Include `make logs` to tail local log files.
"""
    else:  # CLI, Web-Standard, or Other
        type_instructions = """
2. **Standard Development**:
   - Focus on local runtime environment (e.g., venv for Python, node_modules for JS).
   - Specify `make dev` or `npm run dev` for starting the application.
   - Document environment variable requirements in `.env`.

3. **Logging Solution (Standard)**:
   - Focus on structured logging to stdout/stderr.
   - Document log file locations if applicable.
   - Include `make logs` to tail logs.
"""

    # Generate SRD-dev_environment.md using agent
    prompt = f"""You are generating a development environment specification based on the architecture.

Analyze the architecture and create a comprehensive SRD-dev_environment.md file that specifies:
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
   - Log Targets: `make logs`, `make logs-follow`

{type_instructions}

4. **Services Section**: Clearly list all services/components that need to run in development mode with their startup commands.
   - For persistent services (like web servers or Tauri apps), include a `health_check_url` field (e.g., `health_check_url: http://localhost:1420`).
   - If a service is a Tauri app, explicitly mention its default dev URL (http://localhost:1420).

The architecture specification is in product/SRD-architecture.md:

{arch_content}

Generate a complete SRD-dev_environment.md file following this structure:

# Development Environment Specification

## 1. Overview
[High-level overview. Mention if using Skaffold/Helm or specialized tools like Tauri.]

## 2. Build Components
[For each component, specify build commands, dependencies, and outputs.]

## 3. Development Environment
### 3.1 Services Required
### 3.2 Environment Variables
### 3.3 Startup Commands
### 3.4 Logging
### 3.5 Verification

## 4. Build System
### 4.1 Makefile Targets
### 4.2 Build Orchestration [Skaffold/Tauri/Manual]
### 4.3 CI/CD Build Steps

Output ONLY the markdown content for SRD-dev_environment.md.
"""

    cmd = get_agent_command(agent, prompt)
    bypass_safety = bool(os.environ.get("VIBE_IGNORE_GIT_SAFETY"))
    output, code = run_agent(cmd, stream=stream, bypass_safety=bypass_safety)

    if code != 0 or not output.strip():
        click.echo(
            "❌ Failed to generate SRD-dev_environment.md. Please create it manually using 'vibe architect'."
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

    # Write SRD-dev_environment.md
    ensure_dir(DEV_SPEC.parent)
    DEV_SPEC.write_text(clean_output)
    click.echo(f"✅ Generated {DEV_SPEC}")


def _run_infra_cmd(*args, **kwargs):
    """Wrapper around run_command that bypasses git safety for infrastructure operations."""
    from vibe_tools.utils import run_command

    kwargs.setdefault("bypass_safety", True)
    return run_command(*args, **kwargs)


def _install_stern() -> bool:
    """Install Stern for live log tailing. Returns True if successful."""
    import platform

    run_command = _run_infra_cmd

    # Check if already installed
    result = run_command(["stern", "--version"], check=False)
    if result[1] == 0:
        click.echo("  ✅ Stern is already installed")
        return True

    click.echo("  📦 Installing Stern...")
    system = platform.system().lower()
    is_macos = system == "darwin"

    if is_macos:
        if shutil.which("brew"):
            try:
                result = run_command(["brew", "install", "stern"], check=False)
                if result[1] == 0:
                    click.echo("  ✅ Stern installed successfully")
                    return True
                else:
                    click.echo(f"  ⚠️  Homebrew installation failed: {result[0]}")
            except Exception as e:
                click.echo(f"  ⚠️  Installation error: {e}")
        else:
            click.echo("  💡 Install Stern manually: brew install stern")
            return False
    else:
        # Linux - download binary
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                binary_path = pathlib.Path(tmpdir) / "stern"
                download_cmd = [
                    "curl",
                    "-Lo",
                    str(binary_path),
                    "https://github.com/stern/stern/releases/latest/download/stern_linux_amd64",
                ]
                result = run_command(download_cmd, check=False)
                if result[1] == 0:
                    # Make executable and install
                    binary_path.chmod(0o755)
                    install_cmd = [
                        "sudo",
                        "mv",
                        str(binary_path),
                        "/usr/local/bin/stern",
                    ]
                    result = run_command(install_cmd, check=False)
                    if result[1] == 0:
                        click.echo("  ✅ Stern installed successfully")
                        return True
                    else:
                        click.echo(f"  ⚠️  Installation failed: {result[0]}")
                else:
                    click.echo(f"  ⚠️  Download failed: {result[0]}")
        except Exception as e:
            click.echo(f"  ⚠️  Installation error: {e}")

    # Verify installation
    result = run_command(["stern", "--version"], check=False)
    if result[1] == 0:
        click.echo("  ✅ Stern is now available")
        return True
    else:
        click.echo("  ⚠️  Stern installation verification failed")
        return False


def _ensure_helm_installed() -> bool:
    """Ensure Helm is installed. Returns True if available."""
    run_command = _run_infra_cmd

    result = run_command(["helm", "version"], check=False)
    if result[1] == 0:
        return True

    # Try to install via existing logic
    import platform

    system = platform.system().lower()
    is_macos = system == "darwin"

    if is_macos:
        if shutil.which("brew"):
            click.echo("  📦 Installing Helm using Homebrew...")
            result = run_command(["brew", "install", "helm"], check=False)
            if result[1] == 0:
                click.echo("  ✅ Helm installed successfully")
                return True
    else:
        click.echo("  💡 Install Helm manually:")
        click.echo(
            "     curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
        )

    # Verify
    result = run_command(["helm", "version"], check=False)
    return result[1] == 0


def _setup_helm_repos() -> bool:
    """Add Grafana and Loki Helm repos. Returns True if successful."""
    run_command = _run_infra_cmd

    repos = [
        ("grafana", "https://grafana.github.io/helm-charts"),
        ("prometheus-community", "https://prometheus-community.github.io/helm-charts"),
    ]

    for repo_name, repo_url in repos:
        click.echo(f"  📦 Adding Helm repo: {repo_name}...")
        result = run_command(["helm", "repo", "add", repo_name, repo_url], check=False)
        if result[1] != 0:
            # Repo might already exist, try update
            if "already exists" in result[0].lower():
                click.echo(f"  ℹ️  Repo {repo_name} already exists, updating...")
                result = run_command(["helm", "repo", "update", repo_name], check=False)
                if result[1] != 0:
                    click.echo(f"  ⚠️  Failed to update repo {repo_name}: {result[0]}")
                    return False
            else:
                click.echo(f"  ⚠️  Failed to add repo {repo_name}: {result[0]}")
                return False

    # Update all repos
    click.echo("  🔄 Updating Helm repos...")
    result = run_command(["helm", "repo", "update"], check=False)
    if result[1] != 0:
        click.echo(f"  ⚠️  Failed to update Helm repos: {result[0]}")
        return False

    return True


def _deploy_loki_stack() -> bool:
    """Deploy Loki, Promtail, and Grafana via Helm. Returns True if successful."""
    run_command = _run_infra_cmd

    namespace = "monitoring"

    # Create namespace if it doesn't exist
    click.echo(f"  📦 Creating namespace: {namespace}...")
    result = run_command(["kubectl", "create", "namespace", namespace], check=False)
    if result[1] != 0 and "already exists" not in result[0].lower():
        click.echo(f"  ⚠️  Failed to create namespace: {result[0]}")
        return False

    # Deploy Loki (single-binary mode, filesystem storage)
    click.echo("  📦 Deploying Loki...")
    loki_values = {
        "loki": {
            "auth_enabled": False,
            "commonConfig": {"replication_factor": 1},
            "storage": {"type": "filesystem"},
            "schemaConfig": {
                "configs": [
                    {
                        "from": "2024-01-01",
                        "store": "tsdb",
                        "object_store": "filesystem",
                        "schema": "v13",
                        "index": {"prefix": "index_", "period": "24h"},
                    }
                ]
            },
            "compactor": {
                "retention_enabled": True,
                "retention_delete_delay": "2h",
                "retention_delete_worker_count": 150,
            },
            "limits_config": {
                "retention_period": "72h",
                "per_stream_rate_limit": "10MB",
                "per_stream_rate_limit_burst": "20MB",
            },
        },
        "singleBinary": {"replicas": 1},
        "test": {"enabled": False},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(safe_yaml_dump(loki_values))
        loki_values_file = f.name

    try:
        result = run_command(
            [
                "helm",
                "upgrade",
                "--install",
                "loki",
                "grafana/loki",
                "--namespace",
                namespace,
                "--values",
                loki_values_file,
                "--wait",
                "--timeout",
                "5m",
            ],
            check=False,
        )
        if result[1] != 0:
            click.echo(f"  ⚠️  Loki deployment failed: {result[0]}")
            # Show pod logs for debugging
            click.echo("  📋 Checking Loki pod status...")
            result = run_command(
                [
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    namespace,
                    "-l",
                    "app.kubernetes.io/name=loki",
                ],
                check=False,
            )
            click.echo(result[0])
            result = run_command(
                [
                    "kubectl",
                    "logs",
                    "-n",
                    namespace,
                    "-l",
                    "app.kubernetes.io/name=loki",
                    "--tail=50",
                ],
                check=False,
            )
            if result[1] == 0:
                click.echo("  📋 Loki pod logs:")
                click.echo(result[0])
            return False
        click.echo("  ✅ Loki deployed")
    finally:
        pathlib.Path(loki_values_file).unlink(missing_ok=True)

    # Deploy Promtail (Kubernetes service discovery)
    click.echo("  📦 Deploying Promtail...")
    promtail_values = {
        "config": {
            "clients": [
                {
                    "url": f"http://loki.{namespace}.svc.cluster.local:3100/loki/api/v1/push"
                }
            ],
            "serverPort": 3101,
            "positions": {"filename": "/tmp/positions.yaml"},
        },
        "extraArgs": ["-config.expand-env=true"],
        "serviceAccount": {
            "create": True,
        },
        "rbac": {
            "create": True,
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(safe_yaml_dump(promtail_values))
        promtail_values_file = f.name

    try:
        result = run_command(
            [
                "helm",
                "upgrade",
                "--install",
                "promtail",
                "grafana/promtail",
                "--namespace",
                namespace,
                "--values",
                promtail_values_file,
                "--wait",
                "--timeout",
                "5m",
            ],
            check=False,
        )
        if result[1] != 0:
            click.echo(f"  ⚠️  Promtail deployment failed: {result[0]}")
            return False
        click.echo("  ✅ Promtail deployed")
    finally:
        pathlib.Path(promtail_values_file).unlink(missing_ok=True)

    # Deploy Grafana
    click.echo("  📦 Deploying Grafana...")
    grafana_values = {
        "adminUser": "admin",
        "adminPassword": "admin",  # Default for local dev, should be changed
        "service": {"type": "ClusterIP", "port": 3000},
        "datasources": {
            "datasources.yaml": {
                "apiVersion": 1,
                "datasources": [
                    {
                        "name": "Loki",
                        "type": "loki",
                        "access": "proxy",
                        "url": f"http://loki.{namespace}.svc.cluster.local:3100",
                        "isDefault": True,
                        "version": 1,
                        "editable": True,
                    }
                ],
            }
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(safe_yaml_dump(grafana_values))
        grafana_values_file = f.name

    try:
        result = run_command(
            [
                "helm",
                "upgrade",
                "--install",
                "grafana",
                "grafana/grafana",
                "--namespace",
                namespace,
                "--values",
                grafana_values_file,
                "--wait",
                "--timeout",
                "5m",
            ],
            check=False,
        )
        if result[1] != 0:
            click.echo(f"  ⚠️  Grafana deployment failed: {result[0]}")
            # Show pod logs for debugging
            click.echo("  📋 Checking Grafana pod status...")
            result = run_command(
                [
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    namespace,
                    "-l",
                    "app.kubernetes.io/name=grafana",
                ],
                check=False,
            )
            click.echo(result[0])
            result = run_command(
                [
                    "kubectl",
                    "logs",
                    "-n",
                    namespace,
                    "-l",
                    "app.kubernetes.io/name=grafana",
                    "--tail=50",
                ],
                check=False,
            )
            if result[1] == 0:
                click.echo("  📋 Grafana pod logs:")
                click.echo(result[0])
            return False
        click.echo("  ✅ Grafana deployed")
    finally:
        pathlib.Path(grafana_values_file).unlink(missing_ok=True)

    # Wait for pods to be ready
    click.echo("  ⏳ Waiting for pods to be ready...")
    for _ in range(30):  # Wait up to 5 minutes
        result = run_command(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                namespace,
                "-o",
                "jsonpath={.items[*].status.phase}",
            ],
            check=False,
        )
        if result[1] == 0:
            phases = result[0].split()
            if all(phase in ["Running", "Succeeded"] for phase in phases if phase):
                break
        time.sleep(10)

    return True


def _get_grafana_credentials() -> Dict[str, str]:
    """Retrieve Grafana admin credentials. Returns dict with username and password."""
    run_command = _run_infra_cmd

    namespace = "monitoring"
    credentials = {"username": "admin", "password": "admin"}

    # Try to get password from secret
    result = run_command(
        [
            "kubectl",
            "get",
            "secret",
            "-n",
            namespace,
            "grafana",
            "-o",
            "jsonpath={.data.admin-password}",
        ],
        check=False,
    )
    if result[1] == 0 and result[0]:
        import base64

        try:
            credentials["password"] = base64.b64decode(result[0]).decode("utf-8")
        except Exception:
            pass

    return credentials


def _validate_logging_setup() -> bool:
    """Validate logging setup with a test query. Returns True if successful."""
    run_command = _run_infra_cmd

    namespace = "monitoring"

    # Check if pods are running
    click.echo("  🔍 Validating logging setup...")
    result = run_command(
        [
            "kubectl",
            "get",
            "pods",
            "-n",
            namespace,
            "-o",
            "jsonpath={.items[*].metadata.name}",
        ],
        check=False,
    )
    if result[1] != 0:
        click.echo("  ⚠️  Could not check_url_responds status")
        return False

    pods = result[0].split()
    expected_pods = ["loki", "promtail", "grafana"]
    found_pods = [p for p in pods if any(exp in p.lower() for exp in expected_pods)]

    if len(found_pods) < 3:
        click.echo(f"  ⚠️  Expected 3 pods, found: {found_pods}")
        return False

    # Check if Grafana service is accessible
    result = run_command(
        [
            "kubectl",
            "get",
            "svc",
            "-n",
            namespace,
            "grafana",
            "-o",
            "jsonpath={.spec.clusterIP}",
        ],
        check=False,
    )
    if result[1] != 0:
        click.echo("  ⚠️  Grafana service not found")
        return False

    click.echo("  ✅ Logging infrastructure is running")
    return True


def _check_cluster_tool_installed(tool: str) -> bool:
    """Check if a cluster tool (kind/k3d/minikube) is installed. Returns True if available."""
    run_command = _run_infra_cmd

    check_commands = {
        "kind": ["kind", "--version"],
        "k3d": ["k3d", "--version"],
        "minikube": ["minikube", "version"],
    }

    if tool not in check_commands:
        return False

    try:
        result = run_command(check_commands[tool], check=False)
        return result[1] == 0
    except Exception:
        return False


def _get_available_cluster_tools() -> List[str]:
    """Return list of installed cluster tools."""
    tools = []
    for tool in ["kind", "k3d", "minikube"]:
        if _check_cluster_tool_installed(tool):
            tools.append(tool)
    return tools


def _ensure_kubectl_installed() -> bool:
    """Ensure kubectl is installed. Returns True if available."""
    import platform

    from vibe_tools.staging import has_kubectl

    run_command = _run_infra_cmd

    if has_kubectl():
        return True

    click.echo("  📦 kubectl is not installed. Installing...")
    system = platform.system().lower()
    is_macos = system == "darwin"

    if is_macos:
        if shutil.which("brew"):
            try:
                result = run_command(["brew", "install", "kubectl"], check=False)
                if result[1] == 0:
                    click.echo("  ✅ kubectl installed successfully")
                    return True
                else:
                    click.echo(f"  ⚠️  Homebrew installation failed: {result[0]}")
            except Exception as e:
                click.echo(f"  ⚠️  Installation error: {e}")
        else:
            click.echo("  💡 Install kubectl manually: brew install kubectl")
            return False
    else:
        click.echo("  💡 Install kubectl manually:")
        click.echo(
            "     curl -LO https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        )
        click.echo(
            "     sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl"
        )
        return False

    # Verify installation
    if has_kubectl():
        click.echo("  ✅ kubectl is now available")
        return True
    else:
        click.echo("  ⚠️  kubectl installation verification failed")
        return False


def _install_kind() -> bool:
    """Install Kind. Returns True if successful."""
    import platform

    run_command = _run_infra_cmd

    if _check_cluster_tool_installed("kind"):
        click.echo("  ✅ Kind is already installed")
        return True

    click.echo("  📦 Installing Kind...")
    system = platform.system().lower()
    is_macos = system == "darwin"

    if is_macos:
        if shutil.which("brew"):
            try:
                result = run_command(["brew", "install", "kind"], check=False)
                if result[1] == 0:
                    click.echo("  ✅ Kind installed successfully")
                    return True
                else:
                    click.echo(f"  ⚠️  Homebrew installation failed: {result[0]}")
            except Exception as e:
                click.echo(f"  ⚠️  Installation error: {e}")
        else:
            click.echo("  💡 Install Kind manually: brew install kind")
            return False
    else:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                binary_path = pathlib.Path(tmpdir) / "kind"
                download_cmd = [
                    "curl",
                    "-Lo",
                    str(binary_path),
                    "https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64",
                ]
                result = run_command(download_cmd, check=False)
                if result[1] == 0:
                    binary_path.chmod(0o755)
                    install_cmd = [
                        "sudo",
                        "mv",
                        str(binary_path),
                        "/usr/local/bin/kind",
                    ]
                    result = run_command(install_cmd, check=False)
                    if result[1] == 0:
                        click.echo("  ✅ Kind installed successfully")
                        return True
                    else:
                        click.echo(f"  ⚠️  Installation failed: {result[0]}")
                else:
                    click.echo(f"  ⚠️  Download failed: {result[0]}")
        except Exception as e:
            click.echo(f"  ⚠️  Installation error: {e}")

    # Verify installation
    if _check_cluster_tool_installed("kind"):
        click.echo("  ✅ Kind is now available")
        return True
    else:
        click.echo("  ⚠️  Kind installation verification failed")
        return False


def _install_k3d() -> bool:
    """Install k3d. Returns True if successful."""
    import platform

    run_command = _run_infra_cmd

    if _check_cluster_tool_installed("k3d"):
        click.echo("  ✅ k3d is already installed")
        return True

    click.echo("  📦 Installing k3d...")
    system = platform.system().lower()
    is_macos = system == "darwin"

    if is_macos:
        if shutil.which("brew"):
            try:
                result = run_command(["brew", "install", "k3d"], check=False)
                if result[1] == 0:
                    click.echo("  ✅ k3d installed successfully")
                    return True
                else:
                    click.echo(f"  ⚠️  Homebrew installation failed: {result[0]}")
            except Exception as e:
                click.echo(f"  ⚠️  Installation error: {e}")
        else:
            click.echo("  💡 Install k3d manually: brew install k3d")
            return False
    else:
        try:
            # Use subprocess directly for shell command with pipe
            import subprocess

            result = subprocess.run(
                "curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash",
                shell=True,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                click.echo("  ✅ k3d installed successfully")
                return True
            else:
                click.echo(f"  ⚠️  Installation failed: {result.stderr}")
        except Exception as e:
            click.echo(f"  ⚠️  Installation error: {e}")

    # Verify installation
    if _check_cluster_tool_installed("k3d"):
        click.echo("  ✅ k3d is now available")
        return True
    else:
        click.echo("  ⚠️  k3d installation verification failed")
        return False


def _install_minikube() -> bool:
    """Install Minikube. Returns True if successful."""
    import platform

    run_command = _run_infra_cmd

    if _check_cluster_tool_installed("minikube"):
        click.echo("  ✅ Minikube is already installed")
        return True

    click.echo("  📦 Installing Minikube...")
    system = platform.system().lower()
    is_macos = system == "darwin"

    if is_macos:
        if shutil.which("brew"):
            try:
                result = run_command(["brew", "install", "minikube"], check=False)
                if result[1] == 0:
                    click.echo("  ✅ Minikube installed successfully")
                    return True
                else:
                    click.echo(f"  ⚠️  Homebrew installation failed: {result[0]}")
            except Exception as e:
                click.echo(f"  ⚠️  Installation error: {e}")
        else:
            click.echo("  💡 Install Minikube manually: brew install minikube")
            return False
    else:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                binary_path = pathlib.Path(tmpdir) / "minikube"
                download_cmd = [
                    "curl",
                    "-Lo",
                    str(binary_path),
                    "https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64",
                ]
                result = run_command(download_cmd, check=False)
                if result[1] == 0:
                    binary_path.chmod(0o755)
                    install_cmd = [
                        "sudo",
                        "install",
                        str(binary_path),
                        "/usr/local/bin/minikube",
                    ]
                    result = run_command(install_cmd, check=False)
                    if result[1] == 0:
                        click.echo("  ✅ Minikube installed successfully")
                        return True
                    else:
                        click.echo(f"  ⚠️  Installation failed: {result[0]}")
                else:
                    click.echo(f"  ⚠️  Download failed: {result[0]}")
        except Exception as e:
            click.echo(f"  ⚠️  Installation error: {e}")

    # Verify installation
    if _check_cluster_tool_installed("minikube"):
        click.echo("  ✅ Minikube is now available")
        return True
    else:
        click.echo("  ⚠️  Minikube installation verification failed")
        return False


def _create_kind_cluster(name: str = "vibe-dev") -> bool:
    """Create a Kind cluster. Returns True if successful."""
    from vibe_tools.staging import has_k8s_cluster

    run_command = _run_infra_cmd

    # Check if cluster already exists
    result = run_command(["kind", "get", "clusters"], check=False)
    if result[1] == 0 and name in result[0]:
        click.echo(f"  ℹ️  Kind cluster '{name}' already exists")
        # Check if it's accessible
        if has_k8s_cluster():
            click.echo(f"  ✅ Using existing cluster '{name}'")
            return True
        else:
            click.echo(f"  ⚠️  Cluster '{name}' exists but is not accessible")

    click.echo(f"  📦 Creating Kind cluster '{name}'...")
    result = run_command(["kind", "create", "cluster", "--name", name], check=False)
    if result[1] != 0:
        click.echo(f"  ⚠️  Failed to create Kind cluster: {result[0]}")
        return False

    # Verify cluster is accessible
    click.echo("  🔍 Verifying cluster...")
    for _ in range(10):
        if has_k8s_cluster():
            result = run_command(["kubectl", "get", "nodes"], check=False)
            if result[1] == 0:
                click.echo("  ✅ Kind cluster created and verified")
                return True
        time.sleep(2)

    click.echo("  ⚠️  Cluster created but verification failed")
    return False


def _create_k3d_cluster(name: str = "vibe-dev") -> bool:
    """Create a k3d cluster. Returns True if successful."""
    from vibe_tools.staging import has_k8s_cluster

    run_command = _run_infra_cmd

    # Check if cluster already exists
    result = run_command(["k3d", "cluster", "list"], check=False)
    if result[1] == 0 and name in result[0]:
        click.echo(f"  ℹ️  k3d cluster '{name}' already exists")
        # Check if it's accessible
        if has_k8s_cluster():
            click.echo(f"  ✅ Using existing cluster '{name}'")
            return True
        else:
            click.echo(f"  ⚠️  Cluster '{name}' exists but is not accessible")

    click.echo(f"  📦 Creating k3d cluster '{name}'...")
    result = run_command(["k3d", "cluster", "create", name], check=False)
    if result[1] != 0:
        click.echo(f"  ⚠️  Failed to create k3d cluster: {result[0]}")
        return False

    # Verify cluster is accessible
    click.echo("  🔍 Verifying cluster...")
    for _ in range(10):
        if has_k8s_cluster():
            result = run_command(["kubectl", "get", "nodes"], check=False)
            if result[1] == 0:
                click.echo("  ✅ k3d cluster created and verified")
                return True
        time.sleep(2)

    click.echo("  ⚠️  Cluster created but verification failed")
    return False


def _create_minikube_cluster() -> bool:
    """Start Minikube cluster. Returns True if successful."""
    from vibe_tools.staging import has_k8s_cluster

    run_command = _run_infra_cmd

    # Check if minikube is already running
    result = run_command(["minikube", "status"], check=False)
    if result[1] == 0 and "Running" in result[0]:
        click.echo("  ℹ️  Minikube cluster is already running")
        if has_k8s_cluster():
            click.echo("  ✅ Using existing Minikube cluster")
            return True

    click.echo("  📦 Starting Minikube cluster...")
    result = run_command(["minikube", "start"], check=False)
    if result[1] != 0:
        click.echo(f"  ⚠️  Failed to start Minikube: {result[0]}")
        return False

    # Verify cluster is accessible
    click.echo("  🔍 Verifying cluster...")
    for _ in range(10):
        if has_k8s_cluster():
            result = run_command(["kubectl", "get", "nodes"], check=False)
            if result[1] == 0:
                click.echo("  ✅ Minikube cluster started and verified")
                return True
        time.sleep(2)

    click.echo("  ⚠️  Cluster started but verification failed")
    return False


def _setup_logging_infrastructure():
    """Set up logging infrastructure: Stern, Loki, Promtail, Grafana."""
    from vibe_tools.staging import has_k8s_cluster

    click.echo("\n--- Logging Infrastructure Setup ---")

    # Check if Kubernetes cluster is available
    if not has_k8s_cluster():
        click.echo("  ⚠️  Kubernetes cluster not available.")
        click.echo(
            "     Logging infrastructure requires a local Kubernetes cluster (kind/k3d/minikube)."
        )

        # Check if kubectl is installed
        if not _ensure_kubectl_installed():
            click.echo("  ❌ kubectl is required but could not be installed.")
            click.echo("     Please install kubectl manually and re-run scaffold.")
            return

        # Check which cluster tools are available
        available_tools = _get_available_cluster_tools()

        # Prompt user to choose a cluster tool
        click.echo("\n  Set Up Local Kubernetes Cluster")
        click.echo("  What type of Kubernetes cluster would you like to install?")
        click.echo("")
        click.echo("  Option 1: Kind (recommended for local dev)")
        click.echo("           - Fast, easy to reset")
        click.echo("           - Works well with Skaffold")
        click.echo("")
        click.echo("  Option 2: k3d (lightweight)")
        click.echo("           - Lightweight Kubernetes distribution")
        click.echo("           - Good for resource-constrained environments")
        click.echo("")
        click.echo("  Option 3: Minikube")
        click.echo("           - Full-featured local Kubernetes")
        click.echo("           - Supports multiple drivers")

        if available_tools:
            click.echo(f"\n  Note: {', '.join(available_tools)} already installed")
            if "kind" in available_tools:
                default_choice = "1"
            elif "k3d" in available_tools:
                default_choice = "2"
            elif "minikube" in available_tools:
                default_choice = "3"
            else:
                default_choice = "1"
        else:
            default_choice = "1"
            click.echo(
                "\n  No cluster tools found. Kind will be installed (recommended)."
            )

        choice = click.prompt(
            "\n  Which Kubernetes cluster type should we install?",
            default=default_choice,
            type=click.Choice(["1", "2", "3"]),
        )

        tool_map = {"1": "kind", "2": "k3d", "3": "minikube"}
        selected_tool = tool_map[choice]

        # Install the tool if needed
        if not _check_cluster_tool_installed(selected_tool):
            install_funcs = {
                "kind": _install_kind,
                "k3d": _install_k3d,
                "minikube": _install_minikube,
            }
            if not install_funcs[selected_tool]():
                click.echo(
                    f"  ❌ Failed to install {selected_tool}. Please install it manually and re-run scaffold."
                )
                return

        # Create the cluster
        click.echo(f"\n  📦 Setting up {selected_tool} cluster...")
        create_funcs = {
            "kind": lambda: _create_kind_cluster("vibe-dev"),
            "k3d": lambda: _create_k3d_cluster("vibe-dev"),
            "minikube": _create_minikube_cluster,
        }
        if not create_funcs[selected_tool]():
            click.echo(
                f"  ❌ Failed to create {selected_tool} cluster. Please check the error messages above."
            )
            return

        # Verify cluster is now accessible
        if not has_k8s_cluster():
            click.echo(
                "  ❌ Cluster was created but is not accessible. Please check your setup."
            )
            return

        click.echo("  ✅ Kubernetes cluster is ready!")

    # Install Stern
    click.echo("\n📦 Installing Stern for log streaming...")
    if not _install_stern():
        click.echo(
            "  ⚠️  Stern installation failed, but continuing with other components..."
        )

    # Ensure Helm is installed
    click.echo("\n📦 Ensuring Helm is installed...")
    if not _ensure_helm_installed():
        click.echo(
            "  ❌ Helm is required for logging infrastructure. Please install it manually."
        )
        click.echo("     macOS: brew install helm")
        click.echo(
            "     Linux: curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
        )
        raise click.ClickException("Helm installation failed")

    # Setup Helm repos
    click.echo("\n📦 Setting up Helm repositories...")
    if not _setup_helm_repos():
        click.echo("  ❌ Failed to setup Helm repositories")
        raise click.ClickException("Helm repo setup failed")

    # Deploy Loki stack
    click.echo("\n📦 Deploying Loki stack (Loki, Promtail, Grafana)...")
    if not _deploy_loki_stack():
        click.echo("  ❌ Failed to deploy Loki stack")
        raise click.ClickException("Loki stack deployment failed")

    # Get Grafana credentials
    credentials = _get_grafana_credentials()
    click.echo("\n✅ Logging infrastructure deployed successfully!")
    click.echo(
        f"   Grafana credentials: username={credentials['username']}, password={credentials['password']}"
    )
    click.echo(
        "   Access Grafana: kubectl port-forward svc/grafana -n monitoring 3000:3000"
    )
    click.echo("   Then open: http://localhost:3000")

    # Validate setup
    if not _validate_logging_setup():
        click.echo(
            "  ⚠️  Logging setup validation had issues, but components are deployed"
        )


def _detect_architecture(agent, stream) -> Dict[str, Any]:
    """Analyze SRD-architecture.md to detect project type and required capabilities."""
    from vibe_tools.utils import ARCHITECTURE_SPEC, run_llm

    if not ARCHITECTURE_SPEC.exists():
        return {"type": "unknown", "capabilities": []}

    arch_content = ARCHITECTURE_SPEC.read_text()

    prompt = f"""Analyze the following architecture specification and categorize the project.
Return a JSON object with two fields:
1. "type": One of ["kubernetes", "tauri", "cli", "web-standard", "other"]
2. "capabilities": A list of specific technologies detected (e.g., ["python", "react", "docker", "postgresql", "rust"])

ARCHITECTURE:
---
{arch_content}
---

Output ONLY valid JSON.
"""

    response = run_llm(prompt)
    if not response:
        return {"type": "unknown", "capabilities": []}

    # Extract JSON from response
    try:
        # Simple extraction in case of markdown fences
        json_match = re.search(r"(\{.*\})", response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        return json.loads(response)
    except (json.JSONDecodeError, AttributeError):
        # Fallback to simple keyword detection if LLM fails or returns garbage
        capabilities = []
        project_type = "cli"

        lower_content = arch_content.lower()
        if "kubernetes" in lower_content or "skaffold" in lower_content:
            project_type = "kubernetes"
        elif "tauri" in lower_content:
            project_type = "tauri"
        elif "react" in lower_content or "next.js" in lower_content:
            project_type = "web-standard"

        if "python" in lower_content:
            capabilities.append("python")
        if "rust" in lower_content:
            capabilities.append("rust")
        if "react" in lower_content:
            capabilities.append("react")
        if "docker" in lower_content:
            capabilities.append("docker")

        return {"type": project_type, "capabilities": capabilities}


def _generate_dev_spec(agent, stream, arch_info: Dict[str, Any]):
    """Generate SRD-dev_environment.md from SRD-architecture.md."""
    from vibe_tools.utils import (
        ARCHITECTURE_SPEC,
        DEV_SPEC,
        ensure_dir,
    )

    if not ARCHITECTURE_SPEC.exists():
        click.echo(
            f"❌ {ARCHITECTURE_SPEC} not found. Please create it first using 'vibe architect'."
        )
        return

    click.echo(
        f"📋 Generating SRD-dev_environment.md for {arch_info['type']} project..."
    )

    # Read SRD-architecture.md
    arch_content = ARCHITECTURE_SPEC.read_text()

    # Build specialized prompt instructions based on architecture type
    type_instructions = ""
    if arch_info["type"] == "kubernetes":
        type_instructions = """
2. **Skaffold and Helm**:
   - Include Skaffold configuration for local Kubernetes development
   - Include Helm charts for deployment
   - Document how to use `skaffold dev` for local development
   - IMPORTANT: When generating skaffold.yaml, ensure it includes `defaultRepo: ""` under the `build:` section
   - IMPORTANT: If generating frontend Dockerfiles, use node:20-slim or node:22-slim.

3. **Logging Solution (K8s-optimized)**:
   - **Quick Log Streaming (Stern)**: `stern .` to tail logs from all pods.
   - **Centralized Log Aggregation (Loki + Grafana)**: Aggregation service running in Kubernetes.
   - **AI-Queryable Logs**: Grafana HTTP API endpoint details.
"""
    elif arch_info["type"] == "tauri":
        type_instructions = """
2. **Tauri Development**:
   - Focus on `cargo tauri dev` for local development.
   - Specify build requirements for both Rust (Cargo) and Frontend (npm/pnpm/yarn).
   - Document how to handle sidecars if specified in the architecture.
   - Testing: Specify dual-test harness using `cargo test` and `vitest`.

3. **Logging Solution (Desktop/Local)**:
   - Focus on standard output and local log files.
   - Document where application logs are stored on different OS platforms.
   - Include `make logs` to tail local log files.
"""
    else:  # CLI, Web-Standard, or Other
        type_instructions = """
2. **Standard Development**:
   - Focus on local runtime environment (e.g., venv for Python, node_modules for JS).
   - Specify `make dev` or `npm run dev` for starting the application.
   - Document environment variable requirements in `.env`.

3. **Logging Solution (Standard)**:
   - Focus on structured logging to stdout/stderr.
   - Document log file locations if applicable.
   - Include `make logs` to tail logs.
"""

    # Generate SRD-dev_environment.md using agent
    prompt = f"""You are generating a development environment specification based on the architecture.

Analyze the architecture and create a comprehensive SRD-dev_environment.md file that specifies:
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
   - Log Targets: `make logs`, `make logs-follow`

{type_instructions}

4. **Services Section**: Clearly list all services/components that need to run in development mode with their startup commands.
   - For persistent services (like web servers or Tauri apps), include a `health_check_url` field (e.g., `health_check_url: http://localhost:1420`).
   - If a service is a Tauri app, explicitly mention its default dev URL (http://localhost:1420).

The architecture specification is in product/SRD-architecture.md:

{arch_content}

Generate a complete SRD-dev_environment.md file following this structure:

# Development Environment Specification

## 1. Overview
[High-level overview. Mention if using Skaffold/Helm or specialized tools like Tauri.]

## 2. Build Components
[For each component, specify build commands, dependencies, and outputs.]

## 3. Development Environment
### 3.1 Services Required
### 3.2 Environment Variables
### 3.3 Startup Commands
### 3.4 Logging
### 3.5 Verification

## 4. Build System
### 4.1 Makefile Targets
### 4.2 Build Orchestration [Skaffold/Tauri/Manual]
### 4.3 CI/CD Build Steps

Output ONLY the markdown content for SRD-dev_environment.md.
"""

    cmd = get_agent_command(agent, prompt)
    bypass_safety = bool(os.environ.get("VIBE_IGNORE_GIT_SAFETY"))
    output, code = run_agent(cmd, stream=stream, bypass_safety=bypass_safety)

    if code != 0 or not output.strip():
        click.echo(
            "❌ Failed to generate SRD-dev_environment.md. Please create it manually using 'vibe architect'."
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

    # Write SRD-dev_environment.md
    ensure_dir(DEV_SPEC.parent)
    DEV_SPEC.write_text(clean_output)
    click.echo(f"✅ Generated {DEV_SPEC}")


if __name__ == "__main__":
    setup_cli()
