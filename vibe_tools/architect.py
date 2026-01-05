import pathlib
from typing import Dict, List, Optional, Tuple, Any

import click

from vibe_tools.utils import (
    ARCHITECTURE_SPEC,
    INFRA_SPEC,
    ensure_dir,
    get_agent_command,
    run_agent,
    logger,
    ARCH_CONFIG_FILE,
    ARCH_SESSION_FILE,
    get_instructions_context,
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
        self.current_query: str = ""
        self.additional_files: List[pathlib.Path] = []
        self.config = self._load_config()
        self.mode = "ASK"  # Default mode
        self._load_session()

    def _load_config(self) -> Dict[str, Any]:
        if ARCH_CONFIG_FILE.exists():
            try:
                import json
                return json.loads(ARCH_CONFIG_FILE.read_text())
            except Exception:
                pass
        return {"md_editor": None, "code_editor": None}

    def _save_config(self):
        import json
        ensure_dir(ARCH_CONFIG_FILE.parent)
        ARCH_CONFIG_FILE.write_text(json.dumps(self.config, indent=2))

    def _load_session(self):
        if ARCH_SESSION_FILE.exists():
            try:
                import json
                data = json.loads(ARCH_SESSION_FILE.read_text())
                self.history = data.get("history", [])
                self.current_query = data.get("current_query", "")
                self.additional_files = [pathlib.Path(f) for f in data.get("additional_files", [])]
                self.mode = data.get("mode", "ASK")
            except Exception as e:
                logger.debug(f"Error loading architect session: {e}")

    def _save_session(self):
        import json
        ensure_dir(ARCH_SESSION_FILE.parent)
        data = {
            "history": self.history,
            "current_query": self.current_query,
            "additional_files": [str(f) for f in self.additional_files],
            "mode": self.mode
        }
        ARCH_SESSION_FILE.write_text(json.dumps(data, indent=2))

    def run_loop(self, initial_prompt: Optional[str] = None):
        """Main interactive loop."""
        click.echo(click.style("\n🏗️  VIBE ARCHITECT", fg="cyan", bold=True))
        click.echo("Refine your architecture and infrastructure specs interactively.")
        click.echo("Type /help for available commands.\n")

        if initial_prompt:
            self.current_query = initial_prompt
            self._ask_to_send()

        while True:
            prompt_symbol = click.style(f"({self.mode}) 👤", fg="green" if self.mode == "ASK" else "red")
            user_input = click.prompt(prompt_symbol, default="", show_default=False).strip()

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
            
            self._save_session()
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
            self._save_session()
            click.echo("✅ Prompt reset.")
        elif cmd == "/show":
            if args.lower() in ["arch", "architecture"]:
                self._show_file(ARCHITECTURE_SPEC)
            elif args.lower() in ["infra", "infrastructure"]:
                self._show_file(INFRA_SPEC)
            else:
                click.echo("❌ Usage: /show [arch|infra]")
        elif cmd == "/edit":
            self._handle_edit_command(args)
        elif cmd == "/history":
            self._handle_history_command(args, sub_args)
            self._save_session()
        elif cmd == "/files":
            self._handle_files_command(args, sub_args)
            self._save_session()
        elif cmd == "/list":
            if args == "memory":
                self._list_memory()
            else:
                click.echo("❌ Usage: /list memory")
        elif cmd == "/conf":
            self._handle_conf_command(args, sub_args)
        elif cmd == "/mode" or cmd == "/m":
            self._handle_mode_command(args)
        elif cmd == "/ask":
            self._handle_mode_command("ask")
        elif cmd == "/agent":
            self._handle_mode_command("agent")
        elif cmd == "/exit" or cmd == "/quit":
            return True
        else:
            click.echo(f"❌ Unknown command: {cmd}. Type /help for options.")

        return False

    def _show_help(self):
        click.echo("\nAvailable commands:")
        click.echo("  /send, /s        - Dispatch current prompt to Architect")
        click.echo("  /reset, /r       - Clear the current pending prompt")
        click.echo("  /mode, /m [ASK|AGENT] - Switch between modes")
        click.echo("  /ask, /agent     - Shortcut to switch modes")
        click.echo("  /show [arch|infra] - Display current specs")
        click.echo("  /edit [path]     - Open file in code editor")
        click.echo("  /history [list|view <idx>|remove <idx>] - Manage interaction history")
        click.echo("  /files, /f [list|add <path>|remove <path>] - Manage additional context files")
        click.echo("  /add, /a <path>  - Shortcut to add a file to context")
        click.echo("  /list memory, /l - List all pending text and files in memory")
        click.echo("  /conf [md|code] <editor_cmd> - Configure preferred editor (e.g. /conf md typora)")
        click.echo("  /help            - Show this help message")
        click.echo("  /exit, /q        - Exit the session")

    def _handle_conf_command(self, target, editor):
        if not target or target not in ["md", "code"]:
            click.echo("❌ Usage: /conf [md|code] <editor_cmd>")
            return
        if not editor:
            click.echo(f"Current {target} editor: {self.config.get(f'{target}_editor') or 'None'}")
            return
        
        self.config[f"{target}_editor"] = editor
        self._save_config()
        click.echo(f"✅ Set {target} editor to: {editor}")

    def _handle_mode_command(self, new_mode):
        if not new_mode:
            # Toggle mode
            self.mode = "AGENT" if self.mode == "ASK" else "ASK"
        elif new_mode.upper() in ["ASK", "AGENT"]:
            self.mode = new_mode.upper()
        else:
            click.echo("❌ Usage: /mode [ASK|AGENT]")
            return
        
        self._save_session()
        color = "green" if self.mode == "ASK" else "red"
        click.echo(f"✅ Switched to {click.style(self.mode, fg=color)} mode.")

    def _handle_edit_command(self, path_str):
        if not path_str:
            click.echo("❌ Usage: /edit <path>")
            return
        p = pathlib.Path(path_str)
        if not p.exists():
            click.echo(f"❌ File not found: {path_str}")
            return
        
        editor = self.config.get("code_editor") or self.config.get("md_editor")
        if not editor:
            click.echo("❌ No editor configured. Use /conf code <cmd> or /conf md <cmd> first.")
            return
        
        try:
            import subprocess
            subprocess.Popen([editor, str(p)])
            click.echo(f"🚀 Opening {p} in {editor}...")
        except Exception as e:
            click.echo(f"❌ Failed to launch {editor}: {e}")

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

        mode_instructions = ""
        if self.mode == "ASK":
            mode_instructions = "CURRENT MODE: ASK. Do NOT generate any FILE_UPDATE commands. Only provide analysis, answers, or guidance. If the user asks for changes, explain what changes are needed but do NOT emit the machine-readable FILE_UPDATE tag."
        else:
            mode_instructions = "CURRENT MODE: AGENT. You ARE authorized to propose changes to architecture.md or infrastructure.md using the FILE_UPDATE: [arch|infra] tag as specified in the rules."

        return template_path.read_text().format(
            mode=self.mode,
            mode_instructions=mode_instructions,
            architecture_content=arch_content,
            infrastructure_content=infra_content,
            instructions=get_instructions_context(),
            history=history_text + files_context,
            query=self.current_query,
        )

    def _dispatch_agent(self):
        prompt = self._build_prompt()
        query = self.current_query
        
        click.echo("⏳ Architect is thinking... (Ctrl-C to cancel)")
        command = get_agent_command(self.agent_type, prompt)
        try:
            output, exit_code = run_agent(command, stream=self.stream)
        except KeyboardInterrupt:
            click.echo("\n🛑 Agent cancelled.")
            return

        if exit_code != 0:
            click.echo("❌ Architect failed to respond.")
            return

        self.history.append({"role": "user", "content": query})
        self.current_query = "" # Clear after successful send
        self._save_session()
        
        # Display the result (only if it wasn't streamed)
        if not self.stream:
            click.echo(f"\n🤖 {output}")

        # Check for file updates
        if "FILE_UPDATE:" in output:
            parts = output.split("FILE_UPDATE:", 1)
            thinking = parts[0].strip()
            update_part = parts[1].strip()
            
            lines = update_part.splitlines()
            header = lines[0]
            content = "\n".join(lines[1:])
            
            if thinking and not self.stream:
                # If we're not streaming, we already printed the full output above
                pass

            if "arch" in header.lower():
                ARCHITECTURE_SPEC.write_text(content)
                click.echo(f"✅ Updated {ARCHITECTURE_SPEC}")
                self.history.append({"role": "architect", "content": "Updated architecture.md"})
                self._save_session()
                self._maybe_open_editor(ARCHITECTURE_SPEC)
            elif "infra" in header.lower():
                INFRA_SPEC.write_text(content)
                click.echo(f"✅ Updated {INFRA_SPEC}")
                self.history.append({"role": "architect", "content": "Updated infrastructure.md"})
                self._save_session()
                self._maybe_open_editor(INFRA_SPEC)
            else:
                self.history.append({"role": "architect", "content": output})
                self._save_session()
        else:
            self.history.append({"role": "architect", "content": output})
            self._save_session()

    def _maybe_open_editor(self, path: pathlib.Path):
        editor = self.config.get("md_editor") if path.suffix == ".md" else self.config.get("code_editor")
        if editor:
            if click.confirm(f"🚀 Update detected. Open {path.name} in {editor}?", default=True):
                try:
                    import subprocess
                    subprocess.Popen([editor, str(path)])
                except Exception as e:
                    click.echo(f"⚠️ Failed to launch {editor}: {e}")

    def _show_file(self, path: pathlib.Path):
        if not path.exists():
            click.echo(f"❌ File not found: {path}")
            return
        
        # Check if we should open in editor
        editor = self.config.get("md_editor") if path.suffix == ".md" else self.config.get("code_editor")
        if editor:
            if click.confirm(f"Open {path.name} in {editor}?", default=True):
                try:
                    import subprocess
                    subprocess.Popen([editor, str(path)])
                    return
                except Exception as e:
                    click.echo(f"⚠️ Failed to open editor: {e}")

        click.echo(f"\n{click.style('--- ' + path.name + ' ---', fg='cyan', bold=True)}")
        content = path.read_text()
        if path.suffix == ".md":
            self._print_styled_markdown(content)
        else:
            click.echo(content)
        click.echo(f"{click.style('--- END OF ' + path.name + ' ---', fg='cyan', bold=True)}\n")

    def _print_styled_markdown(self, content: str):
        lines = content.splitlines()
        for line in lines:
            if line.startswith("#"):
                # Header
                click.echo(click.style(line.upper(), fg="green", bold=True))
            elif line.startswith("- ") or line.startswith("* "):
                # List item
                click.echo(click.style(line, fg="yellow"))
            elif "`" in line:
                # Code blocks / inline code
                click.echo(click.style(line, fg="white"))
            else:
                click.echo(line)

        click.echo("")

