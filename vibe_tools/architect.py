import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Tuple, Any

import click

try:
    import readline
except ImportError:
    readline = None  # type: ignore

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
    VIBE_PROJECT_DIR,
)


class ArchitectCompleter:
    def __init__(self, architect):
        self.architect = architect
        # Sort commands so cycling order is predictable (alphabetical)
        # We only show the full commands in the completion list
        self.commands = sorted(
            [
                "/send",
                "/reset",
                "/mode",
                "/ask",
                "/agent",
                "/show",
                "/edit",
                "/history",
                "/files",
                "/add",
                "/list",
                "/exit",
                "/conf",
                "/help",
            ]
        )
        self.subcommands = {
            "/files": sorted(["list", "add", "remove"]),
            "/history": sorted(["list", "view", "remove"]),
            "/list": sorted(["memory"]),
            "/conf": sorted(["md", "code"]),
            "/show": sorted(["arch", "infra"]),
        }

    def complete(self, text, state):
        buffer = readline.get_line_buffer() if readline else ""

        # If there's no space, we are completing the primary command
        if " " not in buffer:
            if buffer.startswith("/"):
                options = [c for c in self.commands if c.startswith(text)]
                return options[state] if state < len(options) else None
            return None

        # We have at least one space, so we are in subcommand/argument territory
        parts = buffer.split()
        if not parts:
            return None

        cmd = parts[0].lower()
        # Only complete if we are currently on the second word (the subcommand)
        # Check if there is only one space in the buffer (ignoring trailing)
        if buffer.count(" ") == 1 or (buffer.count(" ") > 1 and not text):
            if cmd in self.subcommands:
                subs = self.subcommands[cmd]
                options = [s for s in subs if s.startswith(text)]
                return options[state] if state < len(options) else None

        return None


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
        self.pending_prompt: str = ""
        self.session_memory: str = ""
        self.additional_files: List[pathlib.Path] = []
        self.config = self._load_config()
        self.mode = "ASK"  # Default mode
        self._load_session()
        self._setup_readline()

    def _setup_readline(self):
        if readline:
            readline.set_completer(ArchitectCompleter(self).complete)
            # Remove / from delimiters so /command is treated as one word
            readline.set_completer_delims(" \t\n;")

            if hasattr(readline, "set_auto_history"):
                readline.set_auto_history(True)

            if "libedit" in readline.__doc__:  # macOS compatibility
                # macOS default is often libedit
                readline.parse_and_bind("bind ^I menu-complete")
                readline.parse_and_bind('bind "\033[Z" backward-menu-complete')
                readline.parse_and_bind("bind -e")  # use emacs keybindings
            else:
                # GNU Readline
                readline.parse_and_bind("tab: menu-complete")
                readline.parse_and_bind('"\e[Z": menu-complete-backward')
                # Bind Escape to clear line
                readline.parse_and_bind('"\e": kill-whole-line')

            # Setup history file
            history_file = VIBE_PROJECT_DIR / ".architect_history"
            if history_file.exists():
                try:
                    readline.read_history_file(str(history_file))
                except Exception:
                    pass
            import atexit

            atexit.register(self._save_readline_history, history_file)

    def _save_readline_history(self, history_file):
        if readline:
            try:
                readline.set_history_length(1000)
                readline.write_history_file(str(history_file))
            except Exception:
                pass

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
                self.pending_prompt = data.get("pending_prompt", "")
                self.session_memory = data.get("session_memory", "")
                self.additional_files = [
                    pathlib.Path(f) for f in data.get("additional_files", [])
                ]
                self.mode = data.get("mode", "ASK")
            except Exception as e:
                logger.debug(f"Error loading architect session: {e}")

    def _save_session(self):
        import json

        ensure_dir(ARCH_SESSION_FILE.parent)
        data = {
            "history": self.history,
            "pending_prompt": self.pending_prompt,
            "session_memory": self.session_memory,
            "additional_files": [str(f) for f in self.additional_files],
            "mode": self.mode,
        }
        ARCH_SESSION_FILE.write_text(json.dumps(data, indent=2))

    def run_loop(self, initial_prompt: Optional[str] = None):
        """Main interactive loop."""
        click.echo(click.style("\n🏗️  VIBE ARCHITECT", fg="cyan", bold=True))
        click.echo("Refine your architecture and infrastructure specs interactively.")
        click.echo("Type /help for available commands.\n")

        if initial_prompt:
            self.pending_prompt = initial_prompt
            self._save_session()
            self._show_prompt_summary()

        while True:
            mode_color_code = "32" if self.mode == "ASK" else "31"  # Green or Red
            # Standard ANSI escape codes
            ESC = "\x1b"
            START = "\001"
            END = "\002"
            RESET = f"{START}{ESC}[0m{END}"
            MODE_COLOR = f"{START}{ESC}[{mode_color_code}m{END}"
            BOLD = f"{START}{ESC}[1m{END}"
            prompt_symbol = f"{MODE_COLOR}({self.mode}){RESET} {BOLD}👤{RESET} "

            try:
                user_input = input(prompt_symbol).strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                click.echo("\n🛑 Interrupted. Type /q to exit.")
                continue

            if not user_input:
                continue

            if user_input.startswith("/"):
                if self._handle_slash_command(user_input):
                    break
                continue

            # Regular text input updates the pending prompt
            if self.pending_prompt:
                self.pending_prompt += f"\n{user_input}"
            else:
                self.pending_prompt = user_input

            self._save_session()
            self._show_prompt_summary()

    def _show_prompt_summary(self):
        if not self.pending_prompt:
            return

        lines = self.pending_prompt.splitlines()
        count = len(lines)
        click.echo(
            click.style(f"\n📝 Pending Prompt ({count} lines):", fg="yellow", bold=True)
        )
        for line in lines[:5]:
            click.echo(f"  {line}")
        if count > 5:
            click.echo(f"  ... (+{count-5} more lines)")

        click.echo(
            click.style(
                "Type /s to send, /r to reset, or keep typing to add more.\n", dim=True
            )
        )

    def _handle_slash_command(self, command_str: str) -> bool:
        """Returns True if the loop should exit."""
        parts = command_str.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Shortcuts/Aliases
        if cmd == "/s":
            cmd = "/send"
        elif cmd == "/r":
            cmd = "/reset"
        elif cmd == "/q":
            cmd = "/exit"
        elif cmd == "/h":
            cmd = "/help"
        elif cmd == "/c":
            if readline:
                readline.clear_history()
                click.echo("✅ Shell history cleared.")
            return False
        elif cmd == "/l":
            cmd = "/list"
            args = "memory"
        elif cmd == "/f":
            cmd = "/files"
            if not args:
                args = "list"
        elif cmd == "/a":
            cmd = "/add"

        if cmd == "/help":
            self._show_help()
        elif cmd == "/send":
            if not self.pending_prompt and not self.additional_files:
                click.echo("❌ Nothing to send. Type something first.")
            else:
                self._dispatch_agent()
        elif cmd == "/reset":
            self.pending_prompt = ""
            self.session_memory = ""
            self.additional_files = []
            self._save_session()
            click.echo("✅ Session memory and pending prompt reset.")
        elif cmd == "/add":
            if args:
                if self.session_memory:
                    self.session_memory += f"\n{args}"
                else:
                    self.session_memory = args
                self._save_session()

                # Show summary of memory
                lines = self.session_memory.splitlines()
                count = len(lines)
                click.echo(
                    click.style(
                        f"✅ Session Memory Updated ({count} lines):",
                        fg="green",
                        bold=True,
                    )
                )
                for line in lines[:5]:
                    click.echo(f"  {line}")
                if count > 5:
                    click.echo(f"  ... (+{count-5} more lines)")
            else:
                click.echo("❌ Usage: /add <text>")
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
            sub_parts = args.split(" ", 1)
            sub_cmd = sub_parts[0] if sub_parts else "list"
            sub_args = sub_parts[1] if len(sub_parts) > 1 else ""
            self._handle_history_command(sub_cmd, sub_args)
            self._save_session()
        elif cmd == "/files":
            sub_parts = args.split(" ", 1)
            sub_cmd = sub_parts[0] if sub_parts else "list"
            sub_args = sub_parts[1] if len(sub_parts) > 1 else ""
            self._handle_files_command(sub_cmd, sub_args)
            self._save_session()
        elif cmd == "/list":
            if args == "memory":
                self._list_memory()
            else:
                click.echo("❌ Usage: /list memory")
        elif cmd == "/conf":
            sub_parts = args.split(" ", 1)
            target = sub_parts[0] if sub_parts else ""
            editor = sub_parts[1] if len(sub_parts) > 1 else ""
            self._handle_conf_command(target, editor)
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
        click.echo("  /add, /a <text>  - Add text to the pending prompt")
        click.echo("  /mode, /m [ASK|AGENT] - Switch between modes")
        click.echo("  /ask, /agent     - Shortcut to switch modes")
        click.echo("  /show [arch|infra] - Display current specs")
        click.echo("  /edit [path]     - Open file in code editor")
        click.echo(
            "  /history [list|view <idx>|remove <idx>] - Manage interaction history"
        )
        click.echo(
            "  /files, /f [list|add <path>|remove <path>] - Manage additional context files"
        )
        click.echo("  /list memory, /l - List pending text, files, and history summary")
        click.echo(
            "  /conf [md|code] <editor_cmd> - Configure preferred editor (e.g. /conf md typora)"
        )
        click.echo("  /help, /h        - Show this help message")
        click.echo("  /c               - Clear the shell prompt history")
        click.echo("  /exit, /q        - Exit the session")

    def _handle_conf_command(self, target, editor):
        if not target or target not in ["md", "code"]:
            click.echo("❌ Usage: /conf [md|code] <editor_cmd>")
            return
        if not editor:
            click.echo(
                f"Current {target} editor: {self.config.get(f'{target}_editor') or 'None'}"
            )
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
            click.echo(
                "❌ No editor configured. Use /conf code <cmd> or /conf md <cmd> first."
            )
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
                click.echo(h["content"])
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
        click.echo("\n--- Session Status ---")

        # Session Memory (Persistent)
        click.echo(
            click.style("Session Memory (Persistent - added via /a):", bold=True)
        )
        if self.session_memory:
            lines = self.session_memory.splitlines()
            for line in lines[:5]:
                click.echo(f"  {line}")
            if len(lines) > 5:
                click.echo(f"  ... (+{len(lines)-5} more lines)")
            click.echo(f"  ({len(lines)} lines total)")
        else:
            click.echo("  (empty)")

        # Pending Prompt
        click.echo(click.style("\nPending Prompt (Current task):", bold=True))
        if self.pending_prompt:
            lines = self.pending_prompt.splitlines()
            for line in lines[:5]:
                click.echo(f"  {line}")
            if len(lines) > 5:
                click.echo(f"  ... (+{len(lines)-5} more lines)")
            click.echo(f"  ({len(lines)} lines total)")
        else:
            click.echo("  (empty)")

        # Files
        click.echo(click.style("\nIncluded Files:", bold=True))
        if not self.additional_files:
            click.echo("  (none)")
        for f in self.additional_files:
            click.echo(f"  - {f}")

        # History
        click.echo(click.style("\nHistory Summary (Sent Prompts):", bold=True))
        sent_prompts = [h for h in self.history if h["role"] == "user"]
        if not sent_prompts:
            click.echo("  (none)")
        else:
            for i, h in enumerate(sent_prompts):
                title = h["content"].splitlines()[0][:60]
                click.echo(f"  [{i}] {title}...")

        # Total Payload size
        prompt = self._build_prompt()
        size_kb = len(prompt) / 1024
        click.echo(f"\n📦 Total payload: {size_kb:.2f} KB")
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

        arch_content = (
            ARCHITECTURE_SPEC.read_text()
            if ARCHITECTURE_SPEC.exists()
            else "No architecture.md found."
        )
        infra_content = (
            INFRA_SPEC.read_text()
            if INFRA_SPEC.exists()
            else "No infrastructure.md found."
        )

        history_text = "\n".join(
            [f"{h['role'].upper()}: {h['content']}" for h in self.history]
        )

        # Build additional files context
        files_context = ""
        for f in self.additional_files:
            try:
                files_context += (
                    f"\n\n--- FILE: {f} ---\n{f.read_text()}\n--- END FILE: {f} ---"
                )
            except Exception as e:
                click.echo(f"⚠️ Error reading {f}: {e}")

        # Combine global instructions with session memory
        instructions = get_instructions_context()

        mode_instructions = ""
        if self.mode == "ASK":
            mode_instructions = "CURRENT MODE: ASK. Do NOT generate any FILE_UPDATE commands. Only provide analysis, answers, or guidance. If the user asks for changes, explain what changes are needed but do NOT emit the machine-readable FILE_UPDATE tag."
        else:
            mode_instructions = "CURRENT MODE: AGENT. You ARE authorized to propose changes to architecture.md or infrastructure.md using the FILE_UPDATE: [arch|infra] tag as specified in the rules."

        user_memory_text = ""
        if self.session_memory:
            user_memory_text = (
                f"SESSION MEMORY (Persistent Instructions):\n{self.session_memory}"
            )

        return template_path.read_text().format(
            mode=self.mode,
            mode_instructions=mode_instructions,
            architecture_content=arch_content,
            infrastructure_content=infra_content,
            instructions=instructions,
            user_memory=user_memory_text,
            history=history_text + files_context,
            query=self.pending_prompt,
        )

    def _dispatch_agent(self):
        prompt = self._build_prompt()
        query = self.pending_prompt

        click.echo("⏳ Architect is thinking... (Ctrl-C to cancel)")
        command = get_agent_command(self.agent_type, prompt)

        # If streaming, show mode prefix before output
        if self.stream:
            mode_prefix = click.style(
                f"({self.mode})", fg="green" if self.mode == "ASK" else "red"
            )
            click.echo(f"{mode_prefix} 🤖 ", nl=False)

        try:
            output, exit_code = run_agent(command, stream=self.stream)
        except KeyboardInterrupt:
            click.echo("\n🛑 Agent cancelled.")
            return

        if exit_code != 0:
            click.echo("❌ Architect failed to respond.")
            return

        self.history.append({"role": "user", "content": query})
        self.pending_prompt = ""  # Clear after successful send

        # Check for file updates
        if "FILE_UPDATE:" in output:
            parts = output.split("FILE_UPDATE:", 1)
            thinking = parts[0].strip()
            update_part = parts[1].strip()

            lines = update_part.splitlines()
            header = lines[0]
            content = "\n".join(lines[1:])

            if thinking and not self.stream:
                mode_prefix = click.style(
                    f"({self.mode})", fg="green" if self.mode == "ASK" else "red"
                )
                click.echo(f"\n{mode_prefix} 🤖 Thinking: {thinking}")

            if "arch" in header.lower():
                ARCHITECTURE_SPEC.write_text(content)
                click.echo(f"✅ Updated {ARCHITECTURE_SPEC}")
                self.history.append(
                    {"role": "architect", "content": "Updated architecture.md"}
                )
                self._handle_response_display(content, ARCHITECTURE_SPEC)
            elif "infra" in header.lower():
                INFRA_SPEC.write_text(content)
                click.echo(f"✅ Updated {INFRA_SPEC}")
                self.history.append(
                    {"role": "architect", "content": "Updated infrastructure.md"}
                )
                self._handle_response_display(content, INFRA_SPEC)
            else:
                self.history.append({"role": "architect", "content": output})
                self._handle_response_display(output)
        else:
            self.history.append({"role": "architect", "content": output})
            self._handle_response_display(output)

        self._save_session()
        click.echo("")

    def _handle_response_display(
        self, content: str, path: Optional[pathlib.Path] = None
    ):
        """Decide whether to show the response in terminal or open in an editor."""
        if self.stream:
            # Already displayed during stream, maybe just offer to open in editor
            return

        md_editor = self.config.get("md_editor")
        code_editor = self.config.get("code_editor")
        mode_prefix = click.style(
            f"({self.mode})", fg="green" if self.mode == "ASK" else "red"
        )

        if not md_editor and not code_editor:
            # Just show it
            click.echo(f"\n{mode_prefix} 🤖 ", nl=False)
            if path and path.suffix == ".md":
                self._print_styled_markdown(content)
            elif content.strip().startswith("#"):  # detected MD
                self._print_styled_markdown(content)
            else:
                click.echo(content)
            return

        # Editors are configured, ask the user
        detected = self._detect_content_type(content)

        options = ["s"]
        prompt_parts = ["[s]how in terminal"]
        if md_editor:
            options.append("m")
            prompt_parts.append("[m]arkdown editor")
        if code_editor:
            options.append("c")
            prompt_parts.append("[c]ode editor")

        prompt_text = (
            f"\n{mode_prefix} 🤖 Response ready. " + ", ".join(prompt_parts) + "?"
        )

        # Decide default based on detection
        default_choice = "s"
        if detected == "md" and md_editor:
            default_choice = "m"
        elif detected == "code" and code_editor:
            default_choice = "c"

        choice = click.prompt(
            prompt_text,
            type=click.Choice(options),
            default=default_choice,
            show_choices=False,
        )

        if choice == "m":
            self._open_in_editor(content, md_editor, ".md", path)
        elif choice == "c":
            suffix = path.suffix if path else ".txt"
            self._open_in_editor(content, code_editor, suffix, path)
        else:
            click.echo(f"{mode_prefix} 🤖 ", nl=False)
            if detected == "md":
                self._print_styled_markdown(content)
            else:
                click.echo(content)

    def _detect_content_type(self, content: str) -> str:
        stripped = content.strip()

        # Obvious code block wrapper
        if (
            stripped.startswith("```")
            and stripped.endswith("```")
            and stripped.count("```") == 2
        ):
            return "code"

        # Common code keywords (Python, JS, TS, etc.)
        code_keywords = [
            "import ",
            "from ",
            "def ",
            "class ",
            "const ",
            "let ",
            "function ",
            "public ",
            "private ",
            "void ",
            "int ",
            "str ",
        ]
        if any(k in content for k in code_keywords):
            # Check if it also has significant MD markers to distinguish from MD containing code
            if not (
                stripped.startswith("# ") or "\n# " in content or "\n## " in content
            ):
                return "code"

            # If it has both code keywords and MD headers, check ratio or just return MD
            # But if headers are just '#' (could be comments), be careful.
            # MD headers usually have space: "# Title"
            has_md_headers = (
                stripped.startswith("# ") or "\n# " in content or "\n## " in content
            )
            if not has_md_headers and ("{" in content and "}" in content):
                return "code"

        # MD markers: headers with spaces, bold, lists
        if (
            stripped.startswith("# ")
            or "\n# " in content
            or "\n- " in content
            or "\n* " in content
            or "**" in content
        ):
            return "md"

        if "```" in content:
            return "code"

        return "md"

    def _open_in_editor(
        self,
        content: str,
        editor: str,
        suffix: str,
        path: Optional[pathlib.Path] = None,
    ):
        if not path:
            # Create a temporary file for raw responses
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=suffix, delete=False
                ) as f:
                    f.write(content)
                    path_str = f.name
                click.echo(f"📝 Created temporary file: {path_str}")
            except Exception as e:
                click.echo(f"❌ Failed to create temporary file: {e}")
                return
        else:
            path_str = str(path)

        try:
            subprocess.Popen([editor, path_str])
            click.echo(f"🚀 Opened in {editor}")
        except Exception as e:
            click.echo(f"❌ Failed to launch {editor}: {e}")

    def _maybe_open_editor(self, path: pathlib.Path):
        # This is now handled by _handle_response_display during agent dispatch,
        # but kept for legacy or other manual calls.
        editor = (
            self.config.get("md_editor")
            if path.suffix == ".md"
            else self.config.get("code_editor")
        )
        if editor:
            if click.confirm(
                f"🚀 Update detected. Open {path.name} in {editor}?", default=True
            ):
                try:
                    subprocess.Popen([editor, str(path)])
                except Exception as e:
                    click.echo(f"⚠️ Failed to launch {editor}: {e}")

    def _show_file(self, path: pathlib.Path):
        if not path.exists():
            click.echo(f"❌ File not found: {path}")
            return

        # Check if we should open in editor
        editor = (
            self.config.get("md_editor")
            if path.suffix == ".md"
            else self.config.get("code_editor")
        )
        if editor:
            if click.confirm(f"Open {path.name} in {editor}?", default=True):
                try:
                    import subprocess

                    subprocess.Popen([editor, str(path)])
                    return
                except Exception as e:
                    click.echo(f"⚠️ Failed to open editor: {e}")

        click.echo(
            f"\n{click.style('--- ' + path.name + ' ---', fg='cyan', bold=True)}"
        )
        content = path.read_text()
        if path.suffix == ".md":
            self._print_styled_markdown(content)
        else:
            click.echo(content)
        click.echo(
            f"{click.style('--- END OF ' + path.name + ' ---', fg='cyan', bold=True)}\n"
        )

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
