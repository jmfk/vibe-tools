import pathlib
import re
import sys

import click

from vibe_tools.cost import AGENT_DEFAULT_MODEL, CostLogger
from vibe_tools.utils import get_agent_command, run_agent

PROMPTS_DIR = pathlib.Path("prompts")
NORMALIZATION_PROMPT_TEMPLATE = PROMPTS_DIR / "pdr_normalization_prompt.txt"
DEFAULT_SPECS_DIR = pathlib.Path("specs")
PRDS_DIR = pathlib.Path("prds")


def normalize_prd(agent, input_file=None, auto_overwrite=False, caffeinate=False, stream=False):
    from vibe_tools.cli import load_config

    if not PROMPTS_DIR.exists():
        print("Error: prompts directory not found. Please run 'vibe init' first.")
        sys.exit(1)

    config = load_config()
    cost_logger = CostLogger(config)

    if not NORMALIZATION_PROMPT_TEMPLATE.exists():
        print(
            f"Error: Normalization prompt template not found at {NORMALIZATION_PROMPT_TEMPLATE}. Please run 'vibe init'."
        )
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
    PRDS_DIR.mkdir(exist_ok=True)

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
    existing_prds = list(PRDS_DIR.rglob("prd_*.yaml"))

    overwrite_all = auto_overwrite
    if existing_prds and not auto_overwrite:
        if click.confirm(
            f"Found {len(existing_prds)} existing files in {PRDS_DIR}/. Overwrite all?",
            default=False,
        ):
            overwrite_all = True

    prompt_base = NORMALIZATION_PROMPT_TEMPLATE.read_text()

    for spec_path in files_to_process:
        stem = spec_path.stem

        # Determine target PRD directory (preserving subdirectories)
        rel_dir = spec_path.parent.relative_to(specs_dir)
        target_prd_dir = PRDS_DIR / rel_dir
        target_prd_dir.mkdir(parents=True, exist_ok=True)

        # Determine output filename with normalized prefix and format
        # 1. Special case for shared global context files ("global truths")
        global_truths = ["architecture", "project_overview", "infrastructure", "cicd"]
        if stem.lower() in global_truths:
            output_filename = f"{stem.lower()}.yaml"
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
        else:
            print(f"❌ Failed to normalize {spec_path.name}")
