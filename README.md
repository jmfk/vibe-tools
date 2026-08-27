# vibe-tools

Local CLI utilities for working inside repo directories.

## Install Modes

```bash
make install-app
```

Installs a packaged global app via `pipx` from a built wheel. After install, the repo itself is no longer needed by the installed command.

```bash
make install-dev-global
```

Installs a global editable dev version via `pipx`. The installed `vibe` command points at this repo, so local changes are reflected without reinstalling.

```bash
make build-dist
```

Builds distribution artifacts in `dist/`:
- wheel for installation
- sdist for distribution/publishing later

## Direct Commands

```bash
vibe
vibe status
vibe config api
vibe config postgres
vibe servers list
vibe project add .
```

## Notes

- `install-app` is for a packaged global install.
- `install-dev-global` is for editable development.
- `build-dist` does not publish; it only builds artifacts locally.
- `pyproject.toml` defines the installed scripts: `vibe` and `vibe-setup`.

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
