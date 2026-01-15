import subprocess
from typing import Any, Dict

import click

from vibe_tools.utils import (
    load_global_servers,
    run_command,
    save_config,
    save_global_servers,
)

DEFAULT_SERVER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "postgres": {
        "image": "pgvector/pgvector:pg16",
        "container_name": "vibe-postgres",
        "ports": {"5432/tcp": 5432},
        "env": {
            "POSTGRES_PASSWORD": "postgres",
            "POSTGRES_USER": "postgres",
        },
        "description": "PostgreSQL with pgvector extension",
    },
    "redis": {
        "image": "redis:alpine",
        "container_name": "vibe-redis",
        "ports": {"6379/tcp": 6379},
        "description": "Redis in-memory data store",
    },
    "rabbitmq": {
        "image": "rabbitmq:3-management",
        "container_name": "vibe-rabbitmq",
        "ports": {"5672/tcp": 5672, "15672/tcp": 15672},
        "description": "RabbitMQ message broker with management UI",
    },
    "elasticsearch": {
        "image": "elasticsearch:8.11.1",
        "container_name": "vibe-elasticsearch",
        "ports": {"9200/tcp": 9200},
        "env": {
            "discovery.type": "single-node",
            "xpack.security.enabled": "false",
        },
        "description": "Elasticsearch search engine (security disabled for local dev)",
    },
    "mailhog": {
        "image": "mailhog/mailhog",
        "container_name": "vibe-mailhog",
        "ports": {"1025/tcp": 1025, "8025/tcp": 8025},
        "description": "MailHog email testing tool (SMTP: 1025, Web: 8025)",
    },
    "minio-linode": {
        "image": "minio/minio",
        "container_name": "vibe-minio-linode",
        "ports": {"9000/tcp": 9000, "9001/tcp": 9001},
        "env": {
            "MINIO_ROOT_USER": "minioadmin",
            "MINIO_ROOT_PASSWORD": "minioadmin",
        },
        "command": "server /data --console-address :9001",
        "description": "MinIO S3-compatible (Linode-style path addressing)",
    },
    "minio-aws": {
        "image": "minio/minio",
        "container_name": "vibe-minio-aws",
        "ports": {"9010/tcp": 9010, "9011/tcp": 9011},
        "env": {
            "MINIO_ROOT_USER": "minioadmin",
            "MINIO_ROOT_PASSWORD": "minioadmin",
        },
        "command": "server /data --console-address :9011",
        "description": "MinIO S3-compatible (AWS-style virtual addressing)",
    },
    "imgproxy": {
        "image": "darthsim/imgproxy:latest",
        "container_name": "vibe-imgproxy",
        "ports": {"8080/tcp": 8080},
        "description": "imgproxy for on-the-fly image resizing and conversion",
    },
}


def get_server_configs() -> Dict[str, Any]:
    """Returns global server configurations, merging defaults with saved ones."""
    configs = DEFAULT_SERVER_CONFIGS.copy()
    saved = load_global_servers()
    if saved:
        # Update defaults with saved configurations (preserving user changes)
        # But ensure new default services are added
        for key, value in saved.items():
            if key in configs:
                configs[key].update(value)
            else:
                configs[key] = value

    # Save the merged version if it's different (optional, but ensures persistence)
    if configs != saved:
        save_global_servers(configs)

    return configs


def get_container_status(container_name: str) -> str:
    """Returns the status of a Docker container."""
    try:
        stdout, code = run_command(
            ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
            check=False,
        )
        if code == 0:
            return stdout.strip()
        return "not_created"
    except Exception:
        return "error"


@click.group()
def servers_cli():
    """Manage local development servers via Docker."""
    pass


@servers_cli.command(name="list")
def list_servers():
    """List supported servers and their status."""
    configs = get_server_configs()
    click.echo(f"{'Service':<15} {'Status':<15} {'Description'}")
    click.echo("-" * 60)
    for name, config in configs.items():
        status = get_container_status(config["container_name"])
        status_display = {
            "running": "✅ Running",
            "exited": "🛑 Stopped",
            "not_created": "⚪ Not Installed",
        }.get(status, f"❓ {status}")

        click.echo(f"{name:<15} {status_display:<15} {config['description']}")

    click.echo("\nRun 'vibe servers install <service>' to set up a new server.")


