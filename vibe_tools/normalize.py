import pathlib
import re
import sys
from typing import Any, Dict, List

import click
import yaml

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.utils import (
    BACKLOG_DIR,
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
    switch_to_main,
)
from vibe_tools.ralph import _switch_to_branch

DEFAULT_SPECS_DIR = pathlib.Path("specs")


def normalize_prd(
    agent,
    input_file=None,
    auto_overwrite=False,
    caffeinate=False,
    stream=False,
    debug=False,
):
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
    # Only prompt for global overwrite when normalizing all files (not specific files)
    overwrite_mode = "yes" if auto_overwrite else "ask"
    if not input_file:  # Only when normalizing all files
        existing_prds = list(BACKLOG_DIR.rglob("prd_*.yaml"))
        if existing_prds and not auto_overwrite:
            choice = click.prompt(
                f"Found {len(existing_prds)} existing files in {BACKLOG_DIR}/. Overwrite? [y]es, [n]o, [a]sk per file",
                type=click.Choice(["y", "n", "a"], case_sensitive=False),
                default="a",
            )
            if choice.lower() == "y":
                overwrite_mode = "yes"
            elif choice.lower() == "n":
                overwrite_mode = "no"
            else:
                overwrite_mode = "ask"

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
        
        # Determine output filename and path
        global_truths = [
            "architecture",
            "project_overview",
            "infrastructure",
            "cicd",
            "testing",
            "build",
        ]
        
        if clean_stem in global_truths:
            output_filename = f"{clean_stem}.yaml"
            if clean_stem == "build":
                output_path = VIBE_PROJECT_DIR / output_filename
            else:
                # Global truths stay in PRD_DIR (product/prds/)
                output_path = PRD_DIR / output_filename
        else:
            # PRDs go to BACKLOG_DIR (product/prds/backlog/)
            target_prd_dir = BACKLOG_DIR / rel_dir
            target_prd_dir.mkdir(parents=True, exist_ok=True)
            output_filename = f"prd_{clean_stem}.yaml"
            output_path = target_prd_dir / output_filename

        # Optimization: Skip if YAML is newer than the source MD
        if output_path.exists():
            if overwrite_mode == "no":
                print(f"⏩ Skipping {spec_path.name} (overwrite mode: no)")
                continue

            if overwrite_mode != "yes":
                md_mtime = spec_path.stat().st_mtime
                yaml_mtime = output_path.stat().st_mtime
                if yaml_mtime > md_mtime:
                    print(
                        f"⏩ Skipping {spec_path.name} (already up-to-date at {output_path.name})"
                    )
                    continue

        if output_path.exists() and overwrite_mode == "ask":
            if not click.confirm(
                f"Overwrite existing {output_path.name}?", default=False
            ):
                continue

        print(
            f"🔄 Normalizing: {spec_path.name} -> {output_path.name} using {agent}..."
        )

        human_prd = spec_path.read_text()
        prompt = prompt_base.replace("{PASTE HUMAN PRD HERE}", human_prd)

        if debug:
            print("\n--- DEBUG: NORMALIZATION PROMPT ---")
            print(prompt)
            print("--- END DEBUG ---\n")

        cmd = get_agent_command(agent, prompt)
        output, code = run_agent(cmd, caffeinate=caffeinate, stream=stream)

        if debug:
            print("\n--- DEBUG: AGENT OUTPUT ---")
            print(output)
            print("--- END DEBUG ---\n")

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
            if not output.strip():
                logger.error(f"❌ Agent returned empty output for {spec_path.name}")
                print(
                    f"❌ Failed to normalize {spec_path.name}: Empty output from agent"
                )
                switch_to_main()
                continue

            # Strip markdown code fences if present
            clean_output = output.strip()

            # Robust extraction: find the first yaml or ``` block
            yaml_match = re.search(r"```(?:yaml)?\n([\s\S]*?)\n```", clean_output)
            if yaml_match:
                clean_output = yaml_match.group(1).strip()
            elif clean_output.startswith("```"):
                # Fallback for simple fence if regex didn't catch it
                lines = clean_output.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_output = "\n".join(lines).strip()

            try:
                # Validate and re-dump to ensure valid YAML formatting and proper quoting
                data = yaml.safe_load(clean_output)
                if data is None or not isinstance(data, dict):
                    # If it's not a dict, it might have failed to extract correctly
                    raise yaml.YAMLError("Output is not a valid YAML dictionary")

                clean_output = yaml.safe_dump(
                    data, sort_keys=False, allow_unicode=True, width=1000
                )
            except yaml.YAMLError as e:
                logger.warning(f"⚠️ Invalid YAML generated for {spec_path.name}: {e}")
                print(f"🔄 Attempting to fix YAML for {spec_path.name} using Gemini...")

                fix_prompt = f"""The following YAML is invalid:
---
{clean_output}
---
Error: {e}

Please fix the YAML formatting issues and return ONLY the valid YAML content.
Ensure all string values with special characters are properly quoted.
"""
                if debug:
                    print("\n--- DEBUG: YAML FIX PROMPT ---")
                    print(fix_prompt)
                    print("--- END DEBUG ---\n")

                try:
                    from vibe_tools.utils import run_llm

                    fixed_output = run_llm(
                        fix_prompt, model="gemini-3-flash", debug=debug
                    )

                    if not fixed_output:
                        if debug:
                            print("DEBUG: Fixed output from LLM is empty.")
                        raise ValueError("Fixed output from LLM is empty.")

                    if debug:
                        print("\n--- DEBUG: FIXED OUTPUT (RAW) ---")
                        print(fixed_output)
                        print("--- END DEBUG ---\n")

                    # Strip markdown code fences if present in fixed output
                    fixed_output = fixed_output.strip()

                    # Robust extraction: find the first yaml or ``` block
                    yaml_match_fixed = re.search(
                        r"```(?:yaml)?\n([\s\S]*?)\n```", fixed_output
                    )
                    if yaml_match_fixed:
                        fixed_output = yaml_match_fixed.group(1).strip()
                    elif fixed_output.startswith("```"):
                        lines = fixed_output.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        fixed_output = "\n".join(lines).strip()

                    # Try to validate again
                    data = yaml.safe_load(fixed_output)
                    if data is None:
                        if debug:
                            print("DEBUG: Fixed output parsed as None")
                        data = {}

                    if debug:
                        print("\n--- DEBUG: PARSED YAML DATA ---")
                        print(data)
                        print("--- END DEBUG ---\n")

                    clean_output = yaml.safe_dump(
                        data, sort_keys=False, allow_unicode=True, width=1000
                    )
                    print(f"✅ Successfully fixed YAML for {spec_path.name}")
                except Exception as fix_err:
                    logger.error(f"❌ Failed to fix YAML: {fix_err}")
                    print(
                        f"⚠️ Warning: Generated YAML for {spec_path.name} is still invalid. Saving as-is for manual fix."
                    )

            output_path.write_text(clean_output)
            logger.info(f"✅ Saved normalized PRD to: {output_path}")
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
                state = load_project_state()
                state["phases"]["normalize"]["status"] = "completed"
                save_project_state(state)

            # Switch back to main after each file normalization
            switch_to_main()
        else:
            logger.error(
                f"❌ Failed to normalize {spec_path.name}. Agent exit code: {code}"
            )
            logger.error(f"Agent output:\n{output}")
            print(f"❌ Failed to normalize {spec_path.name}")
            # Ensure we are back on main if it failed
            switch_to_main()
