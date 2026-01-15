import json
import pathlib
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

import click

from vibe_tools.servers import get_container_status, get_server_configs
from vibe_tools.utils import (
    VIBE_PROJECT_DIR,
    load_config,
    run_command,
    safe_yaml_dump,
)

STAGING_DIR = VIBE_PROJECT_DIR / "staging"
STAGING_CONFIG_FILE = STAGING_DIR / "config.json"
DOCKER_COMPOSE_FILE = STAGING_DIR / "docker-compose.yml"
K8S_MANIFESTS_DIR = STAGING_DIR / "k8s"


def has_kubectl() -> bool:
    """Check if kubectl is installed."""
    try:
        stdout, code = run_command(["kubectl", "version", "--client"], check=False)
        return code == 0
    except Exception:
        return False


def has_k8s_cluster() -> bool:
    """Verify if a Kubernetes cluster is accessible."""
    if not has_kubectl():
        return False
    try:
        stdout, code = run_command(["kubectl", "cluster-info"], check=False)
        return code == 0
    except Exception:
        return False


def detect_k8s_type() -> Optional[str]:
    """Identify the type of Kubernetes cluster."""
    if not has_k8s_cluster():
        return None

    try:
        # Check for minikube
        stdout, code = run_command(["minikube", "status"], check=False)
        if code == 0 and "Running" in stdout:
            return "minikube"

        # Check for kind
        stdout, code = run_command(["kind", "get", "clusters"], check=False)
        if code == 0 and stdout.strip():
            return "kind"

        # Check for Docker Desktop
        stdout, code = run_command(["kubectl", "config", "current-context"], check=False)
        if code == 0 and "docker-desktop" in stdout.lower():
            return "docker-desktop"

        # Generic k8s
        return "generic"
    except Exception:
        return "generic"


def detect_environment() -> str:
    """Detect whether to use Kubernetes or Docker Compose."""
    if has_kubectl() and has_k8s_cluster():
        return "kubernetes"
    return "docker-compose"


def get_docker_compose_cmd() -> Optional[List[str]]:
    """Get the docker compose command (v2 or v1)."""
    for cmd in [["docker", "compose"], ["docker-compose"]]:
        stdout, code = run_command(cmd + ["--version"], check=False)
        if code == 0:
            return cmd
    return None


def check_existing_container(service_key: str, server_key: str) -> Optional[str]:
    """Check if a vibe servers container is running for this service."""
    server_configs = get_server_configs()
    if server_key not in server_configs:
        return None

    container_name = server_configs[server_key].get("container_name")
    if not container_name:
        return None

    status = get_container_status(container_name)
    if status == "running":
        return container_name
    return None


def get_required_services() -> Dict[str, Any]:
    """Get required services from config, integrating with vibe servers."""
    # First, get services from project config
    config = load_config()
    project_services = config.get("services", {})

    # Also get global server configs from vibe servers
    server_configs = get_server_configs()

    # Merge: project config takes precedence, but use server configs as defaults
    services = {}

    # Map vibe servers service names to project service keys
    service_mapping = {
        "postgres": "postgres",
        "redis": "redis",
        "rabbitmq": "rabbitmq",
        "elasticsearch": "elasticsearch",
        "minio-linode": "s3-linode",
        "minio-aws": "s3-aws",
        "mailhog": "mailhog",
        "imgproxy": "imgproxy",
    }

    for server_key, project_key in service_mapping.items():
        if server_key in server_configs:
            server_config = server_configs[server_key].copy()

            # If project has this service configured, merge the configs
            if project_key in project_services:
                project_config = project_services[project_key]
                # Use project config values but keep server defaults for missing fields
                for key, value in project_config.items():
                    server_config[key] = value
                # Preserve docker container info if present
                if "docker_container_name" in project_config:
                    server_config["docker_container_name"] = project_config["docker_container_name"]

            services[project_key] = server_config

    # Add any other services from project config that aren't in server configs
    for key, value in project_services.items():
        if key not in services:
            services[key] = value

    return services


