import datetime
import pathlib
import re
import sys

import click
import yaml

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.ralph import _switch_to_branch
from vibe_tools.utils import (
    PLANNING_BACKLOG_DIR,
    PLANNING_HISTORY_DIR,
    PLANNING_INBOX_DIR,
    PLANNING_REJECTED_DIR,
    PRD_DIR,
    PRD_DONE_DIR,
    PRD_FAILED_DIR,
    PRD_PROCESSING_DIR,
    VIBE_PROJECT_DIR,
    get_agent_command,
    get_file_hash,
    get_main_branch,
    get_prompt,
    is_dirty,
    load_project_state,
    logger,
    run_agent,
    run_command,
    save_project_state,
    switch_to_main,
    safe_yaml_load,
    safe_yaml_dump,
    parse_prd_filename,
    update_md_implementation_status,
)

DEFAULT_SPECS_DIR = pathlib.Path("product")


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
        prompt_base = get_prompt("prd_normalization_prompt.txt")
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

    # Get files to process and pre-read their content and stats to avoid FileNotFoundError after branch switching
    # and to preserve mtime for skip logic.
    files_to_process = []
    if input_file:
        path = pathlib.Path(input_file)
        if not path.exists():
            print(f"Error: File {input_file} not found.")
            sys.exit(1)
        files_to_process = [(path, path.read_text(), path.stat().st_mtime)]
    else:
        # Collect from product root first (system files)
        if specs_dir.exists():
            for path in specs_dir.glob("*.md"):
                try:
                    files_to_process.append((path, path.read_text(), path.stat().st_mtime))
                except Exception as e:
                    print(f"⚠️  Warning: Could not read {path}: {e}")

        # Then collect from backlog
        if PLANNING_BACKLOG_DIR.exists():
            for path in PLANNING_BACKLOG_DIR.rglob("*.md"):
                try:
                    # Avoid duplicates if root and backlog overlap
                    if any(p[0] == path for p in files_to_process):
                        continue
                    files_to_process.append((path, path.read_text(), path.stat().st_mtime))
                except Exception as e:
                    print(f"⚠️  Warning: Could not read {path}: {e}")

        if not files_to_process:
            print(f"❌ No markdown specs found in {specs_dir}/ or {PLANNING_BACKLOG_DIR}/.")
            return

    # Check for existing normalized files
    # Only prompt for global overwrite when normalizing all files (not specific files)
    overwrite_mode = "yes" if auto_overwrite else "ask"
    if not input_file:  # Only when normalizing all files
        existing_prds = list(PRD_PROCESSING_DIR.rglob("prd_*.yaml")) + list(PRD_PROCESSING_DIR.rglob("v*-*_*.yaml"))
        if existing_prds and not auto_overwrite and sys.stdin.isatty():
            choice = click.prompt(
                f"Found {len(existing_prds)} existing files in {PRD_PROCESSING_DIR}/. Overwrite? [y]es, [n]o, [a]sk per file",
                type=click.Choice(["y", "n", "a"], case_sensitive=False),
                default="a",
            )
            if choice.lower() == "y":
                overwrite_mode = "yes"
            elif choice.lower() == "n":
                overwrite_mode = "no"
            else:
                overwrite_mode = "ask"

    for spec_path, pre_read_content, pre_read_mtime in files_to_process:
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

        # Ensure the MD file exists on the branch (it might have been deleted by switch_to_main/checkout)
        if not spec_path.exists():
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            spec_path.write_text(pre_read_content)

        # Determine target PRD directory based on which product subdirectory it came from
        if PLANNING_BACKLOG_DIR in spec_path.parents or spec_path.parent == PLANNING_BACKLOG_DIR:
            target_base = PRD_PROCESSING_DIR
            rel_dir = spec_path.parent.relative_to(PLANNING_BACKLOG_DIR)
        elif PLANNING_HISTORY_DIR in spec_path.parents or spec_path.parent == PLANNING_HISTORY_DIR:
            target_base = PRD_DONE_DIR
            rel_dir = spec_path.parent.relative_to(PLANNING_HISTORY_DIR)
        elif PLANNING_INBOX_DIR in spec_path.parents or spec_path.parent == PLANNING_INBOX_DIR:
            target_base = PRD_PROCESSING_DIR  # Normalized inbox PRDs go to processing
            rel_dir = spec_path.parent.relative_to(PLANNING_INBOX_DIR)
        elif PLANNING_REJECTED_DIR in spec_path.parents or spec_path.parent == PLANNING_REJECTED_DIR:
            print(f"⏩ Skipping {spec_path.name} (rejected PRDs are not normalized)")
            continue
        else:
            # Default to processing if it's in the product root or elsewhere
            target_base = PRD_PROCESSING_DIR
            try:
                rel_dir = spec_path.parent.relative_to(PLANNING_BACKLOG_DIR)
            except ValueError:
                rel_dir = spec_path.parent.relative_to(specs_dir)

        # Determine output filename and path
        global_truths = [
            "architecture",
            "project_overview",
            "infrastructure",
            "cicd",
            "testing",
            "build",
            "dev_environment",
        ]

        if clean_stem in global_truths:
            output_filename = f"{clean_stem}.yaml"
            # Global truths go to VIBE_PROJECT_DIR (implementation/)
            output_path = VIBE_PROJECT_DIR / output_filename
        else:
            # PRDs go to the calculated target base (implementation/prds/category/)
            target_prd_dir = target_base / rel_dir
            target_prd_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if MD already has an implementation ID
            md_content = pre_read_content
            implementation_id = None
            if md_content.startswith("---"):
                parts = md_content.split("---", 2)
                if len(parts) >= 3:
                    fm = safe_yaml_load(parts[1]) or {}
                    implementation_id = fm.get("implementation", {}).get("id")

            # Search for existing YAML file with this clean_stem (legacy or versioned)
            existing_yaml = None
            search_dirs = [PRD_PROCESSING_DIR, PRD_DONE_DIR, PRD_FAILED_DIR]
            for sd in search_dirs:
                if not sd.exists(): continue
                # Legacy check
                leg = sd / f"prd_{clean_stem}.yaml"
                if leg.exists():
                    existing_yaml = leg
                    break
                # Versioned check
                ver_files = list(sd.glob(f"v*-*_{clean_stem}.yaml"))
                if ver_files:
                    existing_yaml = ver_files[0]
                    break

            if existing_yaml:
                output_path = existing_yaml
                output_filename = existing_yaml.name
            elif implementation_id:
                # Use ID from frontmatter if YAML missing
                output_filename = f"{implementation_id}_{clean_stem}.yaml"
                output_path = target_prd_dir / output_filename
            else:
                # Truly new PRD
                output_filename = f"PENDING_{clean_stem}.yaml"
                output_path = target_prd_dir / output_filename

        # Hashing and Change Detection
        md_hash = get_file_hash(spec_path)
        if output_path.exists():
            try:
                existing_data = safe_yaml_load(output_path.read_text())
                if existing_data and isinstance(existing_data, dict):
                    old_hash = existing_data.get("METADATA", {}).get("SOURCE_HASH")
                    if old_hash and old_hash != md_hash:
                        if not auto_overwrite and sys.stdin.isatty():
                            if not click.confirm(f"⚠️  {spec_path.name} has changed. Update {output_path.name}?", default=True):
                                continue
            except Exception as e:
                logger.warning(f"Could not read existing hash from {output_path}: {e}")

        # Optimization: Skip if YAML is newer than the source MD
        if output_path.exists() and not output_filename.startswith("PENDING_"):
            if overwrite_mode == "no":
                print(f"⏩ Skipping {spec_path.name} (overwrite mode: no)")
                continue

            if overwrite_mode != "yes":
                md_mtime = pre_read_mtime
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

        human_prd = pre_read_content
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

            data = None
            try:
                # Validate and re-dump to ensure valid YAML formatting and proper quoting
                data = safe_yaml_load(clean_output)
                if data is None or not isinstance(data, dict):
                    # If it's not a dict, it might have failed to extract correctly
                    raise yaml.YAMLError("Output is not a valid YAML dictionary")
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
                    data = safe_yaml_load(fixed_output)
                    if data is None:
                        if debug:
                            print("DEBUG: Fixed output parsed as None")
                        data = {}

                    if debug:
                        print("\n--- DEBUG: PARSED YAML DATA ---")
                        print(data)
                        print("--- END DEBUG ---\n")

                    print(f"✅ Successfully fixed YAML for {spec_path.name}")
                except Exception as fix_err:
                    logger.error(f"❌ Failed to fix YAML: {fix_err}")
                    print(
                        f"⚠️ Warning: Generated YAML for {spec_path.name} is still invalid. Saving as-is for manual fix."
                    )
                    # We'll try to save whatever we have
                    data = safe_yaml_load(clean_output) or {}

            # Inject metadata and perform scheduling
            if data is not None and isinstance(data, dict):
                # Inject metadata
                if "METADATA" not in data:
                    data["METADATA"] = {}
                data["METADATA"]["SOURCE_HASH"] = md_hash
                data["METADATA"]["NORMALIZED_AT"] = datetime.datetime.now().isoformat()

                # Inject plan metadata if it's a PRD
                if clean_stem not in global_truths:
                    data["TITLE"] = data.get("TITLE", clean_stem.replace("_", " ").title())
                    data["DEPENDS_ON"] = data.get("DEPENDS_ON", [])
                    data["BRANCH"] = data.get("BRANCH", f"feature/{clean_stem}")
                    data["PARENT_BRANCH"] = data.get("PARENT_BRANCH", get_main_branch())

                    # SCHEDULING LOGIC
                    if output_filename.startswith("PENDING_"):
                        state = load_project_state()
                        version = state.get("current_version", "01")
                        
                        # Calculate sequence based on dependencies
                        dependencies = data.get("DEPENDS_ON", [])
                        max_dep_seq = 0
                        
                        # Look up dependency sequences in existing plans
                        plans = state.get("plans", {})
                        for dep_id in dependencies:
                            # dep_id could be 'prd_name' or 'vXX-XXX_name' or just 'name'
                            dep_info = plans.get(dep_id)
                            if not dep_info:
                                # Try with prd_ prefix
                                dep_info = plans.get(f"prd_{dep_id}")
                            
                            if dep_info:
                                dep_filename = pathlib.Path(dep_info["file"]).name
                                parsed = parse_prd_filename(dep_filename)
                                if parsed["sequence"]:
                                    max_dep_seq = max(max_dep_seq, parsed["sequence"])
                        
                        # New sequence is either max(deps) + 10 or next_sequence
                        next_seq = max(max_dep_seq + 10, state.get("next_sequence", 10))
                        
                        # Update state
                        state["next_sequence"] = next_seq + 10
                        save_project_state(state)
                        
                        # Set final filename
                        output_filename = f"v{version}-{next_seq:03d}_{clean_stem}.yaml"
                        output_path = target_prd_dir / output_filename
                        
                        # Update MD frontmatter
                        update_md_implementation_status(
                            spec_path, 
                            version, 
                            next_seq, 
                            output_path
                        )

                clean_output = safe_yaml_dump(data)

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
