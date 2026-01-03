# vibe-tools

Global commands for Cursor Ralph loop and coverage improvement.

## Installation

```bash
pip install -e .
```

## Usage

### CLI

The `vibe` command is the main entry point:

```bash
vibe --help
```

### Loop Scripts

- `run_cursor_ralph_loop.py`: Run the Ralph loop for automated coding.
- `run_coverage_improvement_loop.py`: Run the loop to improve test coverage.
- `run_test_fix_loop.py`: Run the loop to fix failing tests.

## Development

Monitor the status of loops using `monitor.py`:

```bash
python monitor.py
```

