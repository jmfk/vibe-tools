import json
import os
import pathlib
import re
import shutil
import subprocess
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple

import click

from vibe_tools.utils import (
    ensure_dir,
    get_agent_command,
    get_google_api_key,
    get_prompt,
    run_agent,
)

DspyRunner = Callable[[Dict[str, Any]], Dict[str, Any]]
AgentRunner = Callable[[str], Tuple[str, int]]


class PRDWriter:
    """[DEPRECATED] Interactive PRD writer that uses dspy for Q&A and Gemini for markdown output.

    Use `vibe pm` (InteractivePM) instead.
    """

    PROMPT_FILENAME = "prd_generation_prompt.txt"
    MAX_INTERVIEW_ROUNDS = 8

    def __init__(
        self,
        agent_type: str = "cursor-agent",
        specs_dir: Optional[pathlib.Path] = None,
        prompts_dir: Optional[pathlib.Path] = None,
        dspy_runner: Optional[DspyRunner] = None,
        agent_runner: Optional[AgentRunner] = None,
        prd_type: str = "feature",
        stream: bool = False,
    ):
        warnings.warn(
            "PRDWriter is deprecated and will be removed in a future version. Use vibe pm instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.agent_type = agent_type
        self.specs_dir = pathlib.Path(specs_dir or pathlib.Path("product"))
        self.prompts_dir = pathlib.Path(prompts_dir or pathlib.Path("prompts"))
        self.dspy_runner = dspy_runner or self._execute_dspy
        self.agent_runner = agent_runner or self._default_agent_runner
        self.prd_type = prd_type
        self.stream = stream

        # Load configurable iterations
        from vibe_tools.utils import load_config

        config = load_config()
        self.max_interview_rounds = config.get("iterations", {}).get(
            "prd_interview", self.MAX_INTERVIEW_ROUNDS
        )

    def create_prd(self, initial_request: str) -> pathlib.Path:
        """Run the interview and write the resulting markdown PRD."""
        prompt = (initial_request or "").strip()
        if not prompt:
            raise click.ClickException(
                "A feature description is required to write a PRD."
            )

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

        for iteration in range(self.max_interview_rounds):
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
        try:
            template = get_prompt(self.PROMPT_FILENAME)
        except FileNotFoundError as e:
            raise click.ClickException(str(e))

        qa_section = self._render_history(interview.get("history", []))

        # Inject type guidance into context
        type_context = (
            f"This is a {self.prd_type.upper()} PRD. Please focus on relevant sections."
        )
        if self.prd_type == "infra":
            type_context += (
                " Focus heavily on the Infrastructure and Architecture sections."
            )
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

        try:
            output, exit_code = self.agent_runner(prompt)
        except KeyboardInterrupt:
            click.echo("\n🛑 Generation cancelled.")
            raise click.Abort()

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
        """Check if dspy library is installed."""
        try:
            import dspy
        except ImportError:
            raise click.ClickException(
                "The `dspy-ai` library is required but not found. Please install it."
            )

    def _execute_dspy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        import dspy

        api_key = get_google_api_key()

        if not api_key:
            raise click.ClickException(
                "Google API Key is missing. Please run `vibe config api` first."
            )

        lm = dspy.LM("gemini/gemini-2.0-flash-exp", api_key=api_key)

        with dspy.context(lm=lm):

            class PRDQuestionSignature(dspy.Signature):
                """Analyzes project context and generates follow-up questions or signals completion."""

                context = dspy.InputField(
                    desc="JSON string containing project context and requirements"
                )
                questions = dspy.OutputField(
                    desc="List of follow-up questions to clarify requirements"
                )
                satisfied = dspy.OutputField(
                    desc="Boolean: True if enough information is present to generate PRD",
                    type=bool,
                )

            # Use TypedPredictor for better structured output handling
            predictor = dspy.TypedPredictor(PRDQuestionSignature)
            try:
                result = predictor(context=json.dumps(payload))
                return {
                    "questions": (
                        result.questions
                        if isinstance(result.questions, list)
                        else [result.questions]
                    ),
                    "satisfied": bool(result.satisfied),
                }
            except Exception as e:
                logger.error(f"DSPy execution failed: {e}")
                raise click.ClickException(
                    f"Failed to process requirements with DSPy: {e}"
                )

    def _default_agent_runner(self, prompt: str) -> Tuple[str, int]:
        command = get_agent_command(self.agent_type, prompt)
        return run_agent(command, caffeinate=False, stream=self.stream)


class InteractivePRD(PRDWriter):
    """[DEPRECATED] Integrated interactive script for writing PRDs.

    Use `vibe pm` (InteractivePM) instead.
    """

    QUESTIONS_PROMPT_FILENAME = "prd_questions_prompt.txt"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        warnings.warn(
            "InteractivePRD is deprecated and will be removed in a future version. Use vibe pm instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.history: List[Dict[str, str]] = []
        self.pending_questions: List[str] = []
        self.current_summary: str = ""
        self.current_draft: str = ""
        self.satisfied: bool = False
        self.title: str = ""
        self.context: str = ""

    def run_loop(self, initial_prompt: str):
        """Main interactive loop."""
        self.title = initial_prompt.splitlines()[0][:50]
        self.context = initial_prompt
        self.current_summary = initial_prompt

        click.echo(f"\n🚀 Starting interactive PRD session for: {self.title}")
        click.echo(
            "Type your answer, or use slash commands like /help, /generate, /save."
        )

        while True:
            if not self.pending_questions and not self.satisfied:
                self._fetch_new_questions()

            if self.pending_questions:
                q = self.pending_questions.pop(0)
                click.echo(f"\n🤖 {q}")
                user_input = click.prompt("👤", default="", show_default=False).strip()
            else:
                if self.satisfied:
                    click.echo(
                        "\n🤖 I have enough information. You can /generate the PRD or keep talking."
                    )
                user_input = click.prompt("👤", default="", show_default=False).strip()

            if not user_input:
                continue

            if user_input.startswith("/"):
                if self._handle_slash_command(user_input):
                    break
                continue

            # It's an answer or a comment
            if self.pending_questions or not self.satisfied:
                # If we were asking a specific question, record it
                self.history.append(
                    {
                        "question": q if "q" in locals() else "Follow-up",
                        "answer": user_input,
                    }
                )
            else:
                self.context += f"\nUser added: {user_input}"

            # Reset satisfied if user adds more info or we need more
            self.satisfied = False

    def _handle_slash_command(self, command_str: str) -> bool:
        """Returns True if the loop should exit."""
        parts = command_str.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            self._show_help()
        elif cmd == "/generate":
            self._generate_draft()
        elif cmd == "/review":
            self._review_draft()
        elif cmd == "/save":
            if not self.current_draft:
                click.echo("❌ No draft generated yet. Run /generate first.")
            else:
                self.write_spec(self.title, self.current_draft)
                return True
        elif cmd == "/add":
            if not args:
                click.echo("❌ Usage: /add <context information>")
            else:
                self.context += f"\n{args}"
                click.echo("✅ Context added.")
                self.satisfied = False
        elif cmd == "/reset":
            if click.confirm(
                "Are you sure you want to reset the session?", default=False
            ):
                self.history = []
                self.pending_questions = []
                self.current_draft = ""
                self.satisfied = False
                click.echo("✅ Session reset.")
        elif cmd == "/exit":
            if click.confirm("Exit without saving?", default=True):
                return True
        else:
            click.echo(f"❌ Unknown command: {cmd}. Type /help for options.")

        return False

    def _show_help(self):
        click.echo("\nAvailable commands:")
        click.echo("  /generate - Generate a markdown PRD draft")
        click.echo("  /review   - View the current draft")
        click.echo("  /save     - Save the finalized PRD to product/")
        click.echo("  /add <msg>- Manually add information to the context")
        click.echo("  /reset    - Clear all history and start over")
        click.echo("  /help     - Show this help message")
        click.echo("  /exit     - Exit the session")

    def _fetch_new_questions(self):
        """Ask the AI for new questions based on current context."""
        try:
            prompt_template = get_prompt(self.QUESTIONS_PROMPT_FILENAME)
        except FileNotFoundError as e:
            raise click.ClickException(str(e))

        prompt = prompt_template.format(
            title=self.title,
            summary=self.current_summary,
            context=self.context,
            history=self._render_history(self.history),
        )

        # We use the agent_runner but expect JSON output
        # For simplicity in this implementation, we'll try to parse JSON from the agent output
        output, exit_code = self.agent_runner(prompt + "\nOUTPUT ONLY THE JSON.")
        if exit_code != 0:
            click.echo("⚠️ AI failed to generate questions.")
            return

        try:
            # Simple JSON extraction
            import json

            start = output.find("{")
            end = output.rfind("}") + 1
            data = json.loads(output[start:end])

            self.current_summary = data.get("summary", self.current_summary)
            self.pending_questions = data.get("questions", [])
            self.satisfied = data.get("satisfied", False)
        except Exception as e:
            click.echo(f"⚠️ Failed to parse AI response: {e}")

    def _generate_draft(self):
        click.echo("⏳ Generating PRD draft... (Ctrl-C to cancel)")
        interview_data = {
            "history": self.history,
            "summary": self.current_summary,
            "context": self.context,
        }
        self.current_draft = self.build_markdown(self.title, interview_data)
        click.echo("✅ Draft generated! Use /review to see it or /save to finalize.")

    def _review_draft(self):
        if not self.current_draft:
            click.echo("❌ No draft generated. Run /generate first.")
            return

        click.echo("\n--- CURRENT PRD DRAFT ---")
        click.echo(self.current_draft)
        click.echo("--- END OF DRAFT ---\n")
