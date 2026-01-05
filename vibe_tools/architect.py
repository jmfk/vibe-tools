import pathlib
from typing import Dict, List, Optional, Tuple

import click

from vibe_tools.utils import (
    ARCHITECTURE_SPEC,
    INFRA_SPEC,
    ensure_dir,
    get_agent_command,
    run_agent,
    logger,
)


class InteractiveArchitect:
    """Interactive architecture and infrastructure spec manager."""

    PROMPT_FILENAME = "architect_prompt.txt"

    def __init__(
        self,
        agent_type: str = "cursor-agent",
        prompts_dir: Optional[pathlib.Path] = None,
        stream: bool = False,
    ):
        self.agent_type = agent_type
        self.prompts_dir = pathlib.Path(prompts_dir or pathlib.Path("prompts"))
        self.stream = stream
        self.history: List[Dict[str, str]] = []

    def run_loop(self, initial_prompt: Optional[str] = None):
        """Main interactive loop."""
        click.echo(click.style("\n🏗️  VIBE ARCHITECT", fg="cyan", bold=True))
        click.echo("Refine your architecture and infrastructure specs interactively.")
        click.echo("Type /help for available commands.\n")

        if initial_prompt:
            self._handle_query(initial_prompt)

        while True:
            user_input = click.prompt("👤", default="", show_default=False).strip()

            if not user_input:
                continue

            if user_input.startswith("/"):
                if self._handle_slash_command(user_input):
                    break
                continue

            self._handle_query(user_input)

    def _handle_slash_command(self, command_str: str) -> bool:
        """Returns True if the loop should exit."""
        parts = command_str.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            self._show_help()
        elif cmd == "/show":
            if args.lower() in ["arch", "architecture"]:
                self._show_file(ARCHITECTURE_SPEC)
            elif args.lower() in ["infra", "infrastructure"]:
                self._show_file(INFRA_SPEC)
            else:
                click.echo("❌ Usage: /show [arch|infra]")
        elif cmd in ["/edit", "/update"]:
            target = ""
            instr = ""
            if args.lower().startswith("arch"):
                target = "arch"
                instr = args[4:].strip()
            elif args.lower().startswith("infra"):
                target = "infra"
                instr = args[5:].strip()
            
            if not target or not instr:
                click.echo(f"❌ Usage: {cmd} [arch|infra] <instructions>")
            else:
                self._handle_query(f"Update {target}: {instr}")
        elif cmd == "/exit" or cmd == "/quit":
            return True
        else:
            click.echo(f"❌ Unknown command: {cmd}. Type /help for options.")

        return False

    def _show_help(self):
        click.echo("\nAvailable commands:")
        click.echo("  /show arch       - Display architecture.md")
        click.echo("  /show infra      - Display infrastructure.md")
        click.echo("  /edit arch <msg> - Propose changes to architecture.md")
        click.echo("  /edit infra <msg>- Propose changes to infrastructure.md")
        click.echo("  /help            - Show this help message")
        click.echo("  /exit            - Exit the session")

    def _show_file(self, path: pathlib.Path):
        if not path.exists():
            click.echo(f"❌ File not found: {path}")
            return
        click.echo(f"\n--- {path.name} ---")
        click.echo(path.read_text())
        click.echo(f"--- END OF {path.name} ---\n")

    def _handle_query(self, query: str):
        """Send query to agent and handle response."""
        template_path = self.prompts_dir / self.PROMPT_FILENAME
        if not template_path.exists():
            from vibe_tools.templates import TEMPLATES
            content = TEMPLATES.get(self.PROMPT_FILENAME)
            if content:
                ensure_dir(self.prompts_dir)
                template_path.write_text(content)
                click.echo(f"✅ Created missing prompt template: {template_path}")
            else:
                raise click.ClickException(f"Missing prompt template: {template_path}")

        arch_content = ARCHITECTURE_SPEC.read_text() if ARCHITECTURE_SPEC.exists() else "No architecture.md found."
        infra_content = INFRA_SPEC.read_text() if INFRA_SPEC.exists() else "No infrastructure.md found."

        history_text = "\n".join([f"{h['role'].upper()}: {h['content']}" for h in self.history])

        prompt = template_path.read_text().format(
            architecture_content=arch_content,
            infrastructure_content=infra_content,
            history=history_text,
            query=query,
        )

        click.echo("⏳ Architect is thinking...")
        command = get_agent_command(self.agent_type, prompt)
        output, exit_code = run_agent(command, stream=self.stream)

        if exit_code != 0:
            click.echo("❌ Architect failed to respond.")
            return

        self.history.append({"role": "user", "content": query})
        
        # Check for file updates
        if output.startswith("FILE_UPDATE:"):
            lines = output.splitlines()
            header = lines[0]
            content = "\n".join(lines[1:])
            
            if "arch" in header.lower():
                ARCHITECTURE_SPEC.write_text(content)
                click.echo(f"✅ Updated {ARCHITECTURE_SPEC}")
                self.history.append({"role": "architect", "content": "Updated architecture.md"})
            elif "infra" in header.lower():
                INFRA_SPEC.write_text(content)
                click.echo(f"✅ Updated {INFRA_SPEC}")
                self.history.append({"role": "architect", "content": "Updated infrastructure.md"})
            else:
                click.echo(f"\n🤖 {output}")
                self.history.append({"role": "architect", "content": output})
        else:
            click.echo(f"\n🤖 {output}")
            self.history.append({"role": "architect", "content": output})

        click.echo("")

