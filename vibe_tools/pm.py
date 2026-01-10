import asyncio
import collections
import pathlib
import signal
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional

import click
import google.generativeai as genai

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
    get_google_api_key,
    get_instructions_context,
    get_prompt,
    load_project_state,
    logger,
    reset_prd_state,
    run_agent,
)


class MessageQueue:
    def __init__(self):
        self.items = collections.deque()
        self.status = "IDLE"  # IDLE vs BUSY
        self.current_task: Optional[asyncio.Task] = None

    def add(self, prompt: str):
        self.items.append(prompt)

    def push(self, prompt: str):
        """Interrupts current and starts new immediately."""
        self.items.appendleft(prompt)
        if self.current_task:
            self.current_task.cancel()

    def clear(self):
        self.items.clear()

    def remove(self, index: int):
        if 0 <= index < len(self.items):
            del self.items[index]
            return True
        return False


class StreamingLLM:
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        api_key = get_google_api_key()
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not found. Run `vibe-setup api`.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    async def stream(self, prompt: str):
        """Async generator of chunks."""
        # Note: google-generativeai's generate_content is synchronous but can be wrapped or used with stream=True
        # For true async, we use the async client if available or run in executor
        loop = asyncio.get_event_loop()
        
        def _get_stream():
            return self.model.generate_content(prompt, stream=True)

        response = await loop.run_in_executor(None, _get_stream)
        for chunk in response:
            if chunk.text:
                yield chunk.text


