# Development Guide

## Contributing to vibe-tools

This guide helps contributors understand the codebase structure and how to extend vibe-tools.

## Code Structure

### Package Organization

```
vibe_tools/
├── __init__.py           # Package initialization
├── cli.py                # Main CLI entry point
├── utils.py              # Core utilities and paths
├── ralph.py              # Ralph agent integration
├── architect.py          # Interactive architect tool
├── pm.py                 # Interactive PM tool
├── normalize.py          # PRD normalization
├── coverage.py           # Coverage improvement loops
├── fixer.py              # Test fixing automation
├── cost.py               # Cost tracking
├── servers.py            # Server management
├── setup.py              # Service configuration
├── testing.py            # Test execution utilities
├── templates.py          # File templates
└── commands/             # Individual command implementations
    ├── __init__.py       # Command registration
    ├── architect.py
    ├── pm.py
    └── ... (30+ commands)
```

### Key Modules

**`cli.py`**: Main entry point
- Command registration
- Global options handling
- Context management

**`utils.py`**: Core utilities
- Path definitions
- Configuration management
- Agent execution wrappers
- Git operations
- Logging setup

**`ralph.py`**: Agent integration
- Reconciliation loops
- Implementation orchestration
- Branch management

**`commands/`**: Command implementations
- One module per command
- Registered in `commands/__init__.py`

## Adding New Commands

### Step 1: Create Command Module

Create `vibe_tools/commands/new_command.py`:

```python
import click
from vibe_tools.utils import logger

def register_new_command(cli):
    @cli.command()
    @click.option("--flag", is_flag=True, help="Example flag")
    @click.pass_context
    def new_command(ctx, flag):
        """Description of the new command."""
        logger.info("New command executed")
        click.echo("New command output")
    
    cli.add_command(new_command)
```

### Step 2: Register Command

Add to `vibe_tools/commands/__init__.py`:

```python
from vibe_tools.commands import new_command

# In register_all_commands():
new_command.register_new_command(cli)
```

### Step 3: Test Command

```bash
vibe new-command --help
vibe new-command --flag
```

## Adding New Prompts

### Step 1: Create Prompt File

Create `prompts/new_prompt.txt`:

```
This is a prompt template.
Use {variable} for substitutions.
```

### Step 2: Use Prompt

```python
from vibe_tools.utils import get_prompt

prompt_template = get_prompt("new_prompt.txt")
prompt = prompt_template.format(variable="value")
```

## Adding New Services

### Step 1: Define Service

Add to `vibe_tools/servers.py` DEFAULT_SERVER_CONFIGS:

```python
"newservice": {
    "image": "service/image:tag",
    "container_name": "vibe-newservice",
    "ports": {"8080/tcp": 8080},
    "env": {
        "KEY": "value"
    },
    "description": "Description of service"
}
```

### Step 2: Add Setup Command

Add to `vibe_tools/setup.py` SERVICE_DEFINITIONS:

```python
"newservice": {
    "display": "New Service",
    "default_port": 8080,
    "docker_keywords": ["newservice"],
    "fields": [
        {"name": "host", "prompt": "Host", "default": "localhost"},
        {"name": "port", "prompt": "Port", "type": int, "default": 8080}
    ]
}
```

### Step 3: Test

```bash
vibe-servers install newservice
vibe-setup newservice
```

## Testing

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_utils.py

# With coverage
pytest --cov=vibe_tools

# Verbose output
pytest -v
```

### Test Structure

Tests are in `tests/` directory:
- `test_cli.py`: CLI command tests
- `test_utils.py`: Utility function tests
- `test_normalize.py`: Normalization tests
- `test_servers.py`: Server management tests
- etc.

### Writing Tests

```python
import pytest
from vibe_tools.utils import load_config

def test_example():
    config = load_config()
    assert "services" in config
```

## Code Style

### Linting

Uses `ruff` for linting:

```bash
# Check
ruff check vibe_tools/

# Fix
ruff check --fix vibe_tools/
```

### Type Checking

Uses `mypy` for type checking:

```bash
mypy vibe_tools/
```

### Configuration

Linting and type checking configured in `pyproject.toml`:
- Line length: 120
- Target Python: 3.9+
- Strict type checking disabled (pragmatic approach)

## Extension Points

### Custom Agent Types

Add new agent types in `vibe_tools/utils.py`:

```python
def get_agent_command(agent: str, prompt: str) -> List[str]:
    if agent == "new-agent":
        return ["new-agent", "command", prompt]
    # ... existing agents
```

### Custom Reconciliation

Create custom reconciliation loop:

```python
from vibe_tools.ralph import RalphLoop

