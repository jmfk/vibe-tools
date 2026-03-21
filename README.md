# vibe-tools

Local CLI utilities for working inside repo directories.

## Install

```bash
pip install -e .
```

## Commands

```bash
vibe
vibe status
vibe config api
vibe config postgres
vibe servers list
vibe project add .
```

## Repo-Local State

The CLI stores repo-local state in `.vibe-tools/`:

```text
.vibe-tools/
  config.json
  logs/
  costs/
  instructions/
  run-pids.json
```

Shared global metadata is stored in `~/.vibe-tools/`.