class PMCompleter:
    def __init__(self, pm):
        self.pm = pm
        self.commands = sorted(
            [
                "/send", "/reset", "/mode", "/ask", "/agent", "/show", "/edit",
                "/history", "/files", "/add", "/list", "/ls", "/implemented",
                "/i", "/ps", "/kill", "/exit", "/conf", "/help", "/focus",
                "/f", "/switch", "/create", "/delete", "/push", "/queue"
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
            "/queue": sorted(["list", "clear", "remove"]),
        }

    def complete(self, text, state):
        if not readline: return None
        buffer = readline.get_line_buffer()

        if " " not in buffer:
            if buffer.startswith("/"):
                options = [c for c in self.commands if c.startswith(text)]
                return options[state] if state < len(options) else None
            return None

        parts = buffer.split()
        if not parts: return None

        cmd = parts[0].lower()
        if buffer.count(" ") == 1 or (buffer.count(" ") > 1 and not text):
            if cmd in self.subcommands:
                subs = self.subcommands[cmd]
                options = [s for s in subs if s.startswith(text)]
                return options[state] if state < len(options) else None

        return None


class InteractivePM:
    """Interactive Product Manager spec manager with Async LLM loop."""

    PROMPT_FILENAME = "pm_prompt.txt"

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
        self.pending_prompt: str = ""
        self.session_memory: str = ""
        self.additional_files: List[pathlib.Path] = []
        self.config = self._load_config()
        self.mode = "ASK"
        self.focused_prd: Optional[str] = None
        self.mq = MessageQueue()
        self.llm = StreamingLLM()
        self._load_session()
        self._setup_readline()
        self.loop = asyncio.get_event_loop()
        self.interrupt_event = asyncio.Event()

    def _setup_readline(self):
        if readline:
            readline.set_completer(PMCompleter(self).complete)
            readline.set_completer_delims(" \t\n;")
            if hasattr(readline, "set_auto_history"):
                readline.set_auto_history(True)
            if "libedit" in readline.__doc__:
                readline.parse_and_bind("bind ^I menu-complete")
                readline.parse_and_bind('bind "\033[Z" backward-menu-complete')
                readline.parse_and_bind("bind -e")
            else:
                readline.parse_and_bind("tab: menu-complete")
                readline.parse_and_bind(r'"\e[Z": menu-complete-backward')
                readline.parse_and_bind(r'"\e": kill-whole-line')

            history_file = VIBE_PROJECT_DIR / ".pm_history"
            if history_file.exists():
                try: readline.read_history_file(str(history_file))
                except Exception: pass
            import atexit
            atexit.register(self._save_readline_history, history_file)

    def _save_readline_history(self, history_file):
        if readline:
            try:
                readline.set_history_length(1000)
                readline.write_history_file(str(history_file))
            except Exception: pass

    def _load_config(self) -> Dict[str, Any]:
        if PM_CONFIG_FILE.exists():
            try:
                import json
                return json.loads(PM_CONFIG_FILE.read_text())
            except Exception: pass
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
                self.additional_files = [pathlib.Path(f) for f in data.get("additional_files", [])]
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

    async def run_loop(self, initial_prompt: Optional[str] = None):
        """Main interactive loop."""
        click.echo(click.style("\n📋 VIBE PRODUCT MANAGER (Async Mode)", fg="magenta", bold=True))
        click.echo("Refine your PRDs and specifications interactively.")
        click.echo("Type /help for available commands.\n")

        if initial_prompt:
            self.pending_prompt = initial_prompt
            self._save_session()
            self._show_prompt_summary()

        # Start background processor
        processor_task = asyncio.create_task(self._process_queue())

        while True:
            mode_color_code = "32" if self.mode == "ASK" else "31"
            ESC, START, END = "\x1b", "\001", "\002"
            RESET = f"{START}{ESC}[0m{END}"
            MODE_COLOR = f"{START}{ESC}[{mode_color_code}m{END}"
            BOLD = f"{START}{ESC}[1m{END}"
            focus_text = f" [{self.focused_prd}]" if self.focused_prd else ""
            status_text = f" [{click.style(self.mq.status, fg='yellow' if self.mq.status == 'BUSY' else 'green')}]"
            prompt_symbol = f"{MODE_COLOR}({self.mode}){focus_text}{status_text}{RESET} {BOLD}👤{RESET} "

            try:
                user_input = await self.loop.run_in_executor(None, lambda: input(prompt_symbol).strip())
            except EOFError: break
            except KeyboardInterrupt:
                if self.mq.status == "BUSY":
                    click.echo("\n🛑 Interrupting stream...")
                    if self.mq.current_task: self.mq.current_task.cancel()
                else:
                    click.echo("\n🛑 Use /exit to quit.")
                continue

            if not user_input: continue

            if user_input.startswith("/"):
                if await self._handle_slash_command(user_input):
                    break
                continue

            if self.pending_prompt: self.pending_prompt += f"\n{user_input}"
            else: self.pending_prompt = user_input

            self._save_session()
            self._show_prompt_summary()

        processor_task.cancel()
        try: await processor_task
        except asyncio.CancelledError: pass

    async def _process_queue(self):
        while True:
            if not self.mq.items:
                self.mq.status = "IDLE"
                await asyncio.sleep(0.1)
                continue

            self.mq.status = "BUSY"
            prompt_content = self.mq.items.popleft()
            
            self.mq.current_task = asyncio.create_task(self._execute_llm_task(prompt_content))
            try:
                await self.mq.current_task
            except asyncio.CancelledError:
                click.echo(click.style("\n⚠️ Task interrupted.", fg="yellow"))
            finally:
                self.mq.current_task = None
                self.mq.status = "IDLE"

    async def _execute_llm_task(self, query: str):
        full_prompt = self._build_prompt_with_query(query)
        
        mode_prefix = click.style(f"({self.mode})", fg="green" if self.mode == "ASK" else "red")
        click.echo(f"\n{mode_prefix} 🤖 ", nl=False)
        
        full_response = ""
        try:
            async for chunk in self.llm.stream(full_prompt):
                click.echo(chunk, nl=False)
                full_response += chunk
            click.echo("\n")
        except asyncio.CancelledError:
            click.echo(click.style("\n[INTERRUPTED]", fg="red"))
            return

        self.history.append({"role": "user", "content": query})
        
        # Handle FILE_UPDATE if in AGENT mode
        if self.mode == "AGENT" and "FILE_UPDATE:" in full_response:
            self._handle_file_updates(full_response)
        
        self.history.append({"role": "pm", "content": full_response})
        self._save_session()

    def _handle_file_updates(self, output: str):
        if "FILE_UPDATE:" not in output: return
        parts = output.split("FILE_UPDATE:")
        for part in parts[1:]:
            lines = part.strip().splitlines()
            if not lines: continue
            filename = lines[0].strip()
            if filename.startswith("specs/"): filename = filename[6:]
            content = "\n".join(lines[1:]).strip()

            state = load_project_state()
            completed = state.get("completed_prds", [])
            if filename in completed or filename.replace(".md", "") in completed:
                click.echo(click.style(f"🚫 BLOCKED: '{filename}' is implemented.", fg="red", bold=True))
            else:
                target_path = SPECS_DIR / filename
                ensure_dir(SPECS_DIR)
                target_path.write_text(content)
                click.echo(click.style(f"✅ Updated {target_path}", fg="green"))

    def _show_prompt_summary(self):
        if not self.pending_prompt: return
        lines = self.pending_prompt.splitlines()
        count = len(lines)
        click.echo(click.style(f"\n📝 Pending Prompt ({count} lines):", fg="yellow", bold=True))
        for line in lines[:5]: click.echo(f"  {line}")
        if count > 5: click.echo(f"  ... (+{count-5} more lines)")
        click.echo(click.style("Type /s to send, /push to prioritize, or keep typing.\n", dim=True))

    async def _handle_slash_command(self, command_str: str) -> bool:
        parts = command_str.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ["/s", "/send"]:
            if not self.pending_prompt:
                click.echo("❌ Prompt is empty.")
            else:
                self.mq.add(self.pending_prompt)
                self.pending_prompt = ""
                click.echo("✅ Added to queue.")
        elif cmd == "/push":
            if not self.pending_prompt:
                click.echo("❌ Prompt is empty.")
            else:
                self.mq.push(self.pending_prompt)
                self.pending_prompt = ""
                click.echo("🚀 Pushing to front and interrupting current...")
        elif cmd == "/queue":
            self._handle_queue_command(args)
        elif cmd in ["/r", "/reset"]:
            self.pending_prompt = ""
            self.mq.clear()
            click.echo("✅ Pending prompt and queue cleared.")
        elif cmd in ["/q", "/exit", "/quit"]:
            return True
        elif cmd in ["/h", "/help"]:
            self._show_help()
        elif cmd in ["/f", "/focus"]:
            self._handle_focus_command(args)
        elif cmd in ["/m", "/mode"]:
            self._handle_mode_command(args)
        elif cmd == "/ask": self._handle_mode_command("ask")
        elif cmd == "/agent": self._handle_mode_command("agent")
        elif cmd == "/ls" or cmd == "/list":
            if args == "memory": self._list_memory()
            else: self._list_specs()
        elif cmd == "/show":
            self._handle_show_command(args)
        elif cmd == "/create":
            self._handle_create_command(args)
        elif cmd == "/delete":
            self._handle_delete_command(args)
        elif cmd == "/edit":
            self._handle_edit_command(args)
        elif cmd == "/add":
            if args:
                self.session_memory += f"\n{args}" if self.session_memory else args
                click.echo("✅ Added to session memory.")
            else: click.echo("❌ Usage: /add <text>")
        elif cmd == "/i" or cmd == "/implemented":
            self._handle_implemented_command()
        elif cmd == "/ps":
            self._handle_ps_command()
        elif cmd == "/kill":
            self._handle_kill_command(args)
        elif cmd == "/conf":
            self._handle_conf_command_internal(args)
        else:
            click.echo(f"❌ Unknown command: {cmd}")
        
        self._save_session()
        return False

    def _handle_queue_command(self, args):
        parts = args.split()
        sub = parts[0] if parts else "list"
        if sub == "list":
            if not self.mq.items: click.echo("Queue is empty.")
            for i, item in enumerate(self.mq.items):
                click.echo(f"[{i}] {item[:50]}...")
        elif sub == "clear":
            self.mq.clear()
            click.echo("Queue cleared.")
        elif sub == "remove":
            if len(parts) > 1 and self.mq.remove(int(parts[1])):
                click.echo(f"Removed item {parts[1]}")
            else: click.echo("Invalid index.")

    def _show_help(self):
        click.echo("\nAvailable commands:")
        click.echo("  /send, /s        - Add pending prompt to queue")
        click.echo("  /push            - Interrupt current and start pending prompt immediately")
        click.echo("  /queue [list|clear|remove <idx>] - Manage message queue")
        click.echo("  /reset, /r       - Clear pending prompt and queue")
        click.echo("  /mode, /m [ASK|AGENT] - Switch between modes")
        click.echo("  /focus, /f <name|idx> - Focus on a specific PRD")
        click.echo("  /list, /ls [memory|specs] - List items")
        click.echo("  /exit, /q        - Exit session")

    def _handle_focus_command(self, args):
        if not args:
            self.focused_prd = None
            click.echo("✅ Focus cleared.")
            return
        files = sorted(SPECS_DIR.glob("*.md"))
        target = None
        try:
            idx = int(args)
            if 0 <= idx < len(files): target = files[idx]
        except ValueError:
            for f in files:
                if args.lower() in f.name.lower():
                    target = f
                    break
        if target:
            self.focused_prd = target.name
            click.echo(f"✅ Focused on: {click.style(target.name, fg='cyan', bold=True)}")
        else: click.echo(f"❌ Not found: {args}")

    def _handle_mode_command(self, new_mode):
        if not new_mode: self.mode = "AGENT" if self.mode == "ASK" else "ASK"
        elif new_mode.upper() in ["ASK", "AGENT"]: self.mode = new_mode.upper()
        else: click.echo("❌ Usage: /mode [ASK|AGENT]")
        color = "green" if self.mode == "ASK" else "red"
        click.echo(f"✅ Mode: {click.style(self.mode, fg=color)}")

    def _handle_show_command(self, args):
        if not args or args.lower() == "specs": self._list_specs()
        else:
            p = SPECS_DIR / args
            if not p.suffix: p = p.with_suffix(".md")
            if p.exists():
                click.echo(f"\n--- {p.name} ---\n{p.read_text()}\n--- END ---")
            else: click.echo(f"❌ Not found: {args}")

    def _handle_create_command(self, args):
        if not args: return click.echo("❌ Usage: /create <name>")
        name = args if args.endswith(".md") else args + ".md"
        path = SPECS_DIR / name
        if path.exists(): return click.echo("❌ Exists.")
        ensure_dir(SPECS_DIR)
        path.write_text(f"# {args.title()}\n\n## Summary\n")
        self.focused_prd = name
        click.echo(f"✅ Created: {name}")

    def _handle_delete_command(self, args):
        if not args: return click.echo("❌ Usage: /delete <idx|name>")
        files = sorted(SPECS_DIR.glob("*.md"))
        target = None
        try:
            idx = int(args)
            if 0 <= idx < len(files): target = files[idx]
        except ValueError:
            p = SPECS_DIR / args
            if not p.suffix: p = p.with_suffix(".md")
            if p.exists(): target = p
        if target and click.confirm(f"Delete {target.name}?"):
            target.unlink()
            if self.focused_prd == target.name: self.focused_prd = None
            click.echo("✅ Deleted.")

    def _handle_edit_command(self, path_str):
        if not path_str: return click.echo("❌ Usage: /edit <path>")
        p = pathlib.Path(path_str)
        editor = self.config.get("code_editor") or self.config.get("md_editor")
        if not editor: return click.echo("❌ No editor configured.")
        subprocess.Popen([editor, str(p)])

    def _handle_implemented_command(self):
        state = load_project_state()
        completed = state.get("completed_prds", [])
        if not completed: return click.echo("None.")
        for i, p in enumerate(reversed(completed)): click.echo(f"{i+1}. {p}")

    def _handle_ps_command(self):
        procs = get_agent_processes()
        if not procs: click.echo("None.")
        else:
            for p in procs: click.echo(f"{p['pid']} {p['target']} {p['command']}")

    def _handle_kill_command(self, args):
        if not args or "all" in args:
            if click.confirm("Kill all?"):
                cleanup_stale_processes()
                click.echo("✅ Killed.")

    def _handle_conf_command_internal(self, args):
        parts = args.split(maxsplit=1)
        if len(parts) < 2: return click.echo("❌ Usage: /conf [md|code] <cmd>")
        target, cmd = parts
        if target in ["md", "code"]:
            self.config[f"{target}_editor"] = cmd
            self._save_config()
            click.echo("✅ Saved.")

    def _list_specs(self):
        files = sorted(SPECS_DIR.glob("*.md"))
        state = load_project_state()
        completed = state.get("completed_prds", [])
        click.echo("\n--- specs/ ---")
        for i, f in enumerate(files):
            style = {"fg": "cyan", "bold": True} if self.focused_prd == f.name else {"fg": "white"}
            status = click.style(" [DONE]", fg="green") if f.stem in completed else ""
            click.echo(f"[{i}] {click.style(f.name, **style)}{status}")

    def _list_memory(self):
        click.echo(f"\nMemory: {self.session_memory[:200]}...")
        click.echo(f"Files: {[str(f) for f in self.additional_files]}")

    def _build_prompt_with_query(self, query: str) -> str:
        try: template = get_prompt(self.PROMPT_FILENAME)
        except: return query
        
        specs_context = ""
        primary_focus = ""
        if SPECS_DIR.exists():
            for f in sorted(SPECS_DIR.glob("*.md")):
                if self.focused_prd == f.name:
                    primary_focus = f"PRIMARY FOCUS: {f.name}\n\n{f.read_text()}"
                else: specs_context += f"- {f.name}\n"
        
        state = load_project_state()
        impl = ", ".join(state.get("completed_prds", []))
        history = "\n".join([f"{h['role']}: {h['content'][:200]}" for h in self.history])
        
        mode_instr = "ASK mode: No file updates." if self.mode == "ASK" else "AGENT mode: Can update files using FILE_UPDATE: <filename>"
        
        return template.format(
            mode=self.mode,
            mode_instructions=mode_instr,
            primary_focus=primary_focus or "None",
            specs_content=specs_context or "None",
            implemented_prds=impl or "None",
            instructions=get_instructions_context(),
            user_memory=self.session_memory,
            history=history,
            query=query
        )
