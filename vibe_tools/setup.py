import pathlib
import socket
import subprocess
from typing import Any, Dict, Optional

import click
from dotenv import find_dotenv, load_dotenv

from vibe_tools.utils import (
    CONFIG_FILE,
    ensure_dir,
    get_cursor_api_key,
    get_google_api_key,
    get_project_name,
    is_tool_available,
    load_config,
    run_command,
    save_config,
    save_cursor_api_key,
    save_google_api_key,
)

load_dotenv(find_dotenv() or ".env")

SERVICE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "postgres": {
        "display": "PostgreSQL",
        "default_port": 5432,
        "docker_keywords": ["postgres", "postgresql", "pgvector"],
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
                "prompt": "Postgres database",
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
                "prompt": "Redis password",
                "default": "",
                "hide_input": True,
            },
            {"name": "database", "prompt": "Redis database", "type": int, "default": 0},
        ],
    },
    "rabbitmq": {
        "display": "RabbitMQ",
        "default_port": 5672,
        "docker_keywords": ["rabbitmq"],
        "fields": [
            {"name": "host", "prompt": "RabbitMQ host", "default": "localhost"},
            {"name": "port", "prompt": "RabbitMQ port", "type": int, "default": 5672},
            {"name": "user", "prompt": "RabbitMQ user", "default": "guest"},
            {
                "name": "password",
                "prompt": "RabbitMQ password",
                "default": "guest",
                "hide_input": True,
            },
            {"name": "virtual_host", "prompt": "RabbitMQ vhost", "default": "/"},
        ],
    },
    "elasticsearch": {
        "display": "Elasticsearch",
        "default_port": 9200,
        "docker_keywords": ["elasticsearch", "elastic"],
        "fields": [
            {"name": "host", "prompt": "Elasticsearch host", "default": "localhost"},
            {"name": "port", "prompt": "Elasticsearch port", "type": int, "default": 9200},
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
            {"name": "port", "prompt": "MailHog SMTP port", "type": int, "default": 1025},
            {"name": "web_port", "prompt": "MailHog web port", "type": int, "default": 8025},
        ],
    },
    "s3-linode": {
        "display": "S3 (Linode style)",
        "default_port": 9000,
        "docker_keywords": ["minio"],
        "fields": [
            {"name": "host", "prompt": "S3 host", "default": "localhost"},
            {"name": "port", "prompt": "S3 port", "type": int, "default": 9000},
            {"name": "access_key", "prompt": "S3 access key", "default": "minioadmin"},
            {
                "name": "secret_key",
                "prompt": "S3 secret key",
                "default": "minioadmin",
                "hide_input": True,
            },
            {"name": "region", "prompt": "S3 region", "default": "us-east-1"},
            {"name": "addressing_style", "prompt": "Addressing style", "default": "path"},
            {"name": "signature_version", "prompt": "Signature version", "default": "s3v4"},
            {"name": "console_port", "prompt": "Console port", "type": int, "default": 9001},
        ],
    },
    "s3-aws": {
        "display": "S3 (AWS style)",
        "default_port": 9010,
        "docker_keywords": ["minio"],
        "fields": [
            {"name": "host", "prompt": "S3 host", "default": "localhost"},
            {"name": "port", "prompt": "S3 port", "type": int, "default": 9010},
            {"name": "access_key", "prompt": "S3 access key", "default": "minioadmin"},
            {
                "name": "secret_key",
                "prompt": "S3 secret key",
                "default": "minioadmin",
                "hide_input": True,
            },
            {"name": "region", "prompt": "S3 region", "default": "us-east-1"},
            {
                "name": "addressing_style",
                "prompt": "Addressing style",
                "default": "virtual",
            },
            {"name": "signature_version", "prompt": "Signature version", "default": "s3v4"},
            {"name": "console_port", "prompt": "Console port", "type": int, "default": 9011},
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


def _parse_docker_port_mapping(ports: str, target_port: int) -> Optional[int]:
    if not ports:
        return None
    for item in ports.split(","):
        item = item.strip()
        if "->" not in item:
            continue
        host_part, container_part = item.split("->", 1)
        container_port = container_part.split("/")[0].strip()
        if container_port.isdigit() and int(container_port) == target_port:
            host_port = host_part.split(":")[-1].strip()
            if host_port.isdigit():
                return int(host_port)
    return None


def detect_docker_service(service_key: str) -> Dict[str, Any]:
    metadata = SERVICE_DEFINITIONS.get(service_key)
    if not metadata or not is_tool_available("docker"):
        return {}
    stdout, code = run_command(
        ["docker", "ps", "--format", "{{.Names}}||{{.Image}}||{{.Ports}}"],
        check=False,
    )
    if code != 0:
        return {}
    for line in stdout.splitlines():
        if not line:
            continue
        name, image, ports = line.split("||", maxsplit=2)
        searchable = f"{name} {image}".lower()
        if not any(keyword in searchable for keyword in metadata["docker_keywords"]):
            continue
        host_port = _parse_docker_port_mapping(ports, metadata["default_port"])
        return {
            "container_name": name,
            "host": "localhost",
            "port": host_port or metadata["default_port"],
        }
    return {}


def prompt_service_config(service_key: str) -> Dict[str, Any]:
    metadata = SERVICE_DEFINITIONS[service_key]
    detected = detect_docker_service(service_key)
    if detected.get("container_name"):
        click.echo(
            f"Detected Docker container '{detected['container_name']}' for {metadata['display']}."
        )
    values: Dict[str, Any] = {}
    for field in metadata["fields"]:
        default_value = detected.get(field["name"], field.get("default"))
        values[field["name"]] = click.prompt(
            field["prompt"],
            default=default_value,
            hide_input=field.get("hide_input", False),
            type=field.get("type", str),
        )
    if detected.get("container_name"):
        values["docker_container_name"] = detected["container_name"]
    return values


def check_connection(service_key: str, details: Dict[str, Any]) -> bool:
    host = details.get("host", "localhost")
    port = details.get("port")
    if not port:
        return False
    if service_key == "elasticsearch":
        scheme = details.get("scheme", "http")
        try:
            import httpx

            response = httpx.get(f"{scheme}://{host}:{port}", timeout=2.0)
            return response.status_code == 200
        except Exception:
            pass
    try:
        with socket.create_connection((host, int(port)), timeout=2.0):
            return True
    except (OSError, ValueError):
        return False


def configure_service(service_key: str):
    metadata = SERVICE_DEFINITIONS[service_key]
    config = load_config()
    config.setdefault("services", {})
    details = prompt_service_config(service_key)
    click.echo(f"Checking connection to {metadata['display']}...")
    if not check_connection(service_key, details):
        click.echo(
            f"Warning: could not connect to {details.get('host')}:{details.get('port')}."
        )
        if not click.confirm("Save configuration anyway?", default=True):
            click.echo("Aborted.")
            return
    config["services"][service_key] = details
    save_config(config)
    click.echo(f"Saved {metadata['display']} configuration to {CONFIG_FILE}")


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
        click.echo("No services configured.")
        return
    for service_key, details in services.items():
        metadata = SERVICE_DEFINITIONS.get(service_key, {})
        display = metadata.get("display", service_key)
        status = "Connected" if check_connection(service_key, details) else "Failed"
        click.echo(f"{display:<18} {status}")


@setup_cli.command(name="llm")
def llm():
    """Verify Google Gemini connectivity."""
    api_key = get_google_api_key()
    if not api_key:
        click.echo("Google API key is missing. Run 'vibe config api'.")
        return
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Reply with READY and nothing else.",
        )
        click.echo((response.text or "").strip())
    except Exception as exc:
        click.echo(f"LLM test failed: {exc}")


@setup_cli.command(name="dspy", hidden=True)
@click.pass_context
def dspy_alias(ctx):
    """Alias for llm."""
    ctx.invoke(llm)


@setup_cli.command()
def api():
    """Configure API keys for local use."""
    google_key = click.prompt(
        "Google API Key",
        default=get_google_api_key() or "",
        hide_input=True,
    )
    if google_key:
        save_google_api_key(google_key)
        click.echo("Saved Google API key.")

    cursor_key = click.prompt(
        "Cursor API Key",
        default=get_cursor_api_key() or "",
        hide_input=True,
    )
    if cursor_key:
        save_cursor_api_key(cursor_key)
        click.echo("Saved Cursor API key.")


@setup_cli.command()
def google():
    """Configure Google Sheets cost logging."""
    config = load_config()
    enabled = click.confirm(
        "Enable Google Sheets cost logging?",
        default=config.get("use_google_sheets", False),
    )
    config["use_google_sheets"] = enabled
    if enabled:
        sheet_id = click.prompt(
            "Google Sheet ID",
            default=config.get("google_sheet_id", ""),
        )
        config["google_sheet_id"] = sheet_id
    else:
        config.pop("google_sheet_id", None)
    save_config(config)
    click.echo(f"Saved Google settings to {CONFIG_FILE}")


@setup_cli.command()
@click.option("--name", default="local", help="Virtualenv suffix.")
@click.option("--python-version", default="3.11.10", help="Python version.")
def env(name, python_version):
    """Set a local pyenv version for this repo."""
    if not is_tool_available("pyenv"):
        click.echo("pyenv is required for 'vibe config env'.")
        return
    venv_name = f"{get_project_name()}-{python_version}-{name}".replace("_", "-")
    versions, _ = run_command(["pyenv", "versions"], check=False)
    if python_version not in versions:
        click.echo(f"Installing Python {python_version}...")
        run_command(["pyenv", "install", python_version], check=False)
    virtualenvs, _ = run_command(["pyenv", "virtualenvs"], check=False)
    if venv_name not in virtualenvs:
        click.echo(f"Creating virtualenv {venv_name}...")
        run_command(["pyenv", "virtualenv", python_version, venv_name], check=False)
    run_command(["pyenv", "local", venv_name], check=False)
    ensure_dir(pathlib.Path(".venv").parent)
    click.echo(f"Configured local pyenv environment: {venv_name}")


@setup_cli.command(name="eject-prompts")
def eject_prompts():
    """Write bundled prompts into ./prompts/."""
    from vibe_tools.templates import TEMPLATES

    prompts_dir = pathlib.Path("prompts")
    ensure_dir(prompts_dir)
    count = 0
    for filename, content in TEMPLATES.items():
        if filename == "README":
            continue
        target = prompts_dir / filename
        if target.exists():
            continue
        target.write_text(content)
        count += 1
    click.echo(f"Ejected {count} prompts into {prompts_dir}")


@setup_cli.command()
def postgres():
    """Configure PostgreSQL."""
    configure_service("postgres")


@setup_cli.command()
def redis():
    """Configure Redis."""
    configure_service("redis")


@setup_cli.command()
def rabbitmq():
    """Configure RabbitMQ."""
    configure_service("rabbitmq")


@setup_cli.command()
def elasticsearch():
    """Configure Elasticsearch."""
    configure_service("elasticsearch")


@setup_cli.command()
def mailhog():
    """Configure MailHog."""
    configure_service("mailhog")


@setup_cli.command(name="s3-linode")
def s3_linode():
    """Configure Linode-style S3."""
    configure_service("s3-linode")


@setup_cli.command(name="s3-aws")
def s3_aws():
    """Configure AWS-style S3."""
    configure_service("s3-aws")


@setup_cli.command()
def imgproxy():
    """Configure imgproxy."""
    configure_service("imgproxy")


if __name__ == "__main__":
    setup_cli()