def discover_application_services() -> List[Dict[str, Any]]:
    """Discover application services (frontend/backend) by checking for Dockerfiles."""
    app_services = []

    # Check for backend Dockerfile
    backend_dockerfile = pathlib.Path("Dockerfile")
    backend_dockerfile_alt = pathlib.Path("backend/Dockerfile")
    if backend_dockerfile.exists() or backend_dockerfile_alt.exists():
        dockerfile_path = backend_dockerfile if backend_dockerfile.exists() else backend_dockerfile_alt
        app_services.append({
            "name": "backend",
            "type": "backend",
            "dockerfile": str(dockerfile_path),
            "context": str(dockerfile_path.parent),
        })

    # Check for frontend Dockerfile
    frontend_dockerfile = pathlib.Path("frontend/Dockerfile")
    if frontend_dockerfile.exists():
        app_services.append({
            "name": "frontend",
            "type": "frontend",
            "dockerfile": str(frontend_dockerfile),
            "context": str(frontend_dockerfile.parent),
        })

    return app_services


def check_service_health(service_name: str, service_config: Dict[str, Any], env_type: str, check_reused: bool = True) -> Tuple[bool, str]:
    """Check if a service is healthy."""
    # First check if it's a reused container
    if check_reused and env_type != "kubernetes":
        # Try to find the original service key
        # server_configs = get_server_configs()
        # service_mapping = {
        #     "postgres": "postgres",
        #     "redis": "redis",
        #     "rabbitmq": "rabbitmq",
        #     "elasticsearch": "elasticsearch",
        #     "minio_linode": "s3-linode",
        #     "minio_aws": "s3-aws",
        #     "mailhog": "mailhog",
        #     "imgproxy": "imgproxy",
        # }
        # Reverse lookup
        for server_key, project_key in {
            "postgres": "postgres",
            "redis": "redis",
            "rabbitmq": "rabbitmq",
            "elasticsearch": "elasticsearch",
            "minio-linode": "s3-linode",
            "minio-aws": "s3-aws",
            "mailhog": "mailhog",
            "imgproxy": "imgproxy",
        }.items():
            docker_name = project_key.replace("s3-", "minio-").replace("-", "_")
            if docker_name == service_name:
                existing = check_existing_container(project_key, server_key)
                if existing:
                    # Check the existing container
                    status = get_container_status(existing)
                    if status == "running":
                        return True, "reused (running)"
                    return False, f"reused ({status})"
                break

    if env_type == "kubernetes":
        namespace = get_staging_namespace()
        # Normalize service name for k8s (remove underscores, use lowercase)
        k8s_service_name = service_name.replace("_", "").lower()
        try:
            stdout, code = run_command(
                ["kubectl", "get", "pod", "-l", f"app={k8s_service_name}", "-n", namespace, "-o", "json"],
                check=False
            )
            if code == 0:
                pods = json.loads(stdout)
                if pods.get("items"):
                    pod = pods["items"][0]
                    status = pod.get("status", {})
                    phase = status.get("phase", "Unknown")
                    if phase == "Running":
                        # Check if ready
                        conditions = status.get("conditions", [])
                        for condition in conditions:
                            if condition.get("type") == "Ready":
                                if condition.get("status") == "True":
                                    return True, "healthy"
                        return False, "not ready"
                    return False, phase.lower()
            return False, "not found"
        except Exception as e:
            return False, f"error: {str(e)}"
    else:
        # Docker Compose
        container_name = f"vibe-staging-{service_name}"
        status = get_container_status(container_name)
        if status == "running":
            # Try to check if service is actually responding
            host = service_config.get("host", "localhost")
            port = service_config.get("port")
            if port:
                try:
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex((host, int(port)))
                    sock.close()
                    if result == 0:
                        return True, "healthy"
                    return False, "port not responding"
                except Exception:
                    pass
            return True, "running"
        return False, status


def get_staging_namespace() -> str:
    """Get the staging namespace name."""
    config = load_staging_config()
    return config.get("namespace", "vibe-staging")


def load_staging_config() -> Dict[str, Any]:
    """Load staging configuration."""
    if STAGING_CONFIG_FILE.exists():
        try:
            return json.loads(STAGING_CONFIG_FILE.read_text())
        except Exception:
            pass
    return {
        "namespace": "vibe-staging",
        "environment": None,
        "services": {},
    }


