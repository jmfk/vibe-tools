"""Infrastructure deployment generation for Kubernetes clusters on various platforms."""

import pathlib
from typing import Any, Dict, List, Optional


from vibe_tools.utils import INFRA_SPEC, INFRA_CURRENT, logger, safe_yaml_load
from vibe_tools.normalize import normalize_to_data

DEPLOYMENT_DIR = pathlib.Path("deployment")
TERRAFORM_DIR = DEPLOYMENT_DIR / "terraform"
CDK_DIR = DEPLOYMENT_DIR / "cdk"
K8S_DEPLOY_DIR = DEPLOYMENT_DIR / "k8s"
BUILD_DIR = DEPLOYMENT_DIR / "build"


def ensure_deployment_dirs():
    """Ensure deployment directories exist."""
    for dir_path in [DEPLOYMENT_DIR, TERRAFORM_DIR, CDK_DIR, K8S_DEPLOY_DIR, BUILD_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


def load_infrastructure_spec() -> Dict[str, Any]:
    """Load the infrastructure specification, normalizing just-in-time if needed."""
    if INFRA_CURRENT.exists():
        try:
            return safe_yaml_load(INFRA_CURRENT.read_text()) or {}
        except Exception:
            pass

    if not INFRA_SPEC.exists():
        logger.warning(f"Infrastructure spec {INFRA_SPEC} not found")
        return {}

    try:
        # Normalize just-in-time
        data = normalize_to_data(INFRA_SPEC.read_text(), "infrastructure")
        return data or {}
    except Exception as e:
        logger.error(f"Failed to load infrastructure spec from {INFRA_SPEC}: {e}")
        return {}


def generate_k8s_cluster_config(
    platform: str,
    region: str = "us-east-1",
    node_count: int = 3,
    node_size: str = "s-2vcpu-4gb",
    output_dir: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    """Generate Kubernetes cluster configuration for a target platform."""
    if output_dir is None:
        output_dir = K8S_DEPLOY_DIR / platform

    output_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "platform": platform,
        "region": region,
        "node_count": node_count,
        "node_size": node_size,
        "kubernetes_version": "1.28",
        "cluster_name": "vibe-cluster",
    }

    if platform == "linode":
        return generate_linode_k8s_config(config, output_dir)
    elif platform == "aws":
        return generate_aws_k8s_config(config, output_dir)
    elif platform == "hetzner":
        return generate_hetzner_k8s_config(config, output_dir)
    elif platform == "digitalocean":
        return generate_digitalocean_k8s_config(config, output_dir)
    elif platform == "bare-metal":
        return generate_bare_metal_k8s_config(config, output_dir)
    else:
        logger.warning(f"Unknown platform: {platform}")
        return {}


def generate_linode_k8s_config(
    config: Dict[str, Any], output_dir: pathlib.Path
) -> Dict[str, Any]:
    """Generate Terraform config for Linode Kubernetes cluster."""
    terraform_file = output_dir / "main.tf"

    terraform_content = f'''terraform {{
  required_version = ">= 1.0"
  
  required_providers {{
    linode = {{
      source  = "linode/linode"
      version = "~> 2.0"
    }}
  }}
}}

variable "linode_token" {{
  description = "Linode API token"
  type        = string
  sensitive    = true
}}

variable "region" {{
  description = "Linode region"
  type        = string
  default     = "{config["region"]}"
}}

variable "node_count" {{
  description = "Number of nodes in the cluster"
  type        = number
  default     = {config["node_count"]}
}}

variable "node_size" {{
  description = "Linode instance type"
  type        = string
  default     = "{config["node_size"]}"
}}

provider "linode" {{
  token = var.linode_token
}}

resource "linode_lke_cluster" "main" {{
  label       = "{config["cluster_name"]}"
  region      = var.region
  k8s_version  = "{config["kubernetes_version"]}"
  
  pool {{
    type  = var.node_size
    count = var.node_count
  }}
  
  tags = ["vibe", "kubernetes"]
}}

output "kubeconfig" {{
  description = "Kubeconfig for the cluster"
  value       = linode_lke_cluster.main.kubeconfig
  sensitive   = true
}}

output "api_endpoints" {{
  description = "API endpoints for the cluster"
  value       = linode_lke_cluster.main.api_endpoints
}}

output "status" {{
  description = "Status of the cluster"
  value       = linode_lke_cluster.main.status
}}
'''

    terraform_file.write_text(terraform_content)

    # Generate variables file
    terraform_vars = output_dir / "terraform.tfvars.example"
    terraform_vars.write_text("""linode_token = "your-linode-api-token-here"
region      = "us-east"
node_count  = 3
node_size   = "g6-standard-2"
""")

    # Generate README
    readme = output_dir / "README.md"
    readme.write_text("""# Linode Kubernetes Cluster Deployment

## Prerequisites
- Terraform >= 1.0
- Linode API token

## Setup
1. Copy `terraform.tfvars.example` to `terraform.tfvars`
2. Add your Linode API token
3. Run `terraform init`
4. Run `terraform plan`
5. Run `terraform apply`

## Outputs
After deployment, the kubeconfig will be available as a Terraform output.
""")

    return {"terraform_file": str(terraform_file), "platform": "linode"}


def generate_aws_k8s_config(
    config: Dict[str, Any], output_dir: pathlib.Path
) -> Dict[str, Any]:
    """Generate Terraform config for AWS EKS cluster."""
    terraform_file = output_dir / "main.tf"

    terraform_content = f'''terraform {{
  required_version = ">= 1.0"
  
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

variable "aws_region" {{
  description = "AWS region"
  type        = string
  default     = "{config["region"]}"
}}

variable "cluster_name" {{
  description = "EKS cluster name"
  type        = string
  default     = "{config["cluster_name"]}"
}}

variable "node_count" {{
  description = "Number of nodes in the cluster"
  type        = number
  default     = {config["node_count"]}
}}

variable "node_instance_type" {{
  description = "EC2 instance type for nodes"
  type        = string
  default     = "t3.medium"
}}

provider "aws" {{
  region = var.aws_region
}}

data "aws_availability_zones" "available" {{
  state = "available"
}}

resource "aws_vpc" "main" {{
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {{
    Name = "${{var.cluster_name}}-vpc"
  }}
}}

resource "aws_internet_gateway" "main" {{
  vpc_id = aws_vpc.main.id
  
  tags = {{
    Name = "${{var.cluster_name}}-igw"
  }}
}}

resource "aws_subnet" "private" {{
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${{count.index + 1}}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  tags = {{
    Name = "${{var.cluster_name}}-private-${{count.index + 1}}"
    "kubernetes.io/role/internal-elb" = "1"
  }}
}}

resource "aws_subnet" "public" {{
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${{count.index + 10}}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  
  tags = {{
    Name = "${{var.cluster_name}}-public-${{count.index + 1}}"
    "kubernetes.io/role/elb" = "1"
  }}
}}

resource "aws_eks_cluster" "main" {{
  name     = var.cluster_name
  role_arn = aws_iam_role.cluster.arn
  version  = "{config["kubernetes_version"]}"
  
  vpc_config {{
    subnet_ids = concat(aws_subnet.private[*].id, aws_subnet.public[*].id)
  }}
  
  depends_on = [
    aws_iam_role_policy_attachment.cluster_AmazonEKSClusterPolicy,
  ]
}}

resource "aws_iam_role" "cluster" {{
  name = "${{var.cluster_name}}-cluster-role"
  
  assume_role_policy = jsonencode({{
    Statement = [{{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {{
        Service = "eks.amazonaws.com"
      }}
    }}]
    Version = "2012-10-17"
  }})
}}

resource "aws_iam_role_policy_attachment" "cluster_AmazonEKSClusterPolicy" {{
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}}

# Node group would go here - simplified for brevity
# See AWS EKS documentation for complete node group setup

output "cluster_endpoint" {{
  description = "Endpoint for EKS control plane"
  value       = aws_eks_cluster.main.endpoint
}}

output "cluster_security_group_id" {{
  description = "Security group ID attached to the EKS cluster"
  value       = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}}
'''

    terraform_file.write_text(terraform_content)

    readme = output_dir / "README.md"
    readme.write_text("""# AWS EKS Cluster Deployment

## Prerequisites
- Terraform >= 1.0
- AWS CLI configured
- Appropriate IAM permissions

## Setup
1. Configure AWS credentials
2. Run `terraform init`
3. Run `terraform plan`
4. Run `terraform apply`

## Note
This is a simplified EKS configuration. For production, add:
- Node groups
- IAM roles for service accounts
- Load balancer controller
- Additional security configurations
""")

    return {"terraform_file": str(terraform_file), "platform": "aws"}


def generate_hetzner_k8s_config(
    config: Dict[str, Any], output_dir: pathlib.Path
) -> Dict[str, Any]:
    """Generate Terraform config for Hetzner Kubernetes cluster."""
    terraform_file = output_dir / "main.tf"

    terraform_content = f"""terraform {{
  required_version = ">= 1.0"
  
  required_providers {{
    hcloud = {{
      source  = "hetznercloud/hcloud"
      version = "~> 1.0"
    }}
  }}
}}

variable "hcloud_token" {{
  description = "Hetzner Cloud API token"
  type        = string
  sensitive   = true
}}

variable "location" {{
  description = "Hetzner location"
  type        = string
  default     = "nbg1"
}}

variable "node_count" {{
  description = "Number of nodes"
  type        = number
  default     = {config["node_count"]}
}}

variable "server_type" {{
  description = "Hetzner server type"
  type        = string
  default     = "cx21"
}}

provider "hcloud" {{
  token = var.hcloud_token
}}

# Hetzner doesn't have managed Kubernetes, so we'll use k3s
# This creates servers and installs k3s via cloud-init

resource "hcloud_ssh_key" "main" {{
  name       = "${{var.cluster_name}}-key"
  public_key = file("~/.ssh/id_rsa.pub")
}}

resource "hcloud_server" "master" {{
  name        = "${{var.cluster_name}}-master"
  image       = "ubuntu-22.04"
  server_type = var.server_type
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.main.id]
  
  user_data = <<-EOF
    #!/bin/bash
    curl -sfL https://get.k3s.io | sh -
  EOF
}}

resource "hcloud_server" "worker" {{
  count       = var.node_count
  name        = "${{var.cluster_name}}-worker-${{count.index + 1}}"
  image       = "ubuntu-22.04"
  server_type = var.server_type
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.main.id]
  
  user_data = <<-EOF
    #!/bin/bash
    # Get master token and join cluster
    # (Simplified - in production, use proper token management)
    curl -sfL https://get.k3s.io | K3S_URL=https://${{hcloud_server.master.ipv4_address}}:6443 K3S_TOKEN=... sh -
  EOF
}}

output "master_ip" {{
  description = "Master node IP"
  value       = hcloud_server.master.ipv4_address
}}
"""

    terraform_file.write_text(terraform_content)

    readme = output_dir / "README.md"
    readme.write_text("""# Hetzner k3s Cluster Deployment

## Prerequisites
- Terraform >= 1.0
- Hetzner Cloud API token
- SSH key pair

## Setup
1. Copy `terraform.tfvars.example` to `terraform.tfvars`
2. Add your Hetzner token
3. Run `terraform init`
4. Run `terraform plan`
5. Run `terraform apply`

## Note
This uses k3s (lightweight Kubernetes) on Hetzner Cloud.
""")

    return {"terraform_file": str(terraform_file), "platform": "hetzner"}


def generate_digitalocean_k8s_config(
    config: Dict[str, Any], output_dir: pathlib.Path
) -> Dict[str, Any]:
    """Generate Terraform config for DigitalOcean Kubernetes cluster."""
    terraform_file = output_dir / "main.tf"

    terraform_content = f'''terraform {{
  required_version = ">= 1.0"
  
  required_providers {{
    digitalocean = {{
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }}
  }}
}}

variable "do_token" {{
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}}

variable "region" {{
  description = "DigitalOcean region"
  type        = string
  default     = "nyc1"
}}

variable "node_count" {{
  description = "Number of nodes"
  type        = number
  default     = {config["node_count"]}
}}

variable "node_size" {{
  description = "Droplet size"
  type        = string
  default     = "s-2vcpu-4gb"
}}

provider "digitalocean" {{
  token = var.do_token
}}

resource "digitalocean_kubernetes_cluster" "main" {{
  name    = "{config["cluster_name"]}"
  region  = var.region
  version = "{config["kubernetes_version"]}"
  
  node_pool {{
    name       = "worker-pool"
    size       = var.node_size
    node_count = var.node_count
  }}
}}

output "kubeconfig" {{
  description = "Kubeconfig for the cluster"
  value       = digitalocean_kubernetes_cluster.main.kubeconfig[0].raw_config
  sensitive   = true
}}

output "endpoint" {{
  description = "API endpoint"
  value       = digitalocean_kubernetes_cluster.main.endpoint
}}
'''

    terraform_file.write_text(terraform_content)

    readme = output_dir / "README.md"
    readme.write_text("""# DigitalOcean Kubernetes Cluster Deployment

## Prerequisites
- Terraform >= 1.0
- DigitalOcean API token

## Setup
1. Copy `terraform.tfvars.example` to `terraform.tfvars`
2. Add your DigitalOcean token
3. Run `terraform init`
4. Run `terraform plan`
5. Run `terraform apply`
""")

    return {"terraform_file": str(terraform_file), "platform": "digitalocean"}


def generate_bare_metal_k8s_config(
    config: Dict[str, Any], output_dir: pathlib.Path
) -> Dict[str, Any]:
    """Generate SSH + cloud-init config for bare metal deployment."""
    readme = output_dir / "README.md"

    readme.write_text("""# Bare Metal Kubernetes Deployment

## Prerequisites
- SSH access to target machines
- cloud-init or similar provisioning system
- k3s or kubeadm

## Setup
1. Configure SSH access to target machines
2. Run the setup script for each machine
3. Initialize the cluster on the master node
4. Join worker nodes

## Files
- `setup-master.sh`: Master node setup script
- `setup-worker.sh`: Worker node setup script
- `inventory.example`: Example inventory file
""")

    # Generate master setup script
    master_script = output_dir / "setup-master.sh"
    master_script.write_text("""#!/bin/bash
set -e

# Install k3s
curl -sfL https://get.k3s.io | sh -

# Get kubeconfig
sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config
chmod 600 ~/.kube/config

# Get node token
sudo cat /var/lib/rancher/k3s/server/node-token > /tmp/k3s-token
echo "K3S_TOKEN saved to /tmp/k3s-token"
""")
    master_script.chmod(0o755)

    # Generate worker setup script
    worker_script = output_dir / "setup-worker.sh"
    worker_script.write_text("""#!/bin/bash
set -e

if [ -z "$K3S_URL" ] || [ -z "$K3S_TOKEN" ]; then
    echo "Error: K3S_URL and K3S_TOKEN must be set"
    exit 1
fi

curl -sfL https://get.k3s.io | K3S_URL="$K3S_URL" K3S_TOKEN="$K3S_TOKEN" sh -
""")
    worker_script.chmod(0o755)

    # Generate inventory example
    inventory = output_dir / "inventory.example"
    inventory.write_text("""[masters]
master1 ansible_host=192.168.1.10 ansible_user=root

[workers]
worker1 ansible_host=192.168.1.11 ansible_user=root
worker2 ansible_host=192.168.1.12 ansible_user=root
worker3 ansible_host=192.168.1.13 ansible_user=root
""")

    return {"platform": "bare-metal", "scripts": ["setup-master.sh", "setup-worker.sh"]}


def generate_docker_build_system(infra_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Docker build system configuration."""
    ensure_deployment_dirs()

    # Generate main Dockerfile if it doesn't exist
    dockerfile = DEPLOYMENT_DIR / "Dockerfile"
    if not dockerfile.exists():
        dockerfile.write_text("""FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml setup.py ./
RUN pip install --no-cache-dir -e .

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "-m", "vibe_tools.cli"]
""")

    # Generate docker-compose for building
    docker_compose_build = BUILD_DIR / "docker-compose.build.yml"
    docker_compose_build.write_text("""version: '3.8'

services:
  builder:
    build:
      context: ../..
      dockerfile: deployment/Dockerfile
    image: vibe-app:latest
    volumes:
      - ../../:/app
    command: /bin/bash
""")

    # Generate build script
    build_script = BUILD_DIR / "build.sh"
    build_script.write_text("""#!/bin/bash
set -e

echo "Building Docker images..."

# Build main application
docker build -t vibe-app:latest -f deployment/Dockerfile .

# Build frontend if it exists
if [ -d "frontend" ]; then
    cd frontend
    docker build -t vibe-frontend:latest -f Dockerfile .
    cd ..
fi

echo "✅ Build complete"
""")
    build_script.chmod(0o755)

    # Generate Makefile targets
    makefile_targets = BUILD_DIR / "Makefile.targets"
    makefile_targets.write_text("""
# Build targets (add to main Makefile)

.PHONY: build build-docker build-frontend build-all

build:
	@echo "Building application..."
	pip install -e .

build-docker:
	@echo "Building Docker image..."
	docker build -t vibe-app:latest -f deployment/Dockerfile .

build-frontend:
	@if [ -d "frontend" ]; then \\
		echo "Building frontend..."; \\
		cd frontend && npm run build; \\
	fi

build-all: build build-docker build-frontend
	@echo "✅ All builds complete"
""")

    return {
        "dockerfile": str(dockerfile),
        "build_script": str(build_script),
        "docker_compose": str(docker_compose_build),
    }


def generate_all_infrastructure(
    platforms: List[str] = None,
    build_system: bool = True,
) -> Dict[str, Any]:
    """Generate all infrastructure configurations."""
    if platforms is None:
        platforms = ["linode", "aws", "hetzner", "digitalocean", "bare-metal"]

    ensure_deployment_dirs()
    infra_spec = load_infrastructure_spec()

    results = {
        "platforms": {},
        "build_system": None,
    }

    # Generate platform configs
    for platform in platforms:
        try:
            config = generate_k8s_cluster_config(platform)
            results["platforms"][platform] = config
        except Exception as e:
            logger.error(f"Failed to generate config for {platform}: {e}")
            results["platforms"][platform] = {"error": str(e)}

    # Generate build system
    if build_system:
        try:
            results["build_system"] = generate_docker_build_system(infra_spec)
        except Exception as e:
            logger.error(f"Failed to generate build system: {e}")
            results["build_system"] = {"error": str(e)}

    return results
