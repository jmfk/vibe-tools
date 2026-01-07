import pathlib
import re
import sys
from typing import Any, Dict, List

import click
import yaml

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.utils import (
    PRD_DIR,
    VIBE_PROJECT_DIR,
    get_agent_command,
    get_prompt,
    is_dirty,
    load_project_state,
    logger,
    run_agent,
    run_command,
    save_project_state,
)
from vibe_tools.ralph import _switch_to_branch

DEFAULT_SPECS_DIR = pathlib.Path("specs")


def normalize_prd(
    agent, input_file=None, auto_overwrite=False, caffeinate=False, stream=False
):
    # ... existing code ...
    from vibe_tools.cli import load_config

    config = load_config()
    cost_logger = CostLogger(config)

    try:
        prompt_base = get_prompt("pdr_normalization_prompt.txt")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    specs_dir = DEFAULT_SPECS_DIR
    # Ensure specs directory exists
    if not specs_dir.exists():
        # Check for alternative 'spec'
        alt_specs = pathlib.Path("spec")
        if alt_specs.exists():
            specs_dir = alt_specs
        else:
            print(f"Creating directory: {specs_dir}")
            specs_dir.mkdir(exist_ok=True)

    # Ensure prds directory exists
    PRD_DIR.mkdir(exist_ok=True)

    # Get files to process
    files_to_process = []
    if input_file:
        path = pathlib.Path(input_file)
        if not path.exists():
            print(f"Error: File {input_file} not found.")
            sys.exit(1)
        files_to_process = [path]
    else:
        # Find all markdown files in specs and subdirectories
        files_to_process = list(specs_dir.rglob("*.md"))
        if not files_to_process:
            print(f"❌ No markdown specs found in {specs_dir}/.")
            print("   Run 'vibe pm' or 'vibe architect' to create them first.")
            return

    # Check for existing normalized files
    existing_prds = list(PRD_DIR.rglob("prd_*.yaml"))

    overwrite_all = auto_overwrite
    if existing_prds and not auto_overwrite:
        if click.confirm(
            f"Found {len(existing_prds)} existing files in {PRD_DIR}/. Overwrite all?",
            default=False,
        ):
            overwrite_all = True

    for spec_path in files_to_process:
        stem = spec_path.stem

        # Clean the stem by stripping ANY leading 'prd' markers (repeatedly if needed)
        # and replacing dashes/spaces with underscores.
        clean_stem = stem.lower()
        while True:
            new_stem = re.sub(r"^prd[-_ ]?", "", clean_stem)
            if new_stem == clean_stem:
                break
            clean_stem = new_stem

        # Replace remaining dashes/spaces with underscores for consistency
        clean_stem = re.sub(r"[- ]", "_", clean_stem)

        # Switch to normalization branch for this PRD
        if config.get("ralph", {}).get("auto_merge", False):
            from vibe_tools.utils import get_automerge_branch

            branch_name = get_automerge_branch(config)
        else:
            branch_name = f"vibe/normalize/{clean_stem}"

        _switch_to_branch(branch_name, agent, clean_stem, stream=stream)

        # Determine target PRD directory (preserving subdirectories)
        rel_dir = spec_path.parent.relative_to(specs_dir)
        target_prd_dir = PRD_DIR / rel_dir
        target_prd_dir.mkdir(parents=True, exist_ok=True)

        # Determine output filename with normalized prefix and format
        # 1. Special case for shared global context files ("global truths")
        global_truths = [
            "architecture",
            "project_overview",
            "infrastructure",
            "cicd",
            "testing",
        ]
        if clean_stem in global_truths:
            output_filename = f"{clean_stem}.yaml"
            # Global truths now go to the PRD directory (prds/)
            output_path = PRD_DIR / output_filename
        else:
            # 2. Handle PRD prefixes and format
            # Ensure it starts with prd_
            output_filename = f"prd_{clean_stem}.yaml"
            output_path = target_prd_dir / output_filename

        # Optimization: Skip if YAML is newer than the source MD
        if output_path.exists():
            md_mtime = spec_path.stat().st_mtime
            yaml_mtime = output_path.stat().st_mtime
            if yaml_mtime > md_mtime and not overwrite_all:
                print(
                    f"⏩ Skipping {spec_path.name} (already up-to-date at {output_path.name})"
                )
                continue

        if output_path.exists() and not overwrite_all:
            if not click.confirm(
                f"Overwrite existing {output_path.name}?", default=False
            ):
                continue

        print(
            f"🔄 Normalizing: {spec_path.name} -> {output_path.name} using {agent}..."
        )

        human_prd = spec_path.read_text()
        prompt = prompt_base.replace("{PASTE HUMAN PRD HERE}", human_prd)

        cmd = get_agent_command(agent, prompt)
        output, code = run_agent(cmd, caffeinate=caffeinate, stream=stream)

        cost_logger.log_run(
            agent=agent,
            model=AGENT_DEFAULT_MODEL.get(agent, "unknown"),
            prompt=prompt,
            output=output,
            prd_name=stem,
            iteration=1,
            phase="normalize",
            purpose="normalizing_prd",
        )

        if code == 0:
            # Strip markdown code fences if present
            clean_output = output.strip()
            if clean_output.startswith("```"):
                # Remove first line
                lines = clean_output.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                # Remove last line if it's a closing fence
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_output = "\n".join(lines).strip()

            output_path.write_text(clean_output)
            print(f"✅ Saved: {output_path}")

            # Commit changes if dirty
            if is_dirty():
                logger.info(
                    f"💾 Committing normalization for {spec_path.name} on {branch_name}..."
                )
                run_command(["git", "add", "."], check=False)
                run_command(
                    ["git", "commit", "-m", f"vibe: normalize PRD '{spec_path.name}'"],
                    check=False,
                )

            # Update project state if this was a full normalization run
            if not input_file:
                from vibe_tools.utils import (
                    load_project_state,
                    save_project_state,
                    switch_to_main,
                )

                state = load_project_state()
                state["phases"]["normalize"]["status"] = "completed"
                save_project_state(state)

            # Switch back to main after each file normalization
            switch_to_main()
        else:
            print(f"❌ Failed to normalize {spec_path.name}")
            # Ensure we are back on main if it failed
            switch_to_main()
