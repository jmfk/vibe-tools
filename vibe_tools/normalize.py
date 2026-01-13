import datetime
import pathlib
import re
import sys

import click
import yaml

from vibe_tools.cost import CostLogger
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
    SYSTEM_FILES,
    get_file_hash,
    get_main_branch,
    get_prompt,
    is_dirty,
    load_project_state,
    logger,
    run_command,
    save_project_state,
    switch_to_main,
    safe_yaml_load,
    safe_yaml_dump,
    parse_prd_filename,
    update_md_implementation_status,
    out_debug,
    out_error,
    out_info,
    out_print,
    out_success,
    out_warn,
)

DEFAULT_SPECS_DIR = pathlib.Path("product")


def _run_normalization_llm(
    prompt,
    cost_logger,
    stem,
    phase="normalize",
    debug=False,
):
    """Internal helper to run LLM and handle YAML extraction/fixing."""
    from vibe_tools.utils import run_llm

    # Normalization always uses direct LLM call
    output = run_llm(prompt, model="gemini-3-flash", debug=debug)
    code = 0 if output else -1

    if debug:
        out_debug("\n--- DEBUG: LLM OUTPUT ---")
        out_debug(output)
        out_debug("--- END DEBUG ---\n")

    if output:
        # Use 'gemini' as the internal agent name for logging direct LLM calls
        cost_logger.log_run(
            agent="gemini",
            model="gemini-2.0-flash-exp",
            prompt=prompt,
            output=output,
            prd_name=stem,
            iteration=1,
            phase=phase,
            purpose="normalizing_prd",
        )

    if code != 0:
        return None, code

    if not output or not output.strip():
        return None, -1

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
        data = safe_yaml_load(clean_output)
        if data is None or not isinstance(data, dict):
            raise yaml.YAMLError("Output is not a valid YAML dictionary")
    except yaml.YAMLError as e:
        logger.warning(f"⚠️ Invalid YAML generated: {e}")
        out_info(f"🔄 Attempting to fix YAML using Gemini...")

        fix_prompt = f"""The following YAML is invalid:
---
{clean_output}
---
Error: {e}

Please fix the YAML formatting issues and return ONLY the valid YAML content.
Ensure all string values with special characters are properly quoted.
"""
        try:
            fixed_output = run_llm(fix_prompt, model="gemini-3-flash", debug=debug)
            if not fixed_output:
                raise ValueError("Fixed output from LLM is empty.")

            fixed_output = fixed_output.strip()
            yaml_match_fixed = re.search(r"```(?:yaml)?\n([\s\S]*?)\n```", fixed_output)
            if yaml_match_fixed:
                fixed_output = yaml_match_fixed.group(1).strip()
            elif fixed_output.startswith("```"):
                lines = fixed_output.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                fixed_output = "\n".join(lines).strip()

            data = safe_yaml_load(fixed_output)
            if data is None:
                data = {}
            out_success(f"✅ Successfully fixed YAML")
        except Exception as fix_err:
            logger.error(f"❌ Failed to fix YAML: {fix_err}")
            data = safe_yaml_load(clean_output) or {}

    return data, 0


def normalize_system_file(
    input_file,
    auto_overwrite=False,
    debug=False,
    force=False,
):
    """Normalize core project system files (architecture, infrastructure, etc.)."""
    from vibe_tools.cli import load_config

    config = load_config()
    cost_logger = CostLogger(config)

    try:
        prompt_base = get_prompt("prd_normalization_prompt.txt")
    except FileNotFoundError as e:
        out_error(f"Error: {e}")
        sys.exit(1)

    path = pathlib.Path(input_file)
    if not path.exists():
        return auto_overwrite

    stem = path.stem
    clean_stem = re.sub(r"[- ]", "_", stem.lower())
    output_filename = f"{clean_stem}.yaml"
    output_path = VIBE_PROJECT_DIR / output_filename

    md_content = path.read_text()
    md_hash = get_file_hash(path)

    # Check if needs update
    if output_path.exists() and not force:
        try:
            existing_data = safe_yaml_load(output_path.read_text())
            if existing_data and isinstance(existing_data, dict):
                old_hash = existing_data.get("METADATA", {}).get("SOURCE_HASH")
                if old_hash == md_hash:
                    if auto_overwrite == "ask":
                        if not click.confirm(
                            f"⚠️  {path.name} is up-to-date. Reprocess anyway?",
                            default=False,
                        ):
                            return auto_overwrite
                    else:
                        out_info(f"⏩ Skipping {path.name} (already up-to-date)")
                        return auto_overwrite

                if auto_overwrite is True or auto_overwrite == "yes":
                    pass  # Continue to normalization
                elif auto_overwrite == "no":
                    return auto_overwrite
                elif sys.stdin.isatty():
                    choice = click.prompt(
                        f"⚠️  {path.name} has changed. Update {output_path.name}? [y]es, [n]o, [A]ll, [N]one",
                        type=click.Choice(["y", "n", "a", "N"], case_sensitive=False),
                        default="y",
                    )
                    if choice.lower() == "a":
                        auto_overwrite = True
                    elif choice.lower() == "n":
                        return auto_overwrite
                    elif choice.lower() == "N":
                        return "no"
        except Exception as e:
            logger.warning(f"Could not read existing hash from {output_path}: {e}")

    out_info(
        f"🔄 Normalizing system file: {path.name} -> {output_path.name} using Gemini..."
    )
    prompt = prompt_base.replace("{PASTE HUMAN PRD HERE}", md_content)

    data, code = _run_normalization_llm(
        prompt=prompt,
        cost_logger=cost_logger,
        stem=clean_stem,
        debug=debug,
    )

    if code == 0 and data is not None:
        if "METADATA" not in data:
            data["METADATA"] = {}
        data["METADATA"]["SOURCE_HASH"] = md_hash
        data["METADATA"]["NORMALIZED_AT"] = datetime.datetime.now().isoformat()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(safe_yaml_dump(data))
        out_success(f"✅ Saved: {output_path}")
    else:
        out_error(f"❌ Failed to normalize {path.name}")

    return auto_overwrite


