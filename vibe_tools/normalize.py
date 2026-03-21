import pathlib
import re
from typing import Optional

import yaml

from vibe_tools.cost import CostLogger
from vibe_tools.utils import (
    get_prompt,
    load_config,
    logger,
    safe_yaml_load,
    safe_yaml_dump,
    out_debug,
    out_error,
    out_info,
    out_success,
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
            model="gemini-3-flash-preview",
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
    yaml_match = re.search(r"```(?:yaml)?\s*?\n?([\s\S]*?)\n?```", clean_output)
    if yaml_match:
        clean_output = yaml_match.group(1).strip()
    elif clean_output.startswith("```"):
        # Fallback for simple fence if regex didn't catch it
        lines = clean_output.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_output = "\n".join(lines).strip()

    data = None
    try:
        data = safe_yaml_load(clean_output)
        if data is None or not isinstance(data, dict):
            raise yaml.YAMLError("Output is not a valid YAML dictionary")
    except (yaml.YAMLError, Exception) as e:
        logger.warning(f"⚠️ Invalid YAML generated: {e}")
        out_info("🔄 Attempting to fix YAML using Gemini...")

        fix_prompt = f"""The following content was intended to be a YAML dictionary but is invalid or not a dictionary:
---
{clean_output}
---
Error: {e}

Please fix the YAML formatting issues and return ONLY the valid YAML content.
CRITICAL REQUIREMENTS:
1. The output MUST be a valid YAML dictionary (key-value pairs).
2. If any keys or values contain special characters like colons (":"), brackets, or dashes, they MUST be properly quoted.
3. Example of a common error to fix: 'Key: With: Colons: value' should be '"Key: With: Colons": "value"'.
4. Example of another common error: nested lists without a parent key. Fix these by converting to mappings or merging into a single list element.
5. Do NOT include any markdown formatting, just the raw YAML.
"""
        try:
            fixed_output = run_llm(fix_prompt, model="gemini-3-flash", debug=debug)
            if not fixed_output:
                raise ValueError("Fixed output from LLM is empty.")

            fixed_output = fixed_output.strip()
            # Robust extraction for fixed output as well
            yaml_match_fixed = re.search(
                r"```(?:yaml)?\s*?\n?([\s\S]*?)\n?```", fixed_output
            )
            if yaml_match_fixed:
                fixed_output = yaml_match_fixed.group(1).strip()
            elif fixed_output.startswith("```"):
                lines = fixed_output.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                fixed_output = "\n".join(lines).strip()

            data = safe_yaml_load(fixed_output)
            if data is None or not isinstance(data, dict):
                logger.error("❌ Fixed YAML is still not a valid dictionary.")
                data = {}
            else:
                out_success("✅ Successfully fixed YAML")
        except Exception as fix_err:
            logger.error(f"❌ Failed to fix YAML: {fix_err}")
            # If we still can't get a dict, return empty dict or try to recover what we can
            data = {}

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


def normalize_prd(
    input_file: Optional[pathlib.Path] = None,
    auto_overwrite: bool = False,
    debug: bool = False,
):
    """Validate PRD normalization from product/ without writing to disk."""

    # 1. Collect PRDs to normalize
    if input_file:
        files = [input_file]
    else:
        # Defaults to all PRDs in DEFAULT_SPECS_DIR
        files = [
            f
            for f in DEFAULT_SPECS_DIR.rglob("*.md")
            if f.stem
            not in [
                "architecture",
                "infrastructure",
                "cicd",
                "testing",
                "dev_environment",
                "project-overview",
                "project_overview",
                "setup",
            ]
        ]

    if not files:
        out_info("No PRDs found to normalize.")
        return

    for f in files:
        out_info(f"🔄 Validating normalization for {f.name}...")

        # Run normalization in-memory
        data = normalize_to_data(f.read_text(), f.stem, debug=debug)

        if data:
            out_success(f"✅ Normalization valid for {f.name}")
            if debug:
                out_debug(
                    f"\n--- YAML OUTPUT ---\n{safe_yaml_dump(data)}--- END YAML ---\n"
                )
        else:
            out_error(f"❌ Failed to normalize {f.name}")
