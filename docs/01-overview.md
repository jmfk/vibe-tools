# Overview

## System Purpose

vibe-tools is a CLI-first development automation system designed to maximize development velocity using AI-assisted tooling. It provides a comprehensive set of commands for managing the entire software development lifecycle, from requirements gathering to implementation and testing.

## Philosophy

The system follows a **CLI-First** philosophy with a Desktop companion, prioritizing terminal interactions and automated developer workflows while providing a rich GUI for visualization and complex management tasks.

## Key Features

- **PRD-Driven Development**: Changes start with Product Requirements Documents (PRDs) in `product/`, which are normalized into machine-readable YAML plans
- **AI Agent Integration**: Seamless integration with AI agents for automated implementation
- **Desktop Dashboard**: Tauri-based desktop app for project overview and management
- **Interactive Tools**: Built-in interactive shells for architecture (`vibe architect`) and product management (`vibe pm`)
- **Cost Tracking**: Built-in LLM cost tracking with Google Sheets integration
- **Test Coverage Automation**: Automated loops for improving test coverage and fixing failing tests
- **Reconciliation Loops**: Automated reconciliation between desired and actual system state

## Quick Start

### Installation

```bash
pipx install -e .
```

This installs the following CLI commands:
- `vibe` - Main command-line interface
- `vibe-setup` - Tool configuration

To run the Desktop app:
```bash
cargo tauri dev
```

### Initial Setup

1. **Initialize the project structure:**
   ```bash
   vibe init
   ```

2. **Configure API access:**
   ```bash
   vibe-setup api
   ```
   This configures API keys for Google Gemini and other LLM providers.

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
├── src-tauri/       # Desktop application (Rust + Frontend)
├── product/         # Markdown PRDs and specifications
├── prompts/         # AI prompt templates
├── implementation/  # Generated and runtime data
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