def save_staging_config(config: Dict[str, Any]):
    """Save staging configuration."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_CONFIG_FILE.write_text(json.dumps(config, indent=2))


def generate_docker_compose(services: Dict[str, Any], app_services: List[Dict[str, Any]], isolated: bool = False) -> Dict[str, Any]:
    """Generate Docker Compose configuration from service configs."""
    compose = {
        "version": "3.8",
        "services": {},
        "networks": {
            "vibe-staging": {
                "driver": "bridge"
            }
        }
    }

    # Add infrastructure services
    for service_key, service_config in services.items():
        # Map service keys to docker service names
        service_name = service_key.replace("s3-", "minio-").replace("-", "_")
        container_name = f"vibe-staging-{service_name}"

        # Get server config for defaults
        server_configs = get_server_configs()
        server_key = None
        for sk in ["postgres", "redis", "rabbitmq", "elasticsearch", "minio-linode", "minio-aws", "mailhog", "imgproxy"]:
            if (service_key == sk or
                (service_key == "s3-linode" and sk == "minio-linode") or
                (service_key == "s3-aws" and sk == "minio-aws")):
                server_key = sk
                break

        # Check if we should reuse existing container
        existing_container = None
        if not isolated and server_key:
            existing_container = check_existing_container(service_key, server_key)

        if existing_container:
            # Skip creating service - we'll reuse the existing container
            # App services will connect via localhost:port
            continue

        if server_key and server_key in server_configs:
            server_config = server_configs[server_key]
            compose_service = {
                "image": server_config.get("image"),
                "container_name": container_name,
                "networks": ["vibe-staging"],
                "restart": "unless-stopped",
            }

            # Add ports
            if "port" in service_config:
                port = service_config["port"]
                if server_key == "postgres":
                    compose_service["ports"] = [f"{port}:5432"]
                elif server_key == "redis":
                    compose_service["ports"] = [f"{port}:6379"]
                elif server_key == "rabbitmq":
                    compose_service["ports"] = [f"{port}:5672", f"{service_config.get('management_port', 15672)}:15672"]
                elif server_key == "elasticsearch":
                    compose_service["ports"] = [f"{port}:9200"]
                elif server_key in ["minio-linode", "minio-aws"]:
                    compose_service["ports"] = [
                        f"{port}:9000",
                        f"{service_config.get('console_port', port + 1)}:9001"
                    ]
                elif server_key == "mailhog":
                    compose_service["ports"] = [f"{port}:1025", f"{service_config.get('web_port', 8025)}:8025"]
                elif server_key == "imgproxy":
                    compose_service["ports"] = [f"{port}:8080"]

            # Add environment variables
            env_vars = {}
            if server_key == "postgres":
                env_vars["POSTGRES_USER"] = service_config.get("user", "postgres")
                env_vars["POSTGRES_PASSWORD"] = service_config.get("password", "postgres")
                env_vars["POSTGRES_DB"] = service_config.get("database", "app_db")
            elif server_key in ["minio-linode", "minio-aws"]:
                env_vars["MINIO_ROOT_USER"] = service_config.get("access_key", "minioadmin")
                env_vars["MINIO_ROOT_PASSWORD"] = service_config.get("secret_key", "minioadmin")

            if env_vars:
                compose_service["environment"] = env_vars

            # Add command if specified in server config
            if "command" in server_config:
                compose_service["command"] = server_config["command"]

            # Add volumes for data persistence
            if server_key in ["postgres", "minio-linode", "minio-aws", "elasticsearch"]:
                compose_service["volumes"] = [f"{container_name}-data:/data"]

            compose["services"][service_name] = compose_service

    # Add volumes
    volumes = {}
    for service_name, service_def in compose["services"].items():
        container_name = service_def.get("container_name", f"vibe-staging-{service_name}")
        if "volumes" in service_def:
            # Extract volume name from volumes list
            for vol in service_def["volumes"]:
                if isinstance(vol, str) and vol.endswith(":/data"):
                    vol_name = vol.split(":")[0]
                    volumes[vol_name] = {}
    if volumes:
        compose["volumes"] = volumes

    # Track which services are being reused (not in compose)
    reused_services = set()
    if not isolated:
        server_configs = get_server_configs()
        service_mapping = {
            "postgres": "postgres",
            "redis": "redis",
            "rabbitmq": "rabbitmq",
            "elasticsearch": "elasticsearch",
            "minio-linode": "s3-linode",
            "minio-aws": "s3-aws",
            "mailhog": "mailhog",
            "imgproxy": "imgproxy",
        }
        for server_key, project_key in service_mapping.items():
            if project_key in services:
                existing = check_existing_container(project_key, server_key)
                if existing:
                    reused_services.add(project_key)

    # Add application services
    for app_service in app_services:
        service_name = app_service["name"]
        compose["services"][service_name] = {
            "build": {
                "context": app_service["context"],
                "dockerfile": app_service["dockerfile"],
            },
            "container_name": f"vibe-staging-{service_name}",
            "networks": ["vibe-staging"],
            "depends_on": list(compose["services"].keys()),
            "restart": "unless-stopped",
        }

        # Add environment variables for service discovery
        env_vars = {}
        for service_key, service_config in services.items():
            env_name = service_key.upper().replace("-", "_")
            if service_key in reused_services:
                # Reused services are on host network, use host.docker.internal or localhost
                env_vars[f"{env_name}_HOST"] = "host.docker.internal"
            else:
                # New services use service name in docker network
                docker_service_name = service_key.replace("s3-", "minio-").replace("-", "_")
                env_vars[f"{env_name}_HOST"] = docker_service_name
            if "port" in service_config:
                env_vars[f"{env_name}_PORT"] = str(service_config["port"])
        if env_vars:
            compose["services"][service_name]["environment"] = env_vars

        # If reusing services, also add extra_hosts for host.docker.internal
        if reused_services:
            compose["services"][service_name]["extra_hosts"] = ["host.docker.internal:host-gateway"]

    return compose


def generate_k8s_manifests(services: Dict[str, Any], app_services: List[Dict[str, Any]], namespace: str, isolated: bool = False) -> List[Dict[str, Any]]:
    """Generate Kubernetes manifests from service configs."""
    manifests = []

    # Namespace manifest
    manifests.append({
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": namespace}
    })

    server_configs = get_server_configs()

    # Check for existing services if not isolated
    reused_services = set()
    if not isolated:
        for service_key in services.keys():
            server_key = None
            for sk in ["postgres", "redis", "rabbitmq", "elasticsearch", "minio-linode", "minio-aws", "mailhog", "imgproxy"]:
                if (service_key == sk or
                    (service_key == "s3-linode" and sk == "minio-linode") or
                    (service_key == "s3-aws" and sk == "minio-aws")):
                    server_key = sk
                    break
            # For k8s, check if service exists in default namespace
            if server_key:
                try:
                    stdout, code = run_command(
                        ["kubectl", "get", "service", server_key, "-n", "default", "-o", "json"],
                        check=False
                    )
                    if code == 0:
                        reused_services.add(service_key)
                except Exception:
                    pass

    # Generate manifests for infrastructure services
    for service_key, service_config in services.items():
        server_key = None
        for sk in ["postgres", "redis", "rabbitmq", "elasticsearch", "minio-linode", "minio-aws", "mailhog", "imgproxy"]:
            if (service_key == sk or
                (service_key == "s3-linode" and sk == "minio-linode") or
                (service_key == "s3-aws" and sk == "minio-aws")):
                server_key = sk
                break

        if not server_key or server_key not in server_configs:
            continue

        server_config = server_configs[server_key]
        service_name = service_key.replace("s3-", "minio-").replace("-", "")

        # If reusing, create ExternalName service instead of deployment
        if service_key in reused_services:
            # Create ExternalName service pointing to existing service in default namespace
            # ExternalName services don't need ports - they just alias the external service
            service = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": service_name,
                    "namespace": namespace
                },
                "spec": {
                    "type": "ExternalName",
                    "externalName": f"{server_key}.default.svc.cluster.local"
                }
            }

            manifests.append(service)
            continue

        # Deployment
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "labels": {"app": service_name}
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": service_name}},
                "template": {
                    "metadata": {"labels": {"app": service_name}},
                    "spec": {
                        "containers": [{
                            "name": service_name,
                            "image": server_config.get("image"),
                            "ports": []
                        }]
                    }
                }
            }
        }

        # Add ports
        if "port" in service_config:
            if server_key == "postgres":
                deployment["spec"]["template"]["spec"]["containers"][0]["ports"].append({"containerPort": 5432})
            elif server_key == "redis":
                deployment["spec"]["template"]["spec"]["containers"][0]["ports"].append({"containerPort": 6379})
            elif server_key == "rabbitmq":
                deployment["spec"]["template"]["spec"]["containers"][0]["ports"].extend([
                    {"containerPort": 5672},
                    {"containerPort": 15672}
                ])
            elif server_key == "elasticsearch":
                deployment["spec"]["template"]["spec"]["containers"][0]["ports"].append({"containerPort": 9200})
            elif server_key in ["minio-linode", "minio-aws"]:
                deployment["spec"]["template"]["spec"]["containers"][0]["ports"].extend([
                    {"containerPort": 9000},
                    {"containerPort": 9001}
                ])
            elif server_key == "mailhog":
                deployment["spec"]["template"]["spec"]["containers"][0]["ports"].extend([
                    {"containerPort": 1025},
                    {"containerPort": 8025}
                ])
            elif server_key == "imgproxy":
                deployment["spec"]["template"]["spec"]["containers"][0]["ports"].append({"containerPort": 8080})

        # Add environment variables
        env_vars = []
        if server_key == "postgres":
            env_vars.extend([
                {"name": "POSTGRES_USER", "value": service_config.get("user", "postgres")},
                {"name": "POSTGRES_PASSWORD", "value": service_config.get("password", "postgres")},
                {"name": "POSTGRES_DB", "value": service_config.get("database", "app_db")}
            ])
        elif server_key in ["minio-linode", "minio-aws"]:
            env_vars.extend([
                {"name": "MINIO_ROOT_USER", "value": service_config.get("access_key", "minioadmin")},
                {"name": "MINIO_ROOT_PASSWORD", "value": service_config.get("secret_key", "minioadmin")}
            ])

        if env_vars:
            deployment["spec"]["template"]["spec"]["containers"][0]["env"] = env_vars

        # Add command if specified
        if "command" in server_config:
            import shlex
            deployment["spec"]["template"]["spec"]["containers"][0]["command"] = shlex.split(server_config["command"])

        manifests.append(deployment)

        # Service
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": service_name,
                "namespace": namespace
            },
            "spec": {
                "selector": {"app": service_name},
                "ports": []
            }
        }

        if "port" in service_config:
            if server_key == "postgres":
                service["spec"]["ports"].append({"port": 5432, "targetPort": 5432})
            elif server_key == "redis":
                service["spec"]["ports"].append({"port": 6379, "targetPort": 6379})
            elif server_key == "rabbitmq":
                service["spec"]["ports"].extend([
                    {"port": 5672, "targetPort": 5672},
                    {"port": 15672, "targetPort": 15672, "name": "management"}
                ])
            elif server_key == "elasticsearch":
                service["spec"]["ports"].append({"port": 9200, "targetPort": 9200})
            elif server_key in ["minio-linode", "minio-aws"]:
                service["spec"]["ports"].extend([
                    {"port": 9000, "targetPort": 9000},
                    {"port": 9001, "targetPort": 9001, "name": "console"}
                ])
            elif server_key == "mailhog":
                service["spec"]["ports"].extend([
                    {"port": 1025, "targetPort": 1025},
                    {"port": 8025, "targetPort": 8025, "name": "web"}
                ])
            elif server_key == "imgproxy":
                service["spec"]["ports"].append({"port": 8080, "targetPort": 8080})

        manifests.append(service)

    # Add application services
    for app_service in app_services:
        service_name = app_service["name"]

        # Deployment
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "labels": {"app": service_name}
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": service_name}},
                "template": {
                    "metadata": {"labels": {"app": service_name}},
                    "spec": {
                        "containers": [{
                            "name": service_name,
                            "image": f"vibe-staging-{service_name}:latest",
                            "imagePullPolicy": "Never",  # Use local image
                            "ports": [{"containerPort": 8080}]
                        }]
                    }
                }
            }
        }

        # Add environment variables for service discovery
        env_vars = []
        for service_key, service_config in services.items():
            env_name = service_key.upper().replace("-", "_")
            infra_service_name = service_key.replace("s3-", "minio-").replace("-", "")
            # For reused services, use the service name in staging namespace (ExternalName will resolve)
            env_vars.append({
                "name": f"{env_name}_HOST",
                "value": infra_service_name
            })
            if "port" in service_config:
                env_vars.append({
                    "name": f"{env_name}_PORT",
                    "value": str(service_config["port"])
                })

        if env_vars:
            deployment["spec"]["template"]["spec"]["containers"][0]["env"] = env_vars

        manifests.append(deployment)

        # Service
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": service_name,
                "namespace": namespace
            },
            "spec": {
                "selector": {"app": service_name},
                "ports": [{"port": 80, "targetPort": 8080}]
            }
        }
        manifests.append(service)

    return manifests


@click.group()
def staging_cli():
    """Manage local staging environment for complete system testing."""
    pass


@staging_cli.command()
@click.option("--isolated", is_flag=True, default=False, help="Create isolated containers instead of reusing existing vibe servers containers")
def up(isolated):
    """Start the complete staging environment. By default, reuses existing vibe servers containers."""
    env_type = detect_environment()
    click.echo(f"Detected environment: {env_type}")

    if isolated:
        click.echo("Mode: Isolated (creating new containers)")
    else:
        click.echo("Mode: Reuse (connecting to existing vibe servers containers)")

    if env_type == "kubernetes":
        k8s_type = detect_k8s_type()
        click.echo(f"Kubernetes cluster type: {k8s_type}")

    # Get services
    services = get_required_services()
    app_services = discover_application_services()

    click.echo(f"Found {len(services)} infrastructure services")
    click.echo(f"Found {len(app_services)} application services")

    # Check for existing containers if not isolated
    if not isolated:
        click.echo("\nChecking for existing vibe servers containers...")
        reused_count = 0
        for service_key in services.keys():
            server_key = None
            for sk in ["postgres", "redis", "rabbitmq", "elasticsearch", "minio-linode", "minio-aws", "mailhog", "imgproxy"]:
                if (service_key == sk or
                    (service_key == "s3-linode" and sk == "minio-linode") or
                    (service_key == "s3-aws" and sk == "minio-aws")):
                    server_key = sk
                    break
            if server_key:
                existing = check_existing_container(service_key, server_key)
                if existing:
                    click.echo(f"  ✓ {service_key}: reusing {existing}")
                    reused_count += 1
                else:
                    click.echo(f"  ✗ {service_key}: not running, will create new")
        if reused_count > 0:
            click.echo(f"\nReusing {reused_count} existing container(s)")

    # Save staging config
    namespace = get_staging_namespace()
    staging_config = {
        "namespace": namespace,
        "environment": env_type,
        "isolated": isolated,
        "services": {k: {"name": k} for k in services.keys()},
        "app_services": [s["name"] for s in app_services],
    }
    save_staging_config(staging_config)

    if env_type == "kubernetes":
        _setup_k8s_staging(services, app_services, namespace, isolated)
    else:
        _setup_docker_compose_staging(services, app_services, isolated)


def _setup_k8s_staging(services: Dict[str, Any], app_services: List[Dict[str, Any]], namespace: str, isolated: bool = False):
    """Set up Kubernetes staging environment."""
    K8S_MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate manifests
    manifests = generate_k8s_manifests(services, app_services, namespace, isolated)

    # Write manifests
    for i, manifest in enumerate(manifests):
        kind = manifest.get("kind", "unknown").lower()
        name = manifest.get("metadata", {}).get("name", f"resource{i}")
        filename = f"{kind}-{name}.yaml"
        filepath = K8S_MANIFESTS_DIR / filename
        filepath.write_text(safe_yaml_dump(manifest))

    # Create namespace
    click.echo(f"Creating namespace: {namespace}")
    run_command(["kubectl", "create", "namespace", namespace], check=False)

    # Apply manifests
    click.echo("Applying Kubernetes manifests...")
    for manifest_file in sorted(K8S_MANIFESTS_DIR.glob("*.yaml")):
        click.echo(f"  Applying {manifest_file.name}...")
        stdout, code = run_command(
            ["kubectl", "apply", "-f", str(manifest_file), "-n", namespace],
            check=False
        )
        if code != 0:
            click.echo(f"  ⚠️  Warning: {stdout}")

    # Build and load application images for local k8s
    k8s_type = detect_k8s_type()
    for app_service in app_services:
        service_name = app_service["name"]
        click.echo(f"Building image for {service_name}...")

        # Build Docker image
        dockerfile_path = pathlib.Path(app_service["dockerfile"])
        context = pathlib.Path(app_service["context"])
        image_name = f"vibe-staging-{service_name}:latest"

        stdout, code = run_command(
            ["docker", "build", "-t", image_name, "-f", str(dockerfile_path), str(context)],
            check=False
        )
        if code != 0:
            click.echo(f"  ❌ Failed to build {service_name}: {stdout}")
            continue

        # Load into cluster
        if k8s_type == "minikube":
            click.echo("  Loading image into minikube...")
            run_command(["minikube", "image", "load", image_name], check=False)
        elif k8s_type == "kind":
            click.echo("  Loading image into kind...")
            # Get kind cluster name
            stdout, _ = run_command(["kind", "get", "clusters"], check=False)
            if stdout.strip():
                cluster_name = stdout.strip().split()[0]
                run_command(["kind", "load", "docker-image", image_name, "--name", cluster_name], check=False)
        # Docker Desktop doesn't need image loading

    click.echo("✅ Staging environment started")
    click.echo(f"  Namespace: {namespace}")
    click.echo("  View status: vibe-staging status")


def _setup_docker_compose_staging(services: Dict[str, Any], app_services: List[Dict[str, Any]], isolated: bool = False):
    """Set up Docker Compose staging environment."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    # Generate docker-compose.yml
    compose = generate_docker_compose(services, app_services, isolated)
    DOCKER_COMPOSE_FILE.write_text(safe_yaml_dump(compose))

    click.echo("Starting Docker Compose services...")
    compose_cmd = get_docker_compose_cmd()
    if not compose_cmd:
        click.echo("❌ docker-compose or docker compose not found")
        return

    stdout, code = run_command(
        compose_cmd + ["-f", str(DOCKER_COMPOSE_FILE), "up", "-d"],
        check=False
    )
    if code != 0:
        click.echo(f"❌ Failed to start services: {stdout}")
        return

    click.echo("✅ Staging environment started")
    click.echo(f"  Compose file: {DOCKER_COMPOSE_FILE}")
    click.echo("  View status: vibe-staging status")


