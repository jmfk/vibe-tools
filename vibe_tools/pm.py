import pathlib
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

import click

try:
    import readline
except ImportError:
    readline = None  # type: ignore

from vibe_tools.utils import (
    PM_CONFIG_FILE,
    PM_SESSION_FILE,
    SPECS_DIR,
    VIBE_PROJECT_DIR,
    cleanup_stale_processes,
    ensure_dir,
    get_agent_command,
    get_agent_processes,
    get_instructions_context,
    get_prompt,
    load_project_state,
    logger,
    run_agent,
)


class PMCompleter:
    def __init__(self, pm):
        self.pm = pm
        # Sort commands so cycling order is predictable (alphabetical)
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
                "/ls",
                "/ps",
                "/kill",
                "/exit",
                "/conf",
                "/help",
                "/focus",
                "/f",
                "/switch",
                "/create",
                "/delete",
            ]
        )
        self.subcommands = {
            "/files": sorted(["list", "add", "remove"]),
            "/history": sorted(["list", "view", "remove"]),
            "/list": sorted(["memory", "specs"]),
            "/ls": sorted(["memory", "specs"]),
            "/conf": sorted(["md", "code"]),
            "/show": sorted(["specs"]),
            "/kill": sorted(["all"]),
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
        if buffer.count(" ") == 1 or (buffer.count(" ") > 1 and not text):
            if cmd in self.subcommands:
                subs = self.subcommands[cmd]
                options = [s for s in subs if s.startswith(text)]
                return options[state] if state < len(options) else None

        return None


class InteractivePM:
    """Interactive Product Manager spec manager."""

    PROMPT_FILENAME = "pm_prompt.txt"

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
        self.focused_prd: Optional[str] = None
        self._load_session()
        self._setup_readline()

    def _setup_readline(self):
        if readline:
            readline.set_completer(PMCompleter(self).complete)
            readline.set_completer_delims(" \t\n;")

            if hasattr(readline, "set_auto_history"):
                readline.set_auto_history(True)

            if "libedit" in readline.__doc__:  # macOS compatibility
                readline.parse_and_bind("bind ^I menu-complete")
                readline.parse_and_bind('bind "\033[Z" backward-menu-complete')
                readline.parse_and_bind("bind -e")
            else:
                readline.parse_and_bind("tab: menu-complete")
                readline.parse_and_bind(r'"\e[Z": menu-complete-backward')
                readline.parse_and_bind(r'"\e": kill-whole-line')

            history_file = VIBE_PROJECT_DIR / ".pm_history"
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
        if PM_CONFIG_FILE.exists():
            try:
                import json
                return json.loads(PM_CONFIG_FILE.read_text())
            except Exception:
                pass
        return {"md_editor": None, "code_editor": None}

    def _save_config(self):
        import json
        ensure_dir(PM_CONFIG_FILE.parent)
        PM_CONFIG_FILE.write_text(json.dumps(self.config, indent=2))

    def _load_session(self):
        if PM_SESSION_FILE.exists():
            try:
                import json
                data = json.loads(PM_SESSION_FILE.read_text())
                self.history = data.get("history", [])
                self.pending_prompt = data.get("pending_prompt", "")
                self.session_memory = data.get("session_memory", "")
                self.additional_files = [
                    pathlib.Path(f) for f in data.get("additional_files", [])
                ]
                self.mode = data.get("mode", "ASK")
                self.focused_prd = data.get("focused_prd")
            except Exception as e:
                logger.debug(f"Error loading PM session: {e}")

    def _save_session(self):
        import json
        ensure_dir(PM_SESSION_FILE.parent)
        data = {
            "history": self.history,
            "pending_prompt": self.pending_prompt,
            "session_memory": self.session_memory,
            "additional_files": [str(f) for f in self.additional_files],
            "mode": self.mode,
            "focused_prd": self.focused_prd,
        }
        PM_SESSION_FILE.write_text(json.dumps(data, indent=2))

    def run_loop(self, initial_prompt: Optional[str] = None):
        """Main interactive loop."""
        click.echo(click.style("\n📋 VIBE PRODUCT MANAGER", fg="magenta", bold=True))
        click.echo("Refine your PRDs and specifications interactively.")
        click.echo("Type /help for available commands.\n")

        if initial_prompt:
            self.pending_prompt = initial_prompt
            self._save_session()
            self._show_prompt_summary()

        while True:
            mode_color_code = "32" if self.mode == "ASK" else "31"
            ESC = "\x1b"
            START = "\001"
            END = "\002"
            RESET = f"{START}{ESC}[0m{END}"
            MODE_COLOR = f"{START}{ESC}[{mode_color_code}m{END}"
            BOLD = f"{START}{ESC}[1m{END}"
            focus_text = f" [{self.focused_prd}]" if self.focused_prd else ""
            prompt_symbol = f"{MODE_COLOR}({self.mode}){focus_text}{RESET} {BOLD}👤{RESET} "

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
        click.echo(click.style(f"\n📝 Pending Prompt ({count} lines):", fg="yellow", bold=True))
        for line in lines[:5]:
            click.echo(f"  {line}")
        if count > 5:
            click.echo(f"  ... (+{count-5} more lines)")
        click.echo(click.style("Type /s to send, /r to reset, or keep typing to add more.\n", dim=True))

    def _handle_slash_command(self, command_str: str) -> bool:
        parts = command_str.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/s": cmd = "/send"
        elif cmd == "/r": cmd = "/reset"
        elif cmd == "/q": cmd = "/exit"
        elif cmd == "/h": cmd = "/help"
        elif cmd == "/c":
            if readline:
                readline.clear_history()
                click.echo("✅ Shell history cleared.")
            return False
        elif cmd == "/l":
            cmd = "/list"
            args = "memory"
        elif cmd == "/ls":
            cmd = "/list"
            if not args: args = "specs"
        elif cmd == "/f":
            if not args:
                cmd = "/focus"
            elif args in ["list", "add", "remove"]:
                cmd = "/files"
            else:
                cmd = "/focus"
        elif cmd == "/a": cmd = "/add"
        elif cmd == "/switch": cmd = "/focus"

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
            self.focused_prd = None
            self._save_session()
            click.echo("✅ Session memory, pending prompt, and focus reset.")
        elif cmd == "/focus":
            self._handle_focus_command(args)
            self._save_session()
        elif cmd == "/create":
            self._handle_create_command(args)
            self._save_session()
        elif cmd == "/delete":
            self._handle_delete_command(args)
            self._save_session()
        elif cmd == "/add":
            if args:
                if self.session_memory: self.session_memory += f"\n{args}"
                else: self.session_memory = args
                self._save_session()
                lines = self.session_memory.splitlines()
                count = len(lines)
                click.echo(click.style(f"✅ Session Memory Updated ({count} lines):", fg="green", bold=True))
                for line in lines[:5]: click.echo(f"  {line}")
                if count > 5: click.echo(f"  ... (+{count-5} more lines)")
            else:
                click.echo("❌ Usage: /add <text>")
        elif cmd == "/show":
            if args.lower() in ["specs", "spec"] or not args:
                self._list_specs()
            elif args:
                p = SPECS_DIR / args
                if not p.suffix: p = p.with_suffix(".md")
                self._show_file(p)
            else:
                click.echo("❌ Usage: /show [specs|<filename>]")
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
            if args == "memory": self._list_memory()
            elif args == "specs" or not args: self._list_specs()
            else: click.echo("❌ Usage: /list [memory|specs]")
        elif cmd == "/ps":
            processes = get_agent_processes()
            if not processes:
                click.echo("No active agent processes found.")
            else:
                click.echo(f"{'PID':<10} {'TARGET':<20} {'COMMAND'}")
                click.echo("-" * 60)
                for p in processes:
                    click.echo(f"{p['pid']:<10} {p['target']:<20} {p['command']}")
        elif cmd == "/kill":
            processes = get_agent_processes()
            if not processes:
                click.echo("No active agent processes found.")
            else:
                if not args or "all" in args.lower():
                    click.echo("Active agent processes:")
                    for p in processes:
                        click.echo(f"  - {p['pid']}: {p['command']}")

                    if click.confirm("\nAre you sure you want to kill all these processes?", default=False):
                        killed = cleanup_stale_processes()
                        if killed:
                            click.echo(f"✅ Killed processes for: {', '.join(killed)}")
                        else:
                            click.echo("No processes were killed.")
                    else:
                        click.echo("Aborted.")
                else:
                    click.echo("❌ Usage: /kill [all]")
        elif cmd == "/conf":
            sub_parts = args.split(" ", 1)
            target = sub_parts[0] if sub_parts else ""
            editor = sub_parts[1] if len(sub_parts) > 1 else ""
            self._handle_conf_command(target, editor)
        elif cmd == "/mode" or cmd == "/m":
            self._handle_mode_command(args)
        elif cmd == "/ask": self._handle_mode_command("ask")
        elif cmd == "/agent": self._handle_mode_command("agent")
        elif cmd == "/exit" or cmd == "/quit": return True
        else: click.echo(f"❌ Unknown command: {cmd}. Type /help for options.")

        return False

    def _show_help(self):
        click.echo("\nAvailable commands:")
        click.echo("  /send, /s        - Dispatch current prompt to PM")
        click.echo("  /reset, /r       - Clear the current pending prompt")
        click.echo("  /add, /a <text>  - Add text to the persistent session memory")
        click.echo("  /mode, /m [ASK|AGENT] - Switch between modes")
        click.echo("  /ask, /agent     - Shortcut to switch modes")
        click.echo("  /focus, /f, /switch <name|idx> - Focus on a specific PRD (empty to clear)")
        click.echo("  /create <name>   - Create a new PRD file in specs/")
        click.echo("  /delete <name|idx> - Delete a PRD file from specs/")
        click.echo("  /show [specs|file] - Display current specs or a specific file")
        click.echo("  /edit [path]     - Open file in code editor")
        click.echo("  /history [list|view <idx>|remove <idx>] - Manage interaction history")
        click.echo("  /files, /f [list|add <path>|remove <path>] - Manage additional context files")
        click.echo("  /ps              - List active agent processes")
        click.echo("  /kill [all]      - Kill active agent processes")
        click.echo("  /list [memory|specs], /ls, /l - List pending items or PRDs")
        click.echo("  /conf [md|code] <editor_cmd> - Configure preferred editor")
        click.echo("  /help, /h        - Show this help message")
        click.echo("  /c               - Clear the shell prompt history")
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
        if not new_mode: self.mode = "AGENT" if self.mode == "ASK" else "ASK"
        elif new_mode.upper() in ["ASK", "AGENT"]: self.mode = new_mode.upper()
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
            subprocess.Popen([editor, str(p)])
            click.echo(f"🚀 Opening {p} in {editor}...")
        except Exception as e:
            click.echo(f"❌ Failed to launch {editor}: {e}")

    def _handle_history_command(self, sub_cmd, args):
        if not sub_cmd or sub_cmd == "list":
            if not self.history: click.echo("📜 History is empty.")
            for i, h in enumerate(self.history):
                click.echo(f"[{i}] {h['role'].upper()}: {h['content'][:100]}...")
        elif sub_cmd == "view":
            try:
                idx = int(args)
                h = self.history[idx]
                click.echo(f"\n--- History [{idx}] ({h['role'].upper()}) ---")
                click.echo(h["content"])
            except (ValueError, IndexError): click.echo("❌ Invalid history index.")
        elif sub_cmd == "remove":
            try:
                idx = int(args)
                removed = self.history.pop(idx)
                click.echo(f"✅ Removed history item [{idx}]: {removed['role']}")
            except (ValueError, IndexError): click.echo("❌ Invalid history index.")

    def _handle_files_command(self, sub_cmd, args):
        if not sub_cmd or sub_cmd == "list":
            if not self.additional_files: click.echo("📁 No additional files added.")
            for f in self.additional_files: click.echo(f"- {f}")
        elif sub_cmd == "add":
            p = pathlib.Path(args)
            if p.exists() and p.is_file():
                if p not in self.additional_files:
                    self.additional_files.append(p)
                    click.echo(f"✅ Added file: {p}")
                else: click.echo("ℹ️ File already in context.")
            else: click.echo(f"❌ File not found: {args}")
        elif sub_cmd == "remove":
            p = pathlib.Path(args)
            if p in self.additional_files:
                self.additional_files.remove(p)
                click.echo(f"✅ Removed file: {p}")
            else: click.echo(f"❌ File not in context: {args}")

    def _list_memory(self):
        click.echo("\n--- Session Status ---")
        click.echo(click.style("Session Memory (Persistent - added via /a):", bold=True))
        if self.session_memory:
            lines = self.session_memory.splitlines()
            for line in lines[:5]: click.echo(f"  {line}")
            if len(lines) > 5: click.echo(f"  ... (+{len(lines)-5} more lines)")
            click.echo(f"  ({len(lines)} lines total)")
        else: click.echo("  (empty)")

        click.echo(click.style("\nPending Prompt (Current task):", bold=True))
        if self.pending_prompt:
            lines = self.pending_prompt.splitlines()
            for line in lines[:5]: click.echo(f"  {line}")
            if len(lines) > 5: click.echo(f"  ... (+{len(lines)-5} more lines)")
            click.echo(f"  ({len(lines)} lines total)")
        else: click.echo("  (empty)")

        click.echo(click.style("\nIncluded Files:", bold=True))
        if not self.additional_files: click.echo("  (none)")
        for f in self.additional_files: click.echo(f"  - {f}")

        click.echo(click.style("\nHistory Summary (Sent Prompts):", bold=True))
        sent_prompts = [h for h in self.history if h["role"] == "user"]
        if not sent_prompts: click.echo("  (none)")
        else:
            for i, h in enumerate(sent_prompts):
                title = h["content"].splitlines()[0][:60]
                click.echo(f"  [{i}] {title}...")

        prompt = self._build_prompt()
        size_kb = len(prompt) / 1024
        click.echo(f"\n📦 Total payload: {size_kb:.2f} KB")
        click.echo("----------------------")

    def _list_specs(self):
        if not SPECS_DIR.exists():
            click.echo("❌ specs/ directory not found.")
            return
        click.echo("\n--- Files in specs/ ---")
        state = load_project_state()
        completed = state.get("completed_prds", [])
        files = sorted(SPECS_DIR.glob("*.md"))
        for i, f in enumerate(files):
            status = ""
            if f.stem in completed or f.name in completed:
                status = click.style(" [IMPLEMENTED]", fg="green")
            
            prefix = f"[{i}] "
            name_style = {"fg": "white"}
            if self.focused_prd == f.name:
                name_style = {"fg": "cyan", "bold": True}
                prefix = click.style(prefix, fg="cyan", bold=True)
            
            click.echo(f"{prefix}{click.style(f.name, **name_style)}{status}")
        click.echo("----------------------")

    def _handle_focus_command(self, args):
        if not args:
            self.focused_prd = None
            click.echo("✅ Focus cleared.")
            return

        files = sorted(SPECS_DIR.glob("*.md"))
        target = None

        # Try index based selection
        try:
            idx = int(args)
            if 0 <= idx < len(files):
                target = files[idx]
        except ValueError:
            # Try fuzzy matching or exact match
            for f in files:
                if args.lower() in f.name.lower():
                    target = f
                    break
        
        if target:
            self.focused_prd = target.name
            click.echo(f"✅ Focused on: {click.style(target.name, fg='cyan', bold=True)}")
        else:
            click.echo(f"❌ Could not find PRD matching: {args}")

    def _handle_create_command(self, args):
        if not args:
            click.echo("❌ Usage: /create <filename>")
            return
        
        filename = args
        if not filename.endswith(".md"):
            filename += ".md"
        
        target_path = SPECS_DIR / filename
        if target_path.exists():
            click.echo(f"❌ File already exists: {target_path}")
            return
        
        ensure_dir(SPECS_DIR)
        template = f"# {args.replace('_', ' ').title()}\n\n## Summary\n\n## Requirements\n"
        target_path.write_text(template)
        self.focused_prd = filename
        click.echo(f"✅ Created and focused: {target_path}")

    def _handle_delete_command(self, args):
        if not args:
            click.echo("❌ Usage: /delete <filename|idx>")
            return
        
        files = sorted(SPECS_DIR.glob("*.md"))
        target = None

        try:
            idx = int(args)
            if 0 <= idx < len(files):
                target = files[idx]
        except ValueError:
            target_path = SPECS_DIR / args
            if not target_path.suffix:
                target_path = target_path.with_suffix(".md")
            if target_path.exists():
                target = target_path

        if not target or not target.exists():
            click.echo(f"❌ File not found: {args}")
            return
        
        if click.confirm(f"Are you sure you want to delete {target.name}?", default=False):
            target.unlink()
            if self.focused_prd == target.name:
                self.focused_prd = None
            click.echo(f"✅ Deleted {target.name}")
        else:
            click.echo("Aborted.")

    def _build_prompt(self) -> str:
        try:
            prompt_template = get_prompt(self.PROMPT_FILENAME)
        except FileNotFoundError as e:
            raise click.ClickException(str(e))

        # Build specs context
        specs_context = ""
        primary_focus = ""
        if SPECS_DIR.exists():
            other_specs = []
            for f in sorted(SPECS_DIR.glob("*.md")):
                try:
                    if self.focused_prd == f.name:
                        content = f.read_text()
                        primary_focus = f"PRIMARY FOCUS PRD (Update this if needed):\nFILE: specs/{f.name}\n\n{content}"
                    else:
                        other_specs.append(f.name)
                except Exception as e:
                    logger.warning(f"Error reading {f}: {e}")
            
            if other_specs:
                specs_context = "OTHER AVAILABLE PRDs (for context only):\n" + "\n".join([f"- {name}" for name in other_specs])
        else:
            specs_context = "No specs/ directory found."

        if not primary_focus:
            primary_focus = "No specific PRD is currently focused. You may suggest creating a new one or choose one from the available specs."

        state = load_project_state()
        implemented_prds = state.get("completed_prds", [])
        implemented_text = ", ".join(implemented_prds) if implemented_prds else "None"

        history_text = "\n".join([f"{h['role'].upper()}: {h['content']}" for h in self.history])

        files_context = ""
        for f in self.additional_files:
            try: files_context += f"\n\n--- FILE: {f} ---\n{f.read_text()}\n--- END FILE: {f} ---"
            except Exception as e: click.echo(f"⚠️ Error reading {f}: {e}")

        instructions = get_instructions_context()

        mode_instructions = ""
        if self.mode == "ASK":
            mode_instructions = "CURRENT MODE: ASK. Do NOT generate any FILE_UPDATE commands. Only provide analysis, answers, or guidance."
        else:
            default_file = f"\nIf you are proposing changes, focus on the PRIMARY FOCUS file by default: 'FILE_UPDATE: {self.focused_prd}'" if self.focused_prd else ""
            mode_instructions = f"CURRENT MODE: AGENT. You ARE authorized to create or update files in 'specs/' using the 'FILE_UPDATE: <filename>' tag.{default_file}"

        user_memory_text = ""
        if self.session_memory:
            user_memory_text = f"SESSION MEMORY (Persistent Instructions):\n{self.session_memory}"

        return prompt_template.format(
            mode=self.mode,
            mode_instructions=mode_instructions,
            primary_focus=primary_focus,
            specs_content=specs_context,
            implemented_prds=implemented_text,
            instructions=instructions,
            user_memory=user_memory_text,
            history=history_text + files_context,
            query=self.pending_prompt,
        )

    def _dispatch_agent(self):
        prompt = self._build_prompt()
        query = self.pending_prompt

        click.echo("⏳ PM is thinking... (Ctrl-C to cancel)")
        command = get_agent_command(self.agent_type, prompt)

        if self.stream:
            mode_prefix = click.style(f"({self.mode})", fg="green" if self.mode == "ASK" else "red")
            click.echo(f"{mode_prefix} 🤖 ", nl=False)

        try:
            output, exit_code = run_agent(command, stream=self.stream)
        except KeyboardInterrupt:
            click.echo("\n🛑 Agent cancelled.")
            return

        if exit_code != 0:
            click.echo("❌ PM failed to respond.")
            return

        self.history.append({"role": "user", "content": query})
        self.pending_prompt = ""

        if "FILE_UPDATE:" in output:
            parts = output.split("FILE_UPDATE:", 1)
            thinking = parts[0].strip()
            update_part = parts[1].strip()

            lines = update_part.splitlines()
            if not lines:
                click.echo("❌ Invalid FILE_UPDATE tag.")
                return
            header = lines[0].strip()
            content = "\n".join(lines[1:]).strip()

            if thinking and not self.stream:
                mode_prefix = click.style(f"({self.mode})", fg="green" if self.mode == "ASK" else "red")
                click.echo(f"\n{mode_prefix} 🤖 Thinking: {thinking}")

            # Check if implemented
            filename = header
            if filename.startswith("specs/"): filename = filename[6:]

            state = load_project_state()
            completed = state.get("completed_prds", [])
            if filename in completed or filename.replace(".md", "") in completed:
                click.echo(click.style(f"🚫 BLOCKED: '{filename}' has already been implemented and cannot be edited. Please clone it to a new file instead.", fg="red", bold=True))
                self.history.append({"role": "pm", "content": f"Blocked attempt to update implemented file: {filename}"})
            else:
                target_path = SPECS_DIR / filename
                ensure_dir(SPECS_DIR)
                target_path.write_text(content)
                click.echo(f"✅ Updated {target_path}")
                self.history.append({"role": "pm", "content": f"Updated {target_path}"})
                self._handle_response_display(content, target_path)
        else:
            self.history.append({"role": "pm", "content": output})
            self._handle_response_display(output)

        self._save_session()
        click.echo("")

    def _handle_response_display(self, content: str, path: Optional[pathlib.Path] = None):
        if self.stream: return
        md_editor = self.config.get("md_editor")
        code_editor = self.config.get("code_editor")
        mode_prefix = click.style(f"({self.mode})", fg="green" if self.mode == "ASK" else "red")
        detected = self._detect_content_type(content)

        click.echo(f"\n{mode_prefix} 🤖 ", nl=False)
        if path and path.suffix == ".md": self._print_styled_markdown(content)
        elif detected == "md": self._print_styled_markdown(content)
        else: click.echo(content)

        if md_editor or code_editor:
            options = ["n"]
            prompt_parts = ["[n]o"]
            if md_editor:
                options.append("m")
                prompt_parts.append("[m]arkdown editor")
            if code_editor:
                options.append("c")
                prompt_parts.append("[c]ode editor")

            prompt_text = "🚀 Open in " + ", ".join(prompt_parts) + "?"
            default_choice = "n"
            if detected == "md" and md_editor: default_choice = "m"
            elif detected == "code" and code_editor: default_choice = "c"

            choice = click.prompt(prompt_text, type=click.Choice(options), default=default_choice, show_choices=False)
            if choice == "m": self._open_in_editor(content, md_editor, ".md", path)
            elif choice == "c":
                suffix = path.suffix if path else ".txt"
                self._open_in_editor(content, code_editor, suffix, path)

    def _detect_content_type(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```") and stripped.count("```") == 2: return "code"
        code_keywords = ["import ", "from ", "def ", "class ", "const ", "let ", "function ", "public ", "private ", "void ", "int ", "str "]
        if any(k in content for k in code_keywords):
            if not (stripped.startswith("# ") or "\n# " in content or "\n## " in content): return "code"
            has_md_headers = stripped.startswith("# ") or "\n# " in content or "\n## " in content
            if not has_md_headers and ("{" in content and "}" in content): return "code"
        if stripped.startswith("# ") or "\n# " in content or "\n- " in content or "\n* " in content or "**" in content: return "md"
        if "```" in content: return "code"
        return "md"

    def _open_in_editor(self, content: str, editor: str, suffix: str, path: Optional[pathlib.Path] = None):
        if not path:
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
                    f.write(content)
                    path_str = f.name
                click.echo(f"📝 Created temporary file: {path_str}")
            except Exception as e:
                click.echo(f"❌ Failed to create temporary file: {e}")
                return
        else: path_str = str(path)
        try:
            subprocess.Popen([editor, path_str])
            click.echo(f"🚀 Opened in {editor}")
        except Exception as e: click.echo(f"❌ Failed to launch {editor}: {e}")

    def _show_file(self, path: pathlib.Path):
        if not path.exists():
            click.echo(f"❌ File not found: {path}")
            return
        editor = self.config.get("md_editor") if path.suffix == ".md" else self.config.get("code_editor")
        if editor:
            if click.confirm(f"Open {path.name} in {editor}?", default=True):
                try:
                    subprocess.Popen([editor, str(path)])
                    return
                except Exception as e: click.echo(f"⚠️ Failed to open editor: {e}")
        click.echo(f"\n{click.style('--- ' + path.name + ' ---', fg='magenta', bold=True)}")
        content = path.read_text()
        if path.suffix == ".md": self._print_styled_markdown(content)
        else: click.echo(content)
        click.echo(f"{click.style('--- END OF ' + path.name + ' ---', fg='magenta', bold=True)}\n")

    def _print_styled_markdown(self, content: str):
        lines = content.splitlines()
        for line in lines:
            if line.startswith("#"): click.echo(click.style(line.upper(), fg="magenta", bold=True))
            elif line.startswith("- ") or line.startswith("* "): click.echo(click.style(line, fg="yellow"))
            elif "`" in line: click.echo(click.style(line, fg="white"))
            else: click.echo(line)
        click.echo("")