def normalize_prd(
    input_file=None,
    auto_overwrite=False,
    debug=False,
):
    from vibe_tools.cli import load_config

    config = load_config()
    cost_logger = CostLogger(config)

    try:
        prompt_base = get_prompt("prd_normalization_prompt.txt")
    except FileNotFoundError as e:
        out_error(f"Error: {e}")
        sys.exit(1)

    specs_dir = DEFAULT_SPECS_DIR
    if not specs_dir.exists():
        alt_specs = pathlib.Path("spec")
        if alt_specs.exists():
            specs_dir = alt_specs
        else:
            specs_dir.mkdir(exist_ok=True)

    PRD_DIR.mkdir(exist_ok=True)

    files_to_process = []
    if input_file:
        path = pathlib.Path(input_file)
        if not path.exists():
            out_error(f"Error: File {input_file} not found.")
            sys.exit(1)
        files_to_process = [(path, path.read_text(), path.stat().st_mtime)]
    else:
        # Collect from product root (excluding system files)
        if specs_dir.exists():
            for path in specs_dir.glob("*.md"):
                if path.stem in SYSTEM_FILES:
                    continue
                try:
                    files_to_process.append(
                        (path, path.read_text(), path.stat().st_mtime)
                    )
                except Exception as e:
                    out_warn(f"⚠️  Warning: Could not read {path}: {e}")

        # Collect from backlog/inbox
        for d in [PLANNING_BACKLOG_DIR, PLANNING_INBOX_DIR]:
            if d.exists():
                for path in d.rglob("*.md"):
                    if any(p[0] == path for p in files_to_process):
                        continue
                    try:
                        files_to_process.append(
                            (path, path.read_text(), path.stat().st_mtime)
                        )
                    except Exception as e:
                        out_warn(f"⚠️  Warning: Could not read {path}: {e}")

        if not files_to_process:
            out_error(f"❌ No PRDs found to normalize.")
            return

    if isinstance(auto_overwrite, str):
        overwrite_mode = auto_overwrite
    else:
        overwrite_mode = "yes" if auto_overwrite else "ask"

    if not input_file:
        existing_prds = list(PRD_PROCESSING_DIR.rglob("v*-*_*.yaml"))
        if existing_prds and overwrite_mode == "ask" and sys.stdin.isatty():
            choice = click.prompt(
                f"Found {len(existing_prds)} existing PRDs. Overwrite? [y]es, [n]o, [a]sk per file",
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
        clean_stem = stem.lower()
        while True:
            new_stem = re.sub(r"^prd[-_ ]?", "", clean_stem)
            if new_stem == clean_stem:
                break
            clean_stem = new_stem
        clean_stem = re.sub(r"[- ]", "_", clean_stem)

        if config.get("ralph", {}).get("auto_merge", False):
            from vibe_tools.utils import get_automerge_branch

            branch_name = get_automerge_branch(config)
        else:
            branch_name = f"vibe/normalize/{clean_stem}"

        _switch_to_branch(branch_name, "gemini", clean_stem, stream=False)

        if not spec_path.exists():
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            spec_path.write_text(pre_read_content)

        # Target directory logic
        if (
            PLANNING_BACKLOG_DIR in spec_path.parents
            or spec_path.parent == PLANNING_BACKLOG_DIR
        ):
            target_base = PRD_PROCESSING_DIR
            rel_dir = spec_path.parent.relative_to(PLANNING_BACKLOG_DIR)
        elif (
            PLANNING_HISTORY_DIR in spec_path.parents
            or spec_path.parent == PLANNING_HISTORY_DIR
        ):
            target_base = PRD_DONE_DIR
            rel_dir = spec_path.parent.relative_to(PLANNING_HISTORY_DIR)
        elif (
            PLANNING_INBOX_DIR in spec_path.parents
            or spec_path.parent == PLANNING_INBOX_DIR
        ):
            target_base = PRD_PROCESSING_DIR
            rel_dir = spec_path.parent.relative_to(PLANNING_INBOX_DIR)
        else:
            target_base = PRD_PROCESSING_DIR
            try:
                rel_dir = spec_path.parent.relative_to(PLANNING_BACKLOG_DIR)
            except ValueError:
                rel_dir = spec_path.parent.relative_to(specs_dir)

        target_prd_dir = target_base / rel_dir
        target_prd_dir.mkdir(parents=True, exist_ok=True)

        # Output path determination
        md_content = pre_read_content
        implementation_id = None
        if md_content.startswith("---"):
            parts = md_content.split("---", 2)
            if len(parts) >= 3:
                fm = safe_yaml_load(parts[1]) or {}
                implementation_id = fm.get("implementation", {}).get("id")

        existing_yaml = None
        search_dirs = [PRD_PROCESSING_DIR, PRD_DONE_DIR, PRD_FAILED_DIR]
        for sd in search_dirs:
            if not sd.exists():
                continue
            leg = sd / f"prd_{clean_stem}.yaml"
            if leg.exists():
                existing_yaml = leg
                break
            ver_files = list(sd.glob(f"v*-*_{clean_stem}.yaml"))
            if ver_files:
                existing_yaml = ver_files[0]
                break

        if existing_yaml:
            output_path = existing_yaml
            output_filename = existing_yaml.name
        elif implementation_id:
            output_filename = f"{implementation_id}_{clean_stem}.yaml"
            output_path = target_prd_dir / output_filename
        else:
            output_filename = f"PENDING_{clean_stem}.yaml"
            output_path = target_prd_dir / output_filename

        # Skip logic
        md_hash = get_file_hash(spec_path)
        if output_path.exists():
            try:
                existing_data = safe_yaml_load(output_path.read_text())
                if existing_data and isinstance(existing_data, dict):
                    old_hash = existing_data.get("METADATA", {}).get("SOURCE_HASH")
                if old_hash == md_hash:
                    out_info(f"⏩ Skipping {spec_path.name} (already up-to-date)")
                    switch_to_main()
                    continue

                if overwrite_mode == "yes":
                    pass
                elif overwrite_mode == "no":
                    out_info(f"⏩ Skipping {spec_path.name} (overwrite mode: no)")
                    switch_to_main()
                    continue
                elif sys.stdin.isatty():
                    choice = click.prompt(
                        f"⚠️  {spec_path.name} has changed. Update {output_path.name}? [y]es, [n]o, [A]ll, [N]one",
                        type=click.Choice(["y", "n", "a", "N"], case_sensitive=False),
                        default="y",
                    )
                    if choice.lower() == "a":
                        overwrite_mode = "yes"
                    elif choice.lower() == "n":
                        switch_to_main()
                        continue
                    elif choice.lower() == "N":
                        overwrite_mode = "no"
                        switch_to_main()
                        continue
            except Exception as e:
                logger.warning(f"Could not read existing hash from {output_path}: {e}")

        out_info(f"🔄 Normalizing: {spec_path.name} -> {output_path.name} using Gemini...")
        prompt = prompt_base.replace("{PASTE HUMAN PRD HERE}", md_content)

        data, code = _run_normalization_llm(
            prompt=prompt,
            cost_logger=cost_logger,
            stem=stem,
            debug=debug,
        )

        if code == 0 and data is not None:
            if "METADATA" not in data:
                data["METADATA"] = {}
            data["METADATA"]["SOURCE_HASH"] = md_hash
            data["METADATA"]["NORMALIZED_AT"] = datetime.datetime.now().isoformat()

            data["TITLE"] = data.get("TITLE", clean_stem.replace("_", " ").title())
            data["DEPENDS_ON"] = data.get("DEPENDS_ON", [])
            data["BRANCH"] = data.get("BRANCH", f"feature/{clean_stem}")
            data["PARENT_BRANCH"] = data.get("PARENT_BRANCH", get_main_branch())

            if output_filename.startswith("PENDING_"):
                state = load_project_state()
                version = state.get("current_version", "01")
                dependencies = data.get("DEPENDS_ON", [])
                max_dep_seq = 0
                plans = state.get("plans", {})
                for dep_id in dependencies:
                    dep_info = plans.get(dep_id) or plans.get(f"prd_{dep_id}")
                    if dep_info:
                        dep_filename = pathlib.Path(dep_info["file"]).name
                        parsed = parse_prd_filename(dep_filename)
                        if parsed["sequence"]:
                            max_dep_seq = max(max_dep_seq, parsed["sequence"])
                next_seq = max(max_dep_seq + 10, state.get("next_sequence", 10))
                state["next_sequence"] = next_seq + 10
                save_project_state(state)
                output_filename = f"v{version}-{next_seq:03d}_{clean_stem}.yaml"
                output_path = target_prd_dir / output_filename
                update_md_implementation_status(
                    spec_path, version, next_seq, output_path
                )

            output_path.write_text(safe_yaml_dump(data))
            out_success(f"✅ Saved: {output_path}")

            if is_dirty():
                run_command(["git", "add", "."], check=False)
                run_command(
                    ["git", "commit", "-m", f"vibe: normalize PRD '{spec_path.name}'"],
                    check=False,
                )

            if not input_file:
                state = load_project_state()
                state["phases"]["normalize"]["status"] = "completed"
                save_project_state(state)

        switch_to_main()
