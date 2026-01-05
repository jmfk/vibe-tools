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
        stream: bool = True,
    ):
        self.agent_type = agent_type
        self.prompts_dir = pathlib.Path(prompts_dir or pathlib.Path("prompts"))
        self.stream = stream
        self.history: List[Dict[str, str]] = []
        self.current_query: str = ""
        self.additional_files: List[pathlib.Path] = []

    def run_loop(self, initial_prompt: Optional[str] = None):
        """Main interactive loop."""
        click.echo(click.style("\n🏗️  VIBE ARCHITECT", fg="cyan", bold=True))
        click.echo("Refine your architecture and infrastructure specs interactively.")
        click.echo("Type /help for available commands.\n")

        if initial_prompt:
            self.current_query = initial_prompt
            self._ask_to_send()

        while True:
            user_input = click.prompt("👤", default="", show_default=False).strip()

            if not user_input:
                continue

            if user_input.startswith("/"):
                if self._handle_slash_command(user_input):
                    break
                continue

            if self.current_query:
                self.current_query += f"\n{user_input}"
            else:
                self.current_query = user_input
            
            self._ask_to_send()

    def _ask_to_send(self):
        prompt = self._build_prompt()
        size_kb = len(prompt) / 1024
        click.echo(click.style(f"\n📝 Current prompt size: {size_kb:.2f} KB", fg="yellow"))
        click.echo("Type /send to dispatch to Architect, /reset to clear, or keep typing to add info.")

    def _handle_slash_command(self, command_str: str) -> bool:
        """Returns True if the loop should exit."""
        parts = command_str.split(" ", 2)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        sub_args = parts[2] if len(parts) > 2 else ""

        # Shortcuts/Aliases
        if cmd == "/s":
            cmd = "/send"
        elif cmd == "/r":
            cmd = "/reset"
        elif cmd == "/q":
            cmd = "/exit"
        elif cmd == "/l":
            cmd = "/list"
            args = "memory"
        elif cmd == "/f":
            cmd = "/files"
            args = "list"
        elif cmd == "/a" or cmd == "/add":
            sub_args = args
            args = "add"
            cmd = "/files"

        if cmd == "/help":
            self._show_help()
        elif cmd == "/send":
            if not self.current_query:
                click.echo("❌ Nothing to send. Type something first.")
            else:
                self._dispatch_agent()
        elif cmd == "/reset":
            self.current_query = ""
            click.echo("✅ Prompt reset.")
        elif cmd == "/show":
            if args.lower() in ["arch", "architecture"]:
                self._show_file(ARCHITECTURE_SPEC)
            elif args.lower() in ["infra", "infrastructure"]:
                self._show_file(INFRA_SPEC)
            else:
                click.echo("❌ Usage: /show [arch|infra]")
        elif cmd == "/history":
            self._handle_history_command(args, sub_args)
        elif cmd == "/files":
            self._handle_files_command(args, sub_args)
        elif cmd == "/list":
            if args == "memory":
                self._list_memory()
            else:
                click.echo("❌ Usage: /list memory")
        elif cmd == "/exit" or cmd == "/quit":
            return True
        else:
            click.echo(f"❌ Unknown command: {cmd}. Type /help for options.")

        return False

    def _show_help(self):
        click.echo("\nAvailable commands:")
        click.echo("  /send, /s        - Dispatch current prompt to Architect")
        click.echo("  /reset, /r       - Clear the current pending prompt")
        click.echo("  /show [arch|infra] - Display current specs")
        click.echo("  /history [list|view <idx>|remove <idx>] - Manage interaction history")
        click.echo("  /files, /f [list|add <path>|remove <path>] - Manage additional context files")
        click.echo("  /add, /a <path>  - Shortcut to add a file to context")
        click.echo("  /list memory, /l - List all pending text and files in memory")
        click.echo("  /help            - Show this help message")
        click.echo("  /exit, /q        - Exit the session")

    def _handle_history_command(self, sub_cmd, args):
        if not sub_cmd or sub_cmd == "list":
            if not self.history:
                click.echo("📜 History is empty.")
            for i, h in enumerate(self.history):
                click.echo(f"[{i}] {h['role'].upper()}: {h['content'][:100]}...")
        elif sub_cmd == "view":
            try:
                idx = int(args)
                h = self.history[idx]
                click.echo(f"\n--- History [{idx}] ({h['role'].upper()}) ---")
                click.echo(h['content'])
            except (ValueError, IndexError):
                click.echo("❌ Invalid history index.")
        elif sub_cmd == "remove":
            try:
                idx = int(args)
                removed = self.history.pop(idx)
                click.echo(f"✅ Removed history item [{idx}]: {removed['role']}")
            except (ValueError, IndexError):
                click.echo("❌ Invalid history index.")

    def _handle_files_command(self, sub_cmd, args):
        if not sub_cmd or sub_cmd == "list":
            if not self.additional_files:
                click.echo("📁 No additional files added.")
            for f in self.additional_files:
                click.echo(f"- {f}")
        elif sub_cmd == "add":
            p = pathlib.Path(args)
            if p.exists() and p.is_file():
                if p not in self.additional_files:
                    self.additional_files.append(p)
                    click.echo(f"✅ Added file: {p}")
                else:
                    click.echo("ℹ️ File already in context.")
            else:
                click.echo(f"❌ File not found: {args}")
        elif sub_cmd == "remove":
            p = pathlib.Path(args)
            if p in self.additional_files:
                self.additional_files.remove(p)
                click.echo(f"✅ Removed file: {p}")
            else:
                click.echo(f"❌ File not in context: {args}")

    def _list_memory(self):
        click.echo("\n--- Current Memory ---")
        click.echo(click.style("Pending Prompt:", bold=True))
        click.echo(self.current_query or "(empty)")
        click.echo(click.style("\nIncluded Files:", bold=True))
        if not self.additional_files:
            click.echo("(none)")
        for f in self.additional_files:
            click.echo(f"- {f}")
        click.echo("----------------------")

    def _build_prompt(self) -> str:
        template_path = self.prompts_dir / self.PROMPT_FILENAME
        if not template_path.exists():
            from vibe_tools.templates import TEMPLATES
            content = TEMPLATES.get(self.PROMPT_FILENAME)
            if content:
                ensure_dir(self.prompts_dir)
                template_path.write_text(content)
            else:
                raise click.ClickException(f"Missing prompt template: {template_path}")

        arch_content = ARCHITECTURE_SPEC.read_text() if ARCHITECTURE_SPEC.exists() else "No architecture.md found."
        infra_content = INFRA_SPEC.read_text() if INFRA_SPEC.exists() else "No infrastructure.md found."

        history_text = "\n".join([f"{h['role'].upper()}: {h['content']}" for h in self.history])
        
        # Build additional files context
        files_context = ""
        for f in self.additional_files:
            try:
                files_context += f"\n\n--- FILE: {f} ---\n{f.read_text()}\n--- END FILE: {f} ---"
            except Exception as e:
                click.echo(f"⚠️ Error reading {f}: {e}")

        return template_path.read_text().format(
            architecture_content=arch_content,
            infrastructure_content=infra_content,
            history=history_text + files_context,
            query=self.current_query,
        )

    def _dispatch_agent(self):
        prompt = self._build_prompt()
        query = self.current_query
        
        click.echo("⏳ Architect is thinking...")
        command = get_agent_command(self.agent_type, prompt)
        output, exit_code = run_agent(command, stream=self.stream)

        if exit_code != 0:
            click.echo("❌ Architect failed to respond.")
            return

        self.history.append({"role": "user", "content": query})
        self.current_query = "" # Clear after successful send
        
        # Check for file updates
        if "FILE_UPDATE:" in output:
            parts = output.split("FILE_UPDATE:", 1)
            thinking = parts[0].strip()
            update_part = parts[1].strip()
            
            lines = update_part.splitlines()
            header = lines[0]
            content = "\n".join(lines[1:])
            
            if thinking:
                click.echo(f"\n💭 {thinking}")

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