@servers_cli.command()
@click.argument("service")
def install(service):
    """Install and start a development server."""
    configs = get_server_configs()

    # Handle generic 'minio' alias
    if service == "minio":
        click.echo("Which MinIO version would you like to install?")
        click.echo("1. Linode-style (port 9000, path-style addressing)")
        click.echo("2. AWS-style (port 9010, virtual-style addressing)")
        choice = click.prompt("Select option", type=int, default=1)
        service = "minio-linode" if choice == 1 else "minio-aws"

    if service not in configs:
        click.echo(
            f"❌ Unknown service: {service}. Available: {', '.join(configs.keys())}"
        )
        return

    config = configs[service]
    container_name = config["container_name"]
    status = get_container_status(container_name)

    if status != "not_created":
        click.echo(f"Server '{service}' is already installed (status: {status}).")
        if click.confirm("Do you want to recreate it?"):
            run_command(["docker", "rm", "-f", container_name])
        else:
            return

    click.echo(f"Installing {service}...")

    cmd = ["docker", "run", "-d", "--name", container_name, "--restart", "always"]

    for container_port, host_port in config.get("ports", {}).items():
        cmd.extend(["-p", f"{host_port}:{container_port}"])

    for key, value in config.get("env", {}).items():
        cmd.extend(["-e", f"{key}={value}"])

    cmd.append(config["image"])

    if "command" in config:
        import shlex

        cmd.extend(shlex.split(config["command"]))

    stdout, code = run_command(cmd, check=False)
    if code == 0:
        click.echo(f"✅ {service} installed and started successfully.")

        # Save connection details to global config
        from vibe_tools.utils import load_config

        global_config = load_config()  # This now includes global config
        services = global_config.setdefault("services", {})

        # Determine the host port (assuming localhost)
        # In a real scenario we might want to be more sophisticated here
        host_port = (
            list(config.get("ports", {}).values())[0] if config.get("ports") else None
        )

        service_details = {
            "host": "localhost",
            "port": host_port,
            "docker_container_name": container_name,
        }

        # Add default credentials if present in env
        if "env" in config:
            if "POSTGRES_USER" in config["env"]:
                service_details["user"] = config["env"]["POSTGRES_USER"]
            if "POSTGRES_PASSWORD" in config["env"]:
                service_details["password"] = config["env"]["POSTGRES_PASSWORD"]
            if "MINIO_ROOT_USER" in config["env"]:
                service_details["access_key"] = config["env"]["MINIO_ROOT_USER"]
            if "MINIO_ROOT_PASSWORD" in config["env"]:
                service_details["secret_key"] = config["env"]["MINIO_ROOT_PASSWORD"]

        # Handle service specific key names
        save_key = service
        if service == "minio-linode":
            save_key = "s3-linode"
            service_details["region"] = "us-east-1"
            service_details["addressing_style"] = "path"
            service_details["signature_version"] = "s3v4"
            if "9001/tcp" in config.get("ports", {}):
                service_details["console_port"] = config["ports"]["9001/tcp"]
        elif service == "minio-aws":
            save_key = "s3-aws"
            service_details["region"] = "us-east-1"
            service_details["addressing_style"] = "virtual"
            service_details["signature_version"] = "s3v4"
            if "9011/tcp" in config.get("ports", {}):
                service_details["console_port"] = config["ports"]["9011/tcp"]

        services[save_key] = service_details
        save_config(global_config, global_scope=True)
        click.echo("✅ Saved connection details to global config.")
    else:
        click.echo(f"❌ Failed to install {service}: {stdout}")


