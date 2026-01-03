import pathlib
import sys
import click
from vibe_tools.utils import run_agent, get_agent_command

PROMPTS_DIR = pathlib.Path("prompts")
NORMALIZATION_PROMPT_TEMPLATE = PROMPTS_DIR / "pdr_normalization_prompt.txt"

def normalize_prd(agent, input_file):
    if not PROMPTS_DIR.exists():
        print("Error: prompts directory not found. Please run 'vibe init' first.")
        sys.exit(1)

    if not NORMALIZATION_PROMPT_TEMPLATE.exists():
        print(f"Error: Normalization prompt template not found at {NORMALIZATION_PROMPT_TEMPLATE}. Please run 'vibe init'.")
        sys.exit(1)

    input_path = pathlib.Path(input_file)
    if not input_path.exists():
        print(f"Error: Input file {input_file} not found.")
        sys.exit(1)

    human_prd = input_path.read_text()
    prompt_base = NORMALIZATION_PROMPT_TEMPLATE.read_text()
    prompt = prompt_base.replace("{PASTE HUMAN PRD HERE}", human_prd)

    print(f"Normalizing PRD: {input_file} using {agent}...")
    cmd = get_agent_command(agent, prompt)
    output, _ = run_agent(cmd)

    # Save to prds directory
    prds_dir = pathlib.Path("prds")
    prds_dir.mkdir(exist_ok=True)
    
    output_filename = f"prd_{input_path.stem}.yaml"
    output_path = prds_dir / output_filename
    
    output_path.write_text(output)
    print(f"Normalized PRD saved to: {output_path}")