loop = RalphLoop(
    name="Custom Step",
    desired_file=pathlib.Path("desired.yaml"),
    current_file=pathlib.Path("current.yaml"),
    agent="cursor-agent"
)
loop.run()
```

### Custom Templates

Add templates in `vibe_tools/templates.py`:

```python
TEMPLATES = {
    "new_template": """Template content here"""
}
```

## Development Workflow

### Setup Development Environment

```bash
# Clone repository
git clone <repo-url>
cd vibe-tools

# Install in development mode
pip install -e .

# Install development dependencies
pip install pytest pytest-cov ruff mypy
```

### Making Changes

1. **Create feature branch**:
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Make changes**: Edit code, add tests

3. **Run tests**:
   ```bash
   pytest
   ruff check .
   mypy vibe_tools/
   ```

4. **Test manually**:
   ```bash
   vibe <your-command>
   ```

5. **Commit changes**:
   ```bash
   git commit -m "Add new feature"
   ```

### Testing Commands

Test new commands in a test project:

```bash
# Create test project
mkdir test-project
cd test-project

# Initialize vibe-tools
vibe init

# Test your command
vibe your-command
```

## Project State Management

### State File Structure

`implementation/state.json` tracks project state:

```json
{
  "phases": {
    "normalize": {"status": "completed"},
    "implement": {"status": "in_progress"}
  },
  "plans": {
    "plan_1": {
      "prd_id": "prd_01_feature",
      "branch": "vibe/plan_1",
      "status": "in_progress"
    }
  }
}
```

### Working with State

```python
from vibe_tools.utils import load_project_state, save_project_state

state = load_project_state()
state["phases"]["new_phase"] = {"status": "pending"}
save_project_state(state)
```

## Logging

### Log Structure

Logs are written to `implementation/logs/<command>.log`:
- Rotating file handler
- DEBUG level to file
- INFO/WARNING to console (configurable)

### Using Logger

```python
from vibe_tools.utils import logger

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

## Configuration Management

### Reading Configuration

```python
from vibe_tools.utils import load_config

config = load_config()
value = config.get("key", "default")
```

### Writing Configuration

```python
from vibe_tools.utils import save_config

config["key"] = "value"
save_config(config)
```

## Git Operations

### Utility Functions

```python
from vibe_tools.utils import (
    run_command,
    is_dirty,
    switch_to_main
)

# Run git command
run_command(["git", "status"])

# Check if working directory is dirty
if is_dirty():
    # Handle dirty state

# Switch to main branch
switch_to_main()
```

## Best Practices

### Code Organization

1. **One command per module**: Keep commands separate
2. **Use utilities**: Leverage existing utility functions
3. **Follow patterns**: Match existing code style
4. **Document functions**: Add docstrings

### Error Handling

1. **Use Click exceptions**: `click.ClickException` for user errors
2. **Log errors**: Use logger for debugging
3. **Provide feedback**: Clear error messages
4. **Handle gracefully**: Don't crash on expected errors

### Testing

1. **Test new features**: Add tests for new code
2. **Test edge cases**: Handle error conditions
3. **Mock external calls**: Don't require real services
4. **Keep tests fast**: Avoid slow operations

### Documentation

1. **Update docs**: Document new features
2. **Add examples**: Show usage patterns
3. **Update README**: Keep overview current
4. **Document breaking changes**: Note incompatibilities

## Common Patterns

### Command with Options

```python
@cli.command()
@click.option("--flag", is_flag=True)
@click.argument("arg")
@click.pass_context
def command(ctx, flag, arg):
    config = load_config()
    # Command logic
```

### Agent Execution

```python
from vibe_tools.utils import get_agent_command, run_agent

cmd = get_agent_command("cursor-agent", prompt)
output, code = run_agent(cmd, stream=False)
```

### Cost Logging

```python
from vibe_tools.cost import CostLogger, AGENT_DEFAULT_MODEL

cost_logger = CostLogger(config)
cost_logger.log_run(
    agent="cursor-agent",
    model=AGENT_DEFAULT_MODEL["cursor-agent"],
    prompt=prompt,
    output=output,
    prd_name="prd_01",
    iteration=1,
    phase="implement",
    purpose="implementation"
)
```

## Troubleshooting Development

### Import Errors

```bash
# Reinstall in development mode
pip install -e .
```

### Test Failures

```bash
# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_specific.py::test_function

# Debug with pdb
pytest --pdb
```

### Linting Issues

```bash
# Auto-fix what can be fixed
ruff check --fix .

# Check specific file
ruff check vibe_tools/your_file.py
```

See [Troubleshooting](12-troubleshooting.md) for more help.
