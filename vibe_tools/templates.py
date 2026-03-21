TEMPLATES = {
    "README": """# vibe-tools

CLI utilities for local repo workflows.

## What It Does

- Stores repo-local runtime data under `.vibe-tools/`
- Manages local service configuration with `vibe config ...`
- Manages optional Docker-backed dev services with `vibe servers ...`
- Tracks registered repos with `vibe project ...`
- Shows local runtime status with `vibe status`

## Install

```bash
pip install -e .
```

## Core Commands

```bash
vibe
vibe status
vibe config api
vibe config postgres
vibe servers list
vibe project add .
```

## Repo Runtime Layout

```text
.vibe-tools/
  config.json
  logs/
  costs/
  instructions/
  run-pids.json
```

## Notes

- Project-local state lives in `.vibe-tools/`
- Global shared settings live in `~/.vibe-tools/`
- API keys are stored in the repo `.env`
""",
    "example_prompt.txt": """Return output only.""",
}