@staging_cli.command()
def down():
    """Stop the staging environment."""
    config = load_staging_config()
    env_type = config.get("environment") or detect_environment()

    if env_type == "kubernetes":
        namespace = get_staging_namespace()
        click.echo(f"Deleting namespace: {namespace}")
        run_command(["kubectl", "delete", "namespace", namespace], check=False)
        click.echo("✅ Staging environment stopped")
    else:
        if DOCKER_COMPOSE_FILE.exists():
            click.echo("Stopping Docker Compose services...")
            compose_cmd = get_docker_compose_cmd()
            if compose_cmd:
                run_command(
                    compose_cmd + ["-f", str(DOCKER_COMPOSE_FILE), "down"],
                    check=False
                )
            click.echo("✅ Staging environment stopped")
        else:
            click.echo("No staging environment found")


@staging_cli.command()
def status():
    """Show status of all staging services."""
    config = load_staging_config()
    env_type = config.get("environment") or detect_environment()

    services = get_required_services()
    app_services = discover_application_services()

    click.echo(f"Environment: {env_type}")
    click.echo(f"{'Service':<20} {'Status':<15} {'Health'}")
    click.echo("-" * 60)

    for service_key, service_config in services.items():
        # Use display name that matches what's in docker-compose/k8s
        service_name = service_key.replace("s3-", "minio-").replace("-", "_")
        is_healthy, health_msg = check_service_health(service_name, service_config, env_type)
        status_icon = "✅" if is_healthy else "❌"
        # Show original service key for clarity
        display_name = service_key.replace("s3-", "minio-")
        click.echo(f"{display_name:<20} {status_icon:<15} {health_msg}")

    for app_service in app_services:
        service_name = app_service["name"]
        is_healthy, health_msg = check_service_health(service_name, {}, env_type)
        status_icon = "✅" if is_healthy else "❌"
        click.echo(f"{service_name:<20} {status_icon:<15} {health_msg}")


