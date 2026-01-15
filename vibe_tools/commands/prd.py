import click
import pathlib
from typing import Optional, List

from vibe_tools.utils import (
    PRODUCT_BACKLOG_DIR,
    PRODUCT_IN_PROGRESS_DIR,
    PRODUCT_HISTORY_DIR,
    PRODUCT_DIR,
    PLANNING_INBOX_DIR,
    PRODUCT_NEXT_DIR,
    PLANNING_REJECTED_DIR,
    ensure_dir,
)
from vibe_tools.pm import InteractivePM
from vibe_tools.prds import load_prd, PRD

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import ANSI
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.style import Style

console = Console()


def _get_all_prds() -> List[PRD]:
    all_files = list(PRODUCT_DIR.rglob("*.md"))
    prds = []
    for f in all_files:
        try:
            prds.append(load_prd(f))
        except Exception:
            continue
    return prds


def _check_and_suggest_dependencies(
    prd: PRD, all_prds: List[PRD], completed: List[str]
):
    deps = prd.depends_on or []
    missing = [d for d in deps if d not in completed]
    if not missing:
        return True

    console.print(
        f"\n[yellow]⚠️  PRD {prd.id} depends on: {', '.join(missing)}[/yellow]"
    )

    for dep_id in missing:
        dep_prd = next((p for p in all_prds if p.id == dep_id), None)
        if not dep_prd:
            console.print(
                f"[red]❌ Dependency {dep_id} not found in any PRD files.[/red]"
            )
            continue

        status = dep_prd.status
        path = dep_prd.path

        if status == "done":
            continue
        elif status == "in_progress":
            console.print(f"ℹ️  {dep_id} is already IN PROGRESS.")
        elif status in ["backlog", "inbox"]:
            if click.confirm(
                f"👉 {dep_id} is in {status.upper()}. Would you like to start it first?"
            ):
                if _check_and_suggest_dependencies(dep_prd, all_prds, completed):
                    in_progress = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
                    if in_progress:
                        for f in in_progress:
                            p_to_stop = load_prd(f)
                            p_to_stop.status = "backlog"
                            p_to_stop.save(PRODUCT_BACKLOG_DIR / f.name)
                            f.unlink()

                    dep_prd.status = "in_progress"
                    new_path = PRODUCT_IN_PROGRESS_DIR / dep_prd.path.name
                    dep_prd.save(new_path)
                    dep_prd.path.unlink()
                    console.print(
                        f"[green]✅ Started {dep_id}. Run 'vibe implement' to begin.[/green]"
                    )
                    return False
        else:
            console.print(
                f"[yellow]⚠️  {dep_id} has status '{status}' at {path}. Please resolve this dependency manually.[/yellow]"
            )

    return True


def _display_prd_list(files: List[pathlib.Path], title: Optional[str] = None):
    if title:
        console.print(f"\n[bold]--- {title} ---[/bold]")

    table = Table(box=None, show_header=True, header_style="bold")
    table.add_column("ID", width=10)
    table.add_column("Type", width=10)
    table.add_column("Status", width=15)
    table.add_column("Group", width=15)
    table.add_column("Title")

    if not files:
        console.print("[dim]No PRDs found.[/dim]")
        return

    for f in files:
        try:
            p = load_prd(f)
            display_status = p.status
            if PLANNING_INBOX_DIR.resolve() == f.parent.resolve():
                display_status = "inbox"
            elif PRODUCT_NEXT_DIR.resolve() == f.parent.resolve():
                display_status = "planned"
            elif PRODUCT_BACKLOG_DIR.resolve() == f.parent.resolve():
                display_status = "backlog"
            elif PRODUCT_IN_PROGRESS_DIR.resolve() == f.parent.resolve():
                display_status = "in_progress"
            elif PRODUCT_HISTORY_DIR.resolve() == f.parent.resolve():
                display_status = "done"

            status_color = "white"
            if display_status == "done":
                status_color = "green"
            elif display_status == "in_progress":
                status_color = "blue"
            elif display_status == "planned":
                status_color = "magenta"
            elif display_status == "inbox":
                status_color = "cyan"

            status_text = Text(display_status.upper(), style=status_color)
            type_text = Text(p.type, style="cyan" if p.type == "FEATURE" else "yellow")
            table.add_row(p.id, type_text, status_text, p.group or "-", p.title)
        except Exception:
            table.add_row(f.name, "ERROR", "-", "-", f.name)

    console.print(table)