@servers_cli.command()
def status():
    """Show detailed status of all servers."""
    configs = get_server_configs()
    click.echo(f"{'Service':<15} {'Container':<20} {'Status':<15} {'Ports'}")
    click.echo("-" * 70)
    for name, config in configs.items():
        container_name = config["container_name"]
        status = get_container_status(container_name)
        status_display = {
            "running": "✅ Running",
            "exited": "🛑 Stopped",
            "not_created": "⚪ Not Installed",
        }.get(status, f"❓ {status}")

        ports = ", ".join([f"{v}->{k}" for k, v in config.get("ports", {}).items()])
        click.echo(f"{name:<15} {container_name:<20} {status_display:<15} {ports}")


@servers_cli.command()
@click.argument("service", required=False)
def start(service):
    """Start one or all development servers."""
    configs = get_server_configs()

    if not service or service == "all":
        click.echo("Starting all installed servers...")
        for name in configs:
            container_name = configs[name]["container_name"]
            status = get_container_status(container_name)
            if status == "exited":
                click.echo(f"Starting {name}...")
                run_command(["docker", "start", container_name], check=False)
        return

    if service not in configs:
        click.echo(f"❌ Unknown service: {service}")
        return

    config = configs[service]
    container_name = config["container_name"]
    status = get_container_status(container_name)

    if status == "running":
        click.echo(f"Server '{service}' is already running.")
        return
    if status == "not_created":
        click.echo(
            f"Server '{service}' is not installed. Use 'vibe servers install {service}' first."
        )
        return

    click.echo(f"Starting {service}...")
    stdout, code = run_command(["docker", "start", container_name], check=False)
    if code == 0:
        click.echo(f"✅ {service} started.")
    else:
        click.echo(f"❌ Failed to start {service}: {stdout}")


@servers_cli.command()
@click.argument("service", required=False)
def stop(service):
    """Stop one or all development servers."""
    configs = get_server_configs()

    if not service or service == "all":
        click.echo("Stopping all running servers...")
        for name in configs:
            container_name = configs[name]["container_name"]
            status = get_container_status(container_name)
            if status == "running":
                click.echo(f"Stopping {name}...")
                run_command(["docker", "stop", container_name], check=False)
        return

    if service not in configs:
        click.echo(f"❌ Unknown service: {service}")
        return

    config = configs[service]
    container_name = config["container_name"]
    status = get_container_status(container_name)

    if status != "running":
        click.echo(f"Server '{service}' is not running.")
        return

    click.echo(f"Stopping {service}...")
    stdout, code = run_command(["docker", "stop", container_name], check=False)
    if code == 0:
        click.echo(f"✅ {service} stopped.")
    else:
        click.echo(f"❌ Failed to stop {service}: {stdout}")


@servers_cli.command()
@click.argument("service", required=False)
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def logs(service, follow):
    """View logs for one or all development servers."""
    configs = get_server_configs()

    if not service or service == "all":
        container_names = [
            c["container_name"]
            for c in configs.values()
            if get_container_status(c["container_name"]) != "not_created"
        ]
        if not container_names:
            click.echo("No installed servers found.")
            return

        cmd = ["docker", "logs"]
        if follow:
            cmd.append("-f")
        cmd.extend(container_names)

        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            pass
        return

    if service not in configs:
        click.echo(f"❌ Unknown service: {service}")
        return

    config = configs[service]
    container_name = config["container_name"]

    cmd = ["docker", "logs"]
    if follow:
        cmd.append("-f")
    cmd.append(container_name)

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass


@servers_cli.command()
@click.argument("service")
def remove(service):
    """Remove a development server container."""
    configs = get_server_configs()
    if service not in configs:
        click.echo(f"❌ Unknown service: {service}")
        return
    config = configs[service]
    container_name = config["container_name"]

    if get_container_status(container_name) == "not_created":
        click.echo(f"Server '{service}' is not installed.")
        return

    if click.confirm(
        f"Are you sure you want to remove the '{service}' container? All data in the container will be lost."
    ):
        click.echo(f"Removing {service}...")
        stdout, code = run_command(["docker", "rm", "-f", container_name], check=False)
        if code == 0:
            click.echo(f"✅ {service} removed.")
        else:
            click.echo(f"❌ Failed to remove {service}: {stdout}")


if __name__ == "__main__":
    servers_cli()