@staging_cli.command()
@click.argument("service", required=False)
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def logs(service, follow):
    """View logs for staging services."""
    config = load_staging_config()
    env_type = config.get("environment") or detect_environment()

    if env_type == "kubernetes":
        namespace = get_staging_namespace()
        if service:
            # Normalize service name for k8s
            k8s_service_name = service.replace("_", "").lower()
            cmd = ["kubectl", "logs", "-l", f"app={k8s_service_name}", "-n", namespace]
            if follow:
                cmd.append("-f")
            try:
                subprocess.run(cmd)
            except KeyboardInterrupt:
                pass
        else:
            click.echo("Please specify a service name")
    else:
        if DOCKER_COMPOSE_FILE.exists():
            compose_cmd = get_docker_compose_cmd()
            if compose_cmd:
                cmd = compose_cmd + ["-f", str(DOCKER_COMPOSE_FILE), "logs"]
                if service:
                    cmd.append(service)
                if follow:
                    cmd.append("-f")
                try:
                    subprocess.run(cmd)
                except KeyboardInterrupt:
                    pass
        else:
            click.echo("No staging environment found")


@staging_cli.command()
def health():
    """Check health of all staging services."""
    config = load_staging_config()
    env_type = config.get("environment") or detect_environment()

    services = get_required_services()
    app_services = discover_application_services()

    all_healthy = True

    click.echo("Health Check Results:")
    click.echo("-" * 60)

    for service_key, service_config in services.items():
        service_name = service_key.replace("s3-", "minio-").replace("-", "_")
        is_healthy, health_msg = check_service_health(service_name, service_config, env_type)
        if not is_healthy:
            all_healthy = False
        status_icon = "✅" if is_healthy else "❌"
        display_name = service_key.replace("s3-", "minio-")
        click.echo(f"{status_icon} {display_name}: {health_msg}")

    for app_service in app_services:
        service_name = app_service["name"]
        is_healthy, health_msg = check_service_health(service_name, {}, env_type)
        if not is_healthy:
            all_healthy = False
        status_icon = "✅" if is_healthy else "❌"
        click.echo(f"{status_icon} {service_name}: {health_msg}")

    if all_healthy:
        click.echo("\n✅ All services are healthy")
        return 0
    else:
        click.echo("\n❌ Some services are unhealthy")
        return 1


