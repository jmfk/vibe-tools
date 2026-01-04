import json
import pathlib
import re
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple

import click

from vibe_tools.utils import ensure_dir, get_agent_command, run_agent


DspyRunner = Callable[[Dict[str, Any]], Dict[str, Any]]
AgentRunner = Callable[[str], Tuple[str, int]]


class PRDWriter:
    """Interactive PRD writer that uses dspy for Q&A and Gemini for markdown output."""

    PROMPT_FILENAME = "prd_generation_prompt.txt"
    MAX_INTERVIEW_ROUNDS = 8

    def __init__(
        self,
        agent_type: str = "cursor-agent",
        specs_dir: Optional[pathlib.Path] = None,
        prompts_dir: Optional[pathlib.Path] = None,
        dspy_runner: Optional[DspyRunner] = None,
        agent_runner: Optional[AgentRunner] = None,
        prd_type: str = "feature"
    ):
        self.agent_type = agent_type
        self.specs_dir = pathlib.Path(specs_dir or pathlib.Path("specs"))
        self.prompts_dir = pathlib.Path(prompts_dir or pathlib.Path("prompts"))
        self.dspy_runner = dspy_runner or self._execute_dspy
        self.agent_runner = agent_runner or self._default_agent_runner
        self.prd_type = prd_type

    def create_prd(self, initial_request: str) -> pathlib.Path:
        """Run the interview and write the resulting markdown PRD."""
        prompt = (initial_request or "").strip()
        if not prompt:
            raise click.ClickException("A feature description is required to write a PRD.")

        self._ensure_dspy_available()
        interview = self.run_interview(prompt)
        markdown = self.build_markdown(prompt, interview)
        return self.write_spec(prompt, markdown)

    def run_interview(self, initial_request: str) -> Dict[str, Any]:
        """Iteratively ask follow-up questions until dspy signals satisfaction."""
        history: List[Dict[str, str]] = []
        context_summary = initial_request
        last_summary = initial_request
        satisfied = False

        for iteration in range(self.MAX_INTERVIEW_ROUNDS):
            payload = {
                "initial_request": initial_request,
                "context": context_summary,
                "history": history,
                "iteration": iteration + 1,
            }
            response = self.dspy_runner(payload)
            context_summary = response.get("context", context_summary)
            summary = response.get("summary")
            if summary:
                last_summary = summary

            questions = [
                q for q in response.get("questions", []) or [] if q and q.strip()
            ]
            finished = bool(response.get("satisfied"))

            if not questions:
                satisfied = finished
                break

            for question in questions:
                answer = click.prompt(question, default="", show_default=False)
                history.append({"question": question, "answer": answer})

            if finished:
                satisfied = True
                break

        return {
            "history": history,
            "summary": last_summary or initial_request,
            "context": context_summary,
            "satisfied": satisfied,
        }

    def build_markdown(self, title: str, interview: Dict[str, Any]) -> str:
        """Ask Gemini to turn the interview data into markdown per the prompt template."""
        template_path = self.prompts_dir / self.PROMPT_FILENAME
        if not template_path.exists():
            raise click.ClickException(
                f"Prompt template not found at {template_path}. Run 'vibe init' first."
            )
        template = template_path.read_text()
        qa_section = self._render_history(interview.get("history", []))
        
        # Inject type guidance into context
        type_context = f"This is a {self.prd_type.upper()} PRD. Please focus on relevant sections."
        if self.prd_type == "infra":
            type_context += " Focus heavily on the Infrastructure and Architecture sections."
        elif self.prd_type == "cicd":
            type_context += " Focus on deployment, automation, and CI/CD pipelines in the Infrastructure section."
        elif self.prd_type == "architecture":
            type_context += " Focus on the Architecture and Constraints section."

        context = f"{type_context}\n\n{interview.get('context', '')}"
        
        prompt = template.format(
            title=title,
            summary=interview.get("summary", ""),
            context=context,
            qa=qa_section,
        )

        output, exit_code = self.agent_runner(prompt)
        if exit_code != 0:
            raise click.ClickException("Gemini failed to generate the PRD markdown.")

        return output

    def write_spec(self, title: str, markdown: str) -> pathlib.Path:
        """Write the markdown to the next numbered spec file."""
        ensure_dir(self.specs_dir)
        target = self._next_spec_path(title)
        target.write_text(markdown)
        click.echo(f"✅ Wrote {self.prd_type} PRD to {target}")
        return target

    def _next_spec_path(self, title: str) -> pathlib.Path:
        """Generate the next available numbered PRD filename."""
        ensure_dir(self.specs_dir)
        next_number = self._next_spec_number()
        slug = self._slugify(title)
        
        prefix = "prd"
        if self.prd_type != "feature":
            prefix = f"prd_{self.prd_type}"
            
        filename = f"{prefix}_{next_number:02d}_{slug}.md"
        return self.specs_dir / filename

    def _next_spec_number(self) -> int:
        """Return the next sequential spec number based on existing files."""
        ensure_dir(self.specs_dir)
        highest = 0
        
        prefix = "prd"
        if self.prd_type != "feature":
            prefix = f"prd_{self.prd_type}"
            
        pattern = f"{prefix}_*.md"
        for child in self.specs_dir.glob(pattern):
            parts = child.stem.split("_")
            try:
                # prd_01_... -> parts[1] is number
                # prd_infra_01_... -> parts[2] is number
                idx = 1 if self.prd_type == "feature" else 2
                if len(parts) > idx:
                    value = int(parts[idx])
                    highest = max(highest, value)
            except (ValueError, IndexError):
                continue
        return highest + 1

    def _slugify(self, text: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
        cleaned = cleaned.strip("-")
        return cleaned or "feature"

    def _render_history(self, history: List[Dict[str, str]]) -> str:
        if not history:
            return "No follow-up questions were needed."
        lines = []
        for idx, item in enumerate(history, start=1):
            question = item.get("question", "").strip()
            answer = item.get("answer", "").strip()
            lines.append(f"{idx}. **Q:** {question}\n   **A:** {answer}")
        return "\n".join(lines)

    def _ensure_dspy_available(self) -> None:
        if shutil.which("dspy") is None:
            raise click.ClickException("`dspy` is required but was not found in PATH.")

    def _execute_dspy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        command = ["dspy", "--model", "gemini-3-flash", "--json"]
        try:
            result = subprocess.run(
                command,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise click.ClickException("Failed to run dspy.") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise click.ClickException(
                f"dspy failed (exit {result.returncode}): {stderr or 'see logs'}"
            )

        raw_output = result.stdout.strip()
        if not raw_output:
            raise click.ClickException("dspy returned empty output.")

        try:
            start = raw_output.index("{")
            end = raw_output.rindex("}") + 1
            payload_text = raw_output[start:end]
            return json.loads(payload_text)
        except (ValueError, json.JSONDecodeError) as exc:
            raise click.ClickException("Unable to parse dspy output.") from exc

    def _default_agent_runner(self, prompt: str) -> Tuple[str, int]:
        command = get_agent_command(self.agent_type, prompt)
        return run_agent(command, caffeinate=False)

