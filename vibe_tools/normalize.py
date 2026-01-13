import datetime
import pathlib
import re
import sys

import click
import yaml

from vibe_tools.cost import CostLogger
from vibe_tools.branches import _switch_to_branch
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


def normalize_to_data(md_content: str, stem: str, debug: bool = False) -> dict:
    """Normalize PRD content to structured data without writing to disk."""
    from vibe_tools.cli import load_config
    config = load_config()
    cost_logger = CostLogger(config)

    try:
        prompt_base = get_prompt("prd_normalization_prompt.txt")
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return {}

    prompt = prompt_base.replace("{PASTE HUMAN PRD HERE}", md_content)
    data, code = _run_normalization_llm(
        prompt=prompt,
        cost_logger=cost_logger,
        stem=stem,
        debug=debug,
    )

    if code == 0 and data is not None:
        return data
    return {}


def normalize_system_file(
    input_file,
    auto_overwrite=False,
    debug=False,
    force=False,
):
    """Normalize core project system files (architecture, infrastructure, etc.)."""
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
        except Exception as e:
            logger.warning(f"Could not read existing hash from {output_path}: {e}")

    out_info(
        f"🔄 Normalizing system file: {path.name} -> {output_path.name} using Gemini..."
    )
    
    data = normalize_to_data(md_content, clean_stem, debug=debug)

    if data:
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
    # This function is now legacy/unused in the new workflow but kept for CLI compatibility
    # The new workflow uses normalize_to_data in-memory
    from vibe_tools.cli import load_config
    config = load_config()
    
    specs_dir = DEFAULT_SPECS_DIR
    if not specs_dir.exists():
        specs_dir.mkdir(exist_ok=True)

    files_to_process = []
    if input_file:
        path = pathlib.Path(input_file)
        if not path.exists():
            out_error(f"Error: File {input_file} not found.")
            sys.exit(1)
        files_to_process = [(path, path.read_text(), path.stat().st_mtime)]
    else:
        # Collect from product backlog
        for path in PLANNING_BACKLOG_DIR.rglob("*.md"):
            try:
                files_to_process.append((path, path.read_text(), path.stat().st_mtime))
            except Exception as e:
                out_warn(f"⚠️  Warning: Could not read {path}: {e}")

    for spec_path, content, mtime in files_to_process:
        stem = spec_path.stem
        out_info(f"🔄 Normalizing PRD: {spec_path.name}...")
        data = normalize_to_data(content, stem, debug=debug)
        if data:
            # For legacy CLI compatibility, we still save to PRD_PROCESSING_DIR
            # and try to preserve relative structure if possible
            try:
                rel_path = spec_path.relative_to(PLANNING_BACKLOG_DIR).with_suffix(".yaml")
                output_path = PRD_PROCESSING_DIR / rel_path
            except ValueError:
                output_path = PRD_PROCESSING_DIR / f"{stem}.yaml"
                
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(safe_yaml_dump(data))
            out_success(f"✅ Normalized: {spec_path.name} -> {output_path}")
        else:
            out_error(f"❌ Failed to normalize {spec_path.name}")