def register_prd(cli):
    @click.group(invoke_without_command=True)
    @click.pass_context
    def prd(ctx):
        """Manage PRDs and initiatives."""
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @prd.command(name="list")
    @click.option("--all", is_flag=True, help="Show all PRDs including history.")
    def list_prds(all):
        """List unified PRDs and their status."""
        # Collect PRDs from new structure
        inbox = sorted(list(PLANNING_INBOX_DIR.glob("*.md")))
        next_items = sorted(list(PRODUCT_NEXT_DIR.glob("*.md")))
        backlog = sorted(list(PRODUCT_BACKLOG_DIR.glob("*.md")))
        in_progress = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
        history = sorted(list(PRODUCT_HISTORY_DIR.glob("*.md")), reverse=True)

        if in_progress:
            _display_prd_list(in_progress, "In Progress")
        if next_items:
            _display_prd_list(next_items, "Next for Implementation")
        if backlog:
            _display_prd_list(backlog, "Backlog")
        if inbox:
            _display_prd_list(inbox, "Inbox")

        if all:
            if history:
                _display_prd_list(history, "History")
        elif history:
            console.print(
                f"\n[dim]... and {len(history)} items in history (use --all or 'vibe prd history' to see them)[/dim]"
            )

    @prd.command(name="history")
    def prd_history():
        """List PRD history."""
        history = sorted(list(PRODUCT_HISTORY_DIR.glob("*.md")), reverse=True)
        _display_prd_list(history, "PRD History")

    @prd.command(name="rejected")
    def prd_rejected():
        """List rejected PRDs."""
        rejected = sorted(list(PLANNING_REJECTED_DIR.glob("*.md")), reverse=True)
        _display_prd_list(rejected, "Rejected PRDs")

    @prd.command(name="plan")
    @click.option("--page-size", default=10, help="Number of items to show at once.")
    @click.option(
        "--filter", "filter_text", default="", help="Filter PRDs by title or ID."
    )
    def plan_prds(page_size, filter_text):
        """Interactively prioritize the product backlog and inbox."""

        state = {
            "active_pane": 1,  # 0: Next, 1: Planning (Inbox+Backlog)
            "pane_0_selected": 0,
            "pane_1_selected": 0,
            "pane_0_page": 0,
            "pane_1_page": 0,
            "pane_0_files": [],
            "pane_1_files": [],
            "dep_select_mode": False,
            "dep_selected_idx": 0,
            "dep_page": 0,
            "dep_files": [],
            "exit": False,
            "message": "",
            "current_filter": filter_text,
            "filter_mode": False,
            "filter_buffer": filter_text,
        }

        def is_filtering():
            return state["filter_mode"]

        def is_not_filtering():
            return not state["filter_mode"]

        def refresh_files():
            next_items = sorted(list(PRODUCT_NEXT_DIR.glob("*.md")))
            inbox_files = sorted(list(PLANNING_INBOX_DIR.glob("*.md")))
            backlog_files = sorted(list(PRODUCT_BACKLOG_DIR.glob("*.md")))
            planning_files = inbox_files + backlog_files

            f_text = state["current_filter"].lower()
            if f_text:

                def matches(path):
                    if f_text in path.name.lower():
                        return True
                    try:
                        p = load_prd(path)
                        return f_text in p.title.lower() or f_text in p.id.lower()
                    except Exception:
                        return False

                state["pane_0_files"] = [p for p in next_items if matches(p)]
                state["pane_1_files"] = [p for p in planning_files if matches(p)]
            else:
                state["pane_0_files"] = next_items
                state["pane_1_files"] = planning_files

            for i in [0, 1]:
                files = state[f"pane_{i}_files"]
                if not files:
                    state[f"pane_{i}_selected"] = 0
                    state[f"pane_{i}_page"] = 0
                else:
                    state[f"pane_{i}_selected"] = min(
                        state[f"pane_{i}_selected"], len(files) - 1
                    )
                    state[f"pane_{i}_page"] = state[f"pane_{i}_selected"] // page_size

        def render_pane(
            pane_idx: int, files: List[pathlib.Path], selected_idx: int, page: int
        ):
            is_active = (
                (state["active_pane"] == pane_idx)
                and not state["dep_select_mode"]
                and not state["filter_mode"]
            )
            title = (
                "NEXT (Implementation Queue)"
                if pane_idx == 0
                else "PLANNING (Inbox + Backlog)"
            )
            border_style = "bold magenta" if is_active else "dim"

            total_pages = (len(files) + page_size - 1) // page_size if files else 0
            start_idx = page * page_size
            end_idx = min(start_idx + page_size, len(files))
            page_files = files[start_idx:end_idx]

            table = Table(box=None, header_style="bold yellow", expand=True)
            table.add_column("#", width=3)
            table.add_column("ID", width=8)
            table.add_column("Title")
            table.add_column("Deps", width=12)

            for i, f in enumerate(page_files):
                abs_idx = start_idx + i
                is_selected = abs_idx == selected_idx
                try:
                    p = load_prd(f)
                    row_style = (
                        Style(reverse=True) if (is_selected and is_active) else Style()
                    )
                    if (
                        is_selected
                        and not is_active
                        and not state["dep_select_mode"]
                        and not state["filter_mode"]
                    ):
                        row_style += Style(bgcolor="grey23")

                    id_text = Text(
                        p.id, style="cyan" if p.status == "inbox" else "white"
                    )
                    deps_text = ", ".join(p.depends_on) if p.depends_on else "-"
                    table.add_row(
                        str(abs_idx + 1), id_text, p.title, deps_text, style=row_style
                    )
                except Exception:
                    table.add_row(str(abs_idx + 1), "-", f.name, "-", style="red")

            footer = f"Page {page + 1}/{max(1, total_pages)} ({len(files)} items)"
            return Panel(
                table,
                title=title,
                subtitle=footer,
                border_style=border_style,
                expand=True,
            )

        def render_dep_selection():
            files = state["dep_files"]
            selected_idx = state["dep_selected_idx"]
            page = state["dep_page"]

            total_pages = (len(files) + page_size - 1) // page_size if files else 0
            start_idx = page * page_size
            end_idx = min(start_idx + page_size, len(files))
            page_files = files[start_idx:end_idx]

            table = Table(box=None, header_style="bold yellow", expand=True)
            table.add_column("#", width=3)
            table.add_column("ID", width=10)
            table.add_column("Status", width=10)
            table.add_column("Title")

            for i, f in enumerate(page_files):
                abs_idx = start_idx + i
                is_selected = abs_idx == selected_idx
                try:
                    p = load_prd(f)
                    row_style = Style(reverse=True) if is_selected else Style()
                    if f.parent.resolve() == PLANNING_INBOX_DIR.resolve():
                        s_col = "cyan"
                    elif f.parent.resolve() == PRODUCT_NEXT_DIR.resolve():
                        s_col = "magenta"
                    else:
                        s_col = "white"
                    table.add_row(
                        str(abs_idx + 1),
                        p.id,
                        Text(p.status.upper(), style=s_col),
                        p.title,
                        style=row_style,
                    )
                except Exception:
                    table.add_row(str(abs_idx + 1), "-", "ERROR", f.name, style="red")

            footer = (
                f"Page {page + 1}/{max(1, total_pages)} | ENTER: Select | ESC: Cancel"
            )
            return Panel(
                table,
                title="SELECT DEPENDENCY (All PRDs)",
                subtitle=footer,
                border_style="bold yellow",
                expand=True,
            )

        def render_all():
            refresh_files()

            pane_0 = render_pane(
                0, state["pane_0_files"], state["pane_0_selected"], state["pane_0_page"]
            )
            pane_1 = render_pane(
                1, state["pane_1_files"], state["pane_1_selected"], state["pane_1_page"]
            )

            output = [pane_0, pane_1]

            if state["dep_select_mode"]:
                output.append(Text("\n"))
                output.append(render_dep_selection())

            if state["filter_mode"]:
                output.append(
                    Text(f"\n🔍 Filter: {state['filter_buffer']}_", style="bold cyan")
                )
            elif state["current_filter"]:
                output.append(
                    Text(
                        f"\n🔍 Active Filter: '{state['current_filter']}' (S-F to clear)",
                        style="cyan",
                    )
                )

            if state["message"]:
                output.append(Text(f"\n{state['message']}", style="bold yellow"))

            controls = (
                "\n[TAB] Switch List | [Arrows] Select | [SPACE] Move | [S-Arrows] Page"
            )
            actions = "[F] Filter | [S-F] Clear Filter | [S-D] Dependency | [S-R/I/B] Reclassify | [Q] Quit"
            output.append(Text(controls, style="bold"))
            output.append(Text(actions, style="bold"))

            grid = Table.grid()
            grid.add_column()
            for renderable in output:
                grid.add_row(renderable)
            return grid

        def get_tui_text():
            with console.capture() as capture:
                console.print(render_all())
            return ANSI(capture.get())

        kb = KeyBindings()

        @kb.add("tab")
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            state["active_pane"] = 1 - state["active_pane"]

        @kb.add("up")
        def _(event):
            if state["filter_mode"]:
                return
            if state["dep_select_mode"]:
                state["dep_selected_idx"] = max(0, state["dep_selected_idx"] - 1)
                state["dep_page"] = state["dep_selected_idx"] // page_size
            else:
                p = state["active_pane"]
                state[f"pane_{p}_selected"] = max(0, state[f"pane_{p}_selected"] - 1)
                state[f"pane_{p}_page"] = state[f"pane_{p}_selected"] // page_size

        @kb.add("down")
        def _(event):
            if state["filter_mode"]:
                return
            if state["dep_select_mode"]:
                state["dep_selected_idx"] = min(
                    len(state["dep_files"]) - 1, state["dep_selected_idx"] + 1
                )
                state["dep_page"] = state["dep_selected_idx"] // page_size
            else:
                p = state["active_pane"]
                files = state[f"pane_{p}_files"]
                state[f"pane_{p}_selected"] = min(
                    len(files) - 1, state[f"pane_{p}_selected"] + 1
                )
                state[f"pane_{p}_page"] = state[f"pane_{p}_selected"] // page_size

        @kb.add("s-up")
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            p = state["active_pane"]
            state[f"pane_{p}_page"] = max(0, state[f"pane_{p}_page"] - 1)
            state[f"pane_{p}_selected"] = state[f"pane_{p}_page"] * page_size

        @kb.add("s-down")
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            p = state["active_pane"]
            files = state[f"pane_{p}_files"]
            total_pages = (len(files) + page_size - 1) // page_size
            state[f"pane_{p}_page"] = min(
                max(0, total_pages - 1), state[f"pane_{p}_page"] + 1
            )
            state[f"pane_{p}_selected"] = state[f"pane_{p}_page"] * page_size

        @kb.add(
            "f",
            filter=Condition(is_not_filtering)
            & ~Condition(lambda: state["dep_select_mode"]),
        )
        def _(event):
            state["filter_mode"] = True
            state["filter_buffer"] = ""

        @kb.add("F", filter=Condition(is_not_filtering))  # Shift-F
        def _(event):
            state["current_filter"] = ""
            state["message"] = "🗑️ Filter cleared."

        @kb.add("backspace", filter=Condition(is_filtering))
        def _(event):
            state["filter_buffer"] = state["filter_buffer"][:-1]
            state["current_filter"] = state["filter_buffer"]

        @kb.add("escape", filter=Condition(is_filtering))
        def _(event):
            state["filter_mode"] = False

        @kb.add("enter", filter=Condition(is_filtering))
        def _(event):
            state["filter_mode"] = False

        @kb.add("<any>", filter=Condition(is_filtering))
        def _(event):
            for char in event.key_sequence:
                if char.data.isprintable():
                    state["filter_buffer"] += char.data
            state["current_filter"] = state["filter_buffer"]

        @kb.add("enter")
        def _(event):
            if state["filter_mode"]:
                return
            if state["dep_select_mode"]:
                if not state["dep_files"]:
                    state["dep_select_mode"] = False
                    return
                p_idx = state["active_pane"]
                main_files = state[f"pane_{p_idx}_files"]
                main_sel_idx = state[f"pane_{p_idx}_selected"]
                target_prd_file = main_files[main_sel_idx]
                dep_file = state["dep_files"][state["dep_selected_idx"]]
                try:
                    target_prd = load_prd(target_prd_file)
                    dep_prd = load_prd(dep_file)
                    if target_prd.depends_on is None:
                        target_prd.depends_on = []
                    if dep_prd.id == target_prd.id:
                        state["message"] = "❌ A PRD cannot depend on itself."
                    elif dep_prd.id in target_prd.depends_on:
                        state["message"] = f"ℹ️ Already depends on {dep_prd.id}."
                    else:
                        target_prd.depends_on.append(dep_prd.id)
                        target_prd.save()
                        state["message"] = (
                            f"✅ Added dependency: {target_prd.id} -> {dep_prd.id}"
                        )
                except Exception as e:
                    state["message"] = f"❌ Error: {str(e)}"
                state["dep_select_mode"] = False

        @kb.add("space")
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            p_idx = state["active_pane"]
            files = state[f"pane_{p_idx}_files"]
            if not files:
                return
            sel_idx = state[f"pane_{p_idx}_selected"]
            selected_file = files[sel_idx]
            try:
                prd = load_prd(selected_file)
                if p_idx == 1:
                    prd.status = "planned"
                    target_path = PRODUCT_NEXT_DIR / selected_file.name
                    prd.save(target_path)
                    selected_file.unlink()
                    state["message"] = f"✅ Moved {prd.id} to NEXT."
                else:
                    prd.status = "backlog"
                    target_path = PRODUCT_BACKLOG_DIR / selected_file.name
                    prd.save(target_path)
                    selected_file.unlink()
                    state["message"] = f"✅ Moved {prd.id} to BACKLOG."
            except Exception as e:
                state["message"] = f"❌ Error: {str(e)}"

        @kb.add("R")  # Shift-R
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            p_idx = state["active_pane"]
            files = state[f"pane_{p_idx}_files"]
            if not files:
                return
            sel_idx = state[f"pane_{p_idx}_selected"]
            selected_file = files[sel_idx]
            try:
                prd = load_prd(selected_file)
                prd.status = "rejected"
                prd.save(PLANNING_REJECTED_DIR / selected_file.name)
                selected_file.unlink()
                state["message"] = f"🚫 Rejected {prd.id}."
            except Exception as e:
                state["message"] = f"❌ Error: {str(e)}"

        @kb.add("I")  # Shift-I
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            p_idx = state["active_pane"]
            files = state[f"pane_{p_idx}_files"]
            if not files:
                return
            sel_idx = state[f"pane_{p_idx}_selected"]
            selected_file = files[sel_idx]
            try:
                prd = load_prd(selected_file)
                prd.status = "inbox"
                prd.save(PLANNING_INBOX_DIR / selected_file.name)
                if selected_file != (PLANNING_INBOX_DIR / selected_file.name):
                    selected_file.unlink()
                state["message"] = f"📥 Moved {prd.id} to INBOX."
            except Exception as e:
                state["message"] = f"❌ Error: {str(e)}"

        @kb.add("B")  # Shift-B
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            p_idx = state["active_pane"]
            files = state[f"pane_{p_idx}_files"]
            if not files:
                return
            sel_idx = state[f"pane_{p_idx}_selected"]
            selected_file = files[sel_idx]
            try:
                prd = load_prd(selected_file)
                prd.status = "backlog"
                prd.save(PRODUCT_BACKLOG_DIR / selected_file.name)
                if selected_file != (PRODUCT_BACKLOG_DIR / selected_file.name):
                    selected_file.unlink()
                state["message"] = f"📦 Moved {prd.id} to BACKLOG."
            except Exception as e:
                state["message"] = f"❌ Error: {str(e)}"

        @kb.add("D")  # Shift-D
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            p_idx = state["active_pane"]
            files = state[f"pane_{p_idx}_files"]
            if not files:
                return
            state["dep_select_mode"] = True
            inbox_files = sorted(list(PLANNING_INBOX_DIR.glob("*.md")))
            backlog_files = sorted(list(PRODUCT_BACKLOG_DIR.glob("*.md")))
            next_files = sorted(list(PRODUCT_NEXT_DIR.glob("*.md")))
            state["dep_files"] = next_files + inbox_files + backlog_files
            state["dep_selected_idx"] = 0
            state["dep_page"] = 0

        @kb.add("escape")
        def _(event):
            if state["dep_select_mode"]:
                state["dep_select_mode"] = False
            if state["filter_mode"]:
                state["filter_mode"] = False

        @kb.add("q")
        @kb.add("c-c")
        def _(event):
            if state["dep_select_mode"]:
                state["dep_select_mode"] = False
            elif state["filter_mode"]:
                state["filter_mode"] = False
            else:
                event.app.exit()

        # Pure keystroke TUI loop
        app = Application(
            layout=Layout(Window(content=FormattedTextControl(text=get_tui_text))),
            key_bindings=kb,
            full_screen=True,
        )
        app.run()

    @prd.command(name="stop")
    def stop_prd():
        """Move the current in-progress PRD back to the backlog."""
        in_progress = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
        if not in_progress:
            console.print("[yellow]No PRD is currently in progress.[/yellow]")
            return

        for f in in_progress:
            p = load_prd(f)
            p.status = "backlog"
            p.save(PRODUCT_BACKLOG_DIR / f.name)
            f.unlink()
            console.print(
                f"[green]✅ Stopped {p.id} and moved back to backlog.[/green]"
            )

    @prd.command(name="pm")
    @click.argument("query", required=False)
    @click.pass_context
    def pm_command(ctx, query):
        pm_tool = InteractivePM(
            agent_type=ctx.obj.get("agent", "cursor-agent"),
            stream=ctx.obj.get("stream", True),
        )
        pm_tool.run(query)

    @prd.command(name="move")
    @click.argument("prd_id")
    @click.argument(
        "target",
        type=click.Choice(
            ["backlog", "history", "rejected", "in_progress", "next", "inbox"]
        ),
    )
    def move_prd(prd_id, target):
        all_files = list(PRODUCT_DIR.rglob("*.md"))
        found_path = next((f for f in all_files if prd_id.upper() in f.name), None)
        if not found_path:
            console.print(f"[red]❌ PRD not found: {prd_id}[/red]")
            return

        target_map = {
            "backlog": PRODUCT_BACKLOG_DIR,
            "history": PRODUCT_HISTORY_DIR,
            "rejected": PLANNING_REJECTED_DIR,
            "in_progress": PRODUCT_IN_PROGRESS_DIR,
            "next": PRODUCT_NEXT_DIR,
            "inbox": PLANNING_INBOX_DIR,
        }

        target_dir = target_map[target]
        ensure_dir(target_dir)
        p = load_prd(found_path)
        p.status = {
            "history": "done",
            "in_progress": "in_progress",
            "next": "planned",
            "inbox": "inbox",
        }.get(target, "backlog")
        p.save(target_dir / found_path.name)
        found_path.unlink()
        console.print(f"[green]✅ Moved {prd_id} to {target}[/green]")

    cli.add_command(prd)
