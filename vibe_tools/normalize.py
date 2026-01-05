import pathlib
import re
import sys
from typing import Dict, List, Any

import click

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.utils import (
    get_agent_command,
    run_agent,
    VIBE_PROJECT_DIR,
    PRD_DIR,
    PLANS_DIR,
    COMPILED_PLANS_DIR,
    PROJECT_PLAN,
    get_prompt,
    load_project_state,
    save_project_state,
    logger
)

import yaml

DEFAULT_SPECS_DIR = pathlib.Path("specs")


def normalize_prd(agent, input_file=None, auto_overwrite=False, caffeinate=False, stream=False):
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
            print(
                f"No markdown files found in {specs_dir}/. Please add your PRDs as .md files there."
            )
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

        # Determine target PRD directory (preserving subdirectories)
        rel_dir = spec_path.parent.relative_to(specs_dir)
        target_prd_dir = PRD_DIR / rel_dir
        target_prd_dir.mkdir(parents=True, exist_ok=True)

        # Determine output filename with normalized prefix and format
        # 1. Special case for shared global context files ("global truths")
        global_truths = ["architecture", "project_overview", "infrastructure", "cicd", "testing"]
        if stem.lower() in global_truths:
            output_filename = f"{stem.lower()}.yaml"
            # Global truths go to the project directory, not prds/
            output_path = VIBE_PROJECT_DIR / output_filename
        else:
            # 2. Handle PRD prefixes and format
            # Strip case-insensitive "prd" or "PRD" prefix if followed by -, _, or space
            normalized_stem = re.sub(r"^(prd|PRD)[-_ ]?", "", stem)
            
            # Replace remaining dashes with underscores for consistency
            normalized_stem = normalized_stem.replace("-", "_")
            
            # Ensure it starts with prd_
            output_filename = f"prd_{normalized_stem.lower()}.yaml"
            output_path = target_prd_dir / output_filename

        # Optimization: Skip if YAML is newer than the source MD
        if output_path.exists():
            md_mtime = spec_path.stat().st_mtime
            yaml_mtime = output_path.stat().st_mtime
            if yaml_mtime > md_mtime and not overwrite_all:
                print(f"⏩ Skipping {spec_path.name} (already up-to-date at {output_path.name})")
                continue

        if output_path.exists() and not overwrite_all:
            if not click.confirm(f"Overwrite existing {output_path.name}?", default=False):
                continue

        print(f"🔄 Normalizing: {spec_path.name} -> {output_path.name} using {agent}...")

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

            # Update project state if this was a full normalization run
            if not input_file:
                from vibe_tools.utils import load_project_state, save_project_state
                state = load_project_state()
                state["phases"]["normalize"]["status"] = "completed"
                save_project_state(state)
        else:
            print(f"❌ Failed to normalize {spec_path.name}")


def _extract_all_plans(index_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Helper to extract all plan objects from the nested phases/prds structure."""
    all_plans = []
    phases = index_data.get("phases", {})

    # Standard phases: setup, infra, cicd
    for phase_name in ["setup", "infra", "cicd"]:
        phase_data = phases.get(phase_name, {})
        all_plans.extend(phase_data.get("plans", []))

    # Implementation phase: grouped by PRDs
    implement = phases.get("implement", {})
    prds = implement.get("prds", [])
    for prd in prds:
        all_plans.extend(prd.get("plans", []))

    return all_plans


def normalize_plans(agent: str, stream: bool = False) -> bool:
    """Normalizes Markdown plans in plans/ into machine-consumable YAML files in compiled_plans/."""
    from vibe_tools.utils import migrate_to_project_dir

    migrate_to_project_dir()

    if not PROJECT_PLAN.exists():
        logger.error(f"❌ {PROJECT_PLAN} not found. Planning failed.")
        return False

    try:
        index_data = yaml.safe_load(PROJECT_PLAN.read_text())
    except Exception as e:
        logger.error(f"Failed to parse {PROJECT_PLAN}: {e}")
        return False

    all_plans = _extract_all_plans(index_data)
    if not all_plans:
        logger.warning("No plans found in project-plan.yaml index.")
        return True

    try:
        prompt_base = get_prompt("plan_normalization_prompt.txt")
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return False

    COMPILED_PLANS_DIR.mkdir(exist_ok=True)

    for plan_info in all_plans:
        plan_file = pathlib.Path(plan_info.get("file"))
        if not plan_file.exists():
            logger.error(f"Plan file {plan_file} not found.")
            continue

        # Target is in COMPILED_PLANS_DIR
        yaml_path = COMPILED_PLANS_DIR / (plan_file.stem + ".yaml")
        
        # Optimization: skip if yaml is newer than markdown
        if yaml_path.exists() and yaml_path.stat().st_mtime > plan_file.stat().st_mtime:
            continue

        logger.info(f"🔄 Normalizing plan: {plan_file.name} -> {yaml_path.name}...")
        prompt = prompt_base.replace("{plan_content}", plan_file.read_text())
        cmd = get_agent_command(agent, prompt)
        output, code = run_agent(cmd, stream=stream)

        if code == 0:
            # Clean markdown code fences if present
            clean_output = output.strip()
            if clean_output.startswith("```"):
                lines = clean_output.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_output = "\n".join(lines).strip()

            yaml_path.write_text(clean_output)
            logger.info(f"✅ Saved: {yaml_path}")

            # Sync to project-state.json
            try:
                plan_data = yaml.safe_load(clean_output)
                state = load_project_state()
                plan_id = plan_data.get("id")
                if plan_id:
                    state["plans"][plan_id] = {
                        "status": plan_data.get("status", "pending"),
                        "depends_on": plan_data.get("dependencies", []),
                        "title": plan_data.get("title", plan_id),
                    }
                    save_project_state(state)
            except Exception as e:
                logger.error(f"Failed to sync plan {plan_file.name} to state: {e}")
        else:
            logger.error(f"❌ Failed to normalize plan {plan_file.name}")
            return False

    return True
