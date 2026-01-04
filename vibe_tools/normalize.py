import pathlib
import sys
import click
from vibe_tools.utils import run_agent, get_agent_command
from vibe_tools.cost import CostLogger, AGENT_DEFAULT_MODEL

PROMPTS_DIR = pathlib.Path("prompts")
NORMALIZATION_PROMPT_TEMPLATE = PROMPTS_DIR / "pdr_normalization_prompt.txt"
DEFAULT_SPECS_DIR = pathlib.Path("specs")
PRDS_DIR = pathlib.Path("prds")


def normalize_prd(agent, input_file=None, auto_overwrite=False, caffeinate=False):
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
        # Find all markdown files in specs
        files_to_process = list(specs_dir.glob("*.md"))
        if not files_to_process:
            print(
                f"No markdown files found in {specs_dir}/. Please add your PRDs as .md files there."
            )
            return

    # Check for existing normalized files
    existing_prds = list(PRDS_DIR.glob("prd_*.yaml"))
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
        # Handle case-insensitive "prd_" prefix normalization
        if stem.lower().startswith("prd_"):
            output_filename = f"prd_{stem[4:]}.yaml"
        else:
            output_filename = f"prd_{stem}.yaml"
        output_path = PRDS_DIR / output_filename

        if output_path.exists() and not overwrite_all:
            print(f"Skipping {spec_path.name} (already exists at {output_path})")
            continue

        print(f"Normalizing: {spec_path.name} -> {output_path.name} using {agent}...")

        human_prd = spec_path.read_text()
        prompt = prompt_base.replace("{PASTE HUMAN PRD HERE}", human_prd)

        cmd = get_agent_command(agent, prompt)
        output, code = run_agent(cmd, caffeinate=caffeinate)

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