@staging_cli.command()
@click.option("--type", type=click.Choice(["integration", "regression", "all"]), default="all")
def test(type):
    """Run tests against the staging environment."""
    config = load_staging_config()
    env_type = config.get("environment") or detect_environment()

    # Wait for services to be ready
    click.echo("Waiting for services to be ready...")
    max_wait = 60
    waited = 0
    while waited < max_wait:
        all_ready = True
        services = get_required_services()
        for service_key, service_config in services.items():
            service_name = service_key.replace("s3-", "minio-").replace("-", "_")
            is_healthy, _ = check_service_health(service_name, service_config, env_type)
            if not is_healthy:
                all_ready = False
                break
        if all_ready:
            break
        time.sleep(2)
        waited += 2
        click.echo(".", nl=False)

    click.echo()

    if waited >= max_wait:
        click.echo("⚠️  Some services may not be ready, proceeding anyway...")

    # Run tests
    from vibe_tools.testing import ProjectTester

    tester = ProjectTester()

    if type in ["integration", "all"]:
        click.echo("Running integration tests...")
        if tester.has_make_target("test-integration"):
            stdout, code = run_command(["make", "test-integration"], check=False)
            if code != 0:
                click.echo(f"❌ Integration tests failed: {stdout}")
                return code
        else:
            click.echo("⚠️  No test-integration target found in Makefile")

    if type in ["regression", "all"]:
        click.echo("Running regression tests...")
        if tester.has_make_target("test-regression"):
            stdout, code = run_command(["make", "test-regression"], check=False)
            if code != 0:
                click.echo(f"❌ Regression tests failed: {stdout}")
                return code
        else:
            click.echo("⚠️  No test-regression target found in Makefile")

    click.echo("✅ All tests passed")
    return 0


if __name__ == "__main__":
    staging_cli()
