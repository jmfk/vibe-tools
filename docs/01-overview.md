# Overview

## System Purpose

vibe-tools is a CLI-first development automation system designed to maximize development velocity using AI-assisted tooling. It provides a comprehensive set of commands for managing the entire software development lifecycle, from requirements gathering to implementation, testing, and deployment.

## Philosophy

The system follows a **CLI-First** philosophy, prioritizing terminal interactions and automated developer workflows. All infrastructure and common tasks are driven through command-line interfaces, enabling developers to work efficiently without switching between multiple tools or interfaces.

## Key Features

- **PRD-Driven Development**: Changes start with Product Requirements Documents (PRDs) in `product/`, which are normalized into machine-readable YAML plans
- **AI Agent Integration**: Seamless integration with Cursor Ralph and other AI agents for automated implementation
- **Interactive Tools**: Built-in interactive shells for architecture (`vibe architect`) and product management (`vibe pm`)
- **Infrastructure Management**: Automated setup and management of local development servers (Postgres, Redis, RabbitMQ, etc.)
- **Cost Tracking**: Built-in LLM cost tracking with Google Sheets integration
- **Test Coverage Automation**: Automated loops for improving test coverage and fixing failing tests
- **Reconciliation Loops**: Automated reconciliation between desired and actual system state

## Quick Start

### Installation

```bash
pip install -e .
```

This installs the following CLI commands:
- `vibe` - Main command-line interface
- `vibe-setup` - Service configuration tool
- `vibe-servers` - Local server management
- `vibe-staging` - Staging environment management

### Initial Setup

1. **Initialize the project structure:**
   ```bash
   vibe init
   ```

2. **Configure API access:**
   ```bash
   vibe-setup api
   ```
   This configures API keys for Google Gemini/DSPy and other LLM providers.

3. **Configure Google Sheets (optional):**
   ```bash
   vibe-setup google
   ```
   This enables cost logging to Google Sheets.

4. **Set up local services:**
   ```bash
   vibe-setup postgres
   vibe-setup redis
   # ... other services as needed
   ```

### Basic Usage

**Check system status:**
```bash
vibe status
```

**Create a new PRD:**
```bash
vibe pm
# Then use interactive commands to create specifications
```

**Normalize specs to PRDs:**
```bash
vibe normalize
```

**Run implementation:**
```bash
vibe implement
```

**Improve test coverage:**
```bash
vibe coverage
```


## Project Structure

```
/
├── vibe_tools/      # Core automation logic and CLI
├── product/           # Markdown PRDs and specifications
├── prompts/         # AI prompt templates
├── implementation/         # Architecture and infrastructure definitions (YAML)
│   ├── prds/        # Normalized PRD YAML files
│   ├── logs/        # Execution logs
│   ├── costs/       # Cost tracking data
│   └── instructions/ # Global agent instructions
└── tests/           # Comprehensive test suite
```

## Configuration

The system uses a `.vibe_config.json` file (stored in `implementation/config.json`) for configuration. This file is automatically created and updated when running setup commands.

See [Configuration](04-configuration.md) for detailed configuration options.

## Next Steps

- Read [Architecture](02-architecture.md) to understand the system design
- Review [CLI Commands](03-cli-commands.md) for available commands
- Learn about [PRD Workflow](05-prd-workflow.md) for development processes
- Explore [Interactive Tools](08-interactive-tools.md) for architecture and PM management
