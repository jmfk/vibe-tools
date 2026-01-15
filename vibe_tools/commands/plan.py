import click
import pathlib
import re
import datetime
import json
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
    get_prompt,
    run_llm,
)
from vibe_tools.pm import InteractivePM
from vibe_tools.architect import InteractiveArchitect
from vibe_tools.prds import load_prd, PRD, generate_prd_id

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
        console.print("[dim]No items found.[/dim]")
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


def register_plan(cli):
    @click.group(name="plan", invoke_without_command=True)
    @click.pass_context
    def plan_group(ctx):
        """Phase 3: Unified Planning and Issue Management."""
        if ctx.invoked_subcommand is None:
            ctx.invoke(plan_tui)

    @plan_group.command(name="tui")
    @click.option("--page-size", default=10, help="Number of items to show at once.")
    @click.option(
        "--filter", "filter_text", default="", help="Filter by title or ID."
    )
    @click.pass_context
    def plan_tui(ctx, page_size, filter_text):
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
            table.add_column("Type", width=6)
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
                    type_text = Text(
                        "PRD" if p.type == "FEATURE" else "ISS",
                        style="cyan" if p.type == "FEATURE" else "yellow",
                    )
                    deps_text = ", ".join(p.depends_on) if p.depends_on else "-"
                    table.add_row(
                        str(abs_idx + 1), id_text, type_text, p.title, deps_text, style=row_style
                    )
                except Exception:
                    table.add_row(str(abs_idx + 1), "-", "-", f.name, "-", style="red")

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
                title="SELECT DEPENDENCY (All Items)",
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
            actions = "[F] Filter | [S-F] Clear | [S-D] Dep | [S-A] Architect | [S-P] PM | [S-T] Tests | [Q] Quit"
            reclass = "[S-R/I/B] Reclassify (Rejected/Inbox/Backlog)"
            
            output.append(Text(controls, style="bold"))
            output.append(Text(actions, style="bold"))
            output.append(Text(reclass, style="bold"))

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

        @kb.add("A")  # Shift-A
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            event.app.exit()
            # Run architect
            arch_tool = InteractiveArchitect(
                agent_type=ctx.obj.get("agent", "cursor-agent"),
                stream=ctx.obj.get("stream", True),
            )
            arch_tool.run_loop()
            # Rerun TUI? For now just exit TUI.

        @kb.add("P")  # Shift-P
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            event.app.exit()
            # Run PM
            pm_tool = InteractivePM(
                agent_type=ctx.obj.get("agent", "cursor-agent"),
                stream=ctx.obj.get("stream", True),
            )
            pm_tool.run()

        @kb.add("T")  # Shift-T
        def _(event):
            if state["dep_select_mode"] or state["filter_mode"]:
                return
            event.app.exit()
            # Run Test Setup
            _run_test_setup_interactive(ctx)

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
                        state["message"] = "❌ An item cannot depend on itself."
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

    @plan_group.command(name="list")
    @click.option("--all", is_flag=True, help="Show all items including history.")
    @click.option("--issues-only", is_flag=True, help="Show only issues.")
    @click.option("--prds-only", is_flag=True, help="Show only PRDs.")
    def list_items(all, issues_only, prds_only):
        """List unified PRDs/Issues and their status."""
        # Collect items from new structure
        inbox = sorted(list(PLANNING_INBOX_DIR.glob("*.md")))
        next_items = sorted(list(PRODUCT_NEXT_DIR.glob("*.md")))
        backlog = sorted(list(PRODUCT_BACKLOG_DIR.glob("*.md")))
        in_progress = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
        history = sorted(list(PRODUCT_HISTORY_DIR.glob("*.md")), reverse=True)

        def filter_type(files):
            if not issues_only and not prds_only:
                return files
            result = []
            for f in files:
                try:
                    p = load_prd(f)
                    if issues_only and p.type == "ISSUE":
                        result.append(f)
                    elif prds_only and p.type == "FEATURE":
                        result.append(f)
                except Exception:
                    continue
            return result

        in_progress = filter_type(in_progress)
        next_items = filter_type(next_items)
        backlog = filter_type(backlog)
        inbox = filter_type(inbox)
        history = filter_type(history)

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
                f"\n[dim]... and {len(history)} items in history (use --all to see them)[/dim]"
            )

    @plan_group.command(name="history")
    def plan_history():
        """List planning history."""
        history = sorted(list(PRODUCT_HISTORY_DIR.glob("*.md")), reverse=True)
        _display_prd_list(history, "History")

    @plan_group.command(name="rejected")
    def plan_rejected():
        """List rejected items."""
        rejected = sorted(list(PLANNING_REJECTED_DIR.glob("*.md")), reverse=True)
        _display_prd_list(rejected, "Rejected Items")

    @plan_group.command(name="stop")
    def stop_item():
        """Move the current in-progress item back to the backlog."""
        in_progress = list(PRODUCT_IN_PROGRESS_DIR.glob("*.md"))
        if not in_progress:
            console.print("[yellow]No item is currently in progress.[/yellow]")
            return

        for f in in_progress:
            p = load_prd(f)
            p.status = "backlog"
            p.save(PRODUCT_BACKLOG_DIR / f.name)
            f.unlink()
            console.print(
                f"[green]✅ Stopped {p.id} and moved back to backlog.[/green]"
            )

    @plan_group.command(name="pm")
    @click.argument("query", required=False)
    @click.pass_context
    def pm_command(ctx, query):
        """Phase 2: Interactive Product Manager for requirement and PRD management."""
        pm_tool = InteractivePM(
            agent_type=ctx.obj.get("agent", "cursor-agent"),
            stream=ctx.obj.get("stream", True),
        )
        pm_tool.run(query)

    @plan_group.command(name="architect")
    @click.argument("query", required=False)
    @click.pass_context
    def architect_command(ctx, query):
        """Phase 1: Interactive architecture and infrastructure spec manager."""
        architect_tool = InteractiveArchitect(
            agent_type=ctx.obj.get("agent", "cursor-agent"),
            stream=ctx.obj.get("stream", True),
        )
        architect_tool.run_loop(query)

    @plan_group.command(name="move")
    @click.argument("item_id")
    @click.argument(
        "target",
        type=click.Choice(
            ["backlog", "history", "rejected", "in_progress", "next", "inbox"]
        ),
    )
    def move_item(item_id, target):
        """Move an item to a different status/directory."""
        all_files = list(PRODUCT_DIR.rglob("*.md"))
        found_path = next((f for f in all_files if item_id.upper() in f.name), None)
        if not found_path:
            console.print(f"[red]❌ Item not found: {item_id}[/red]")
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
        console.print(f"[green]✅ Moved {item_id} to {target}[/green]")

    @plan_group.command(name="add")
    @click.argument("prompt", required=False)
    @click.option("--title", help="Explicitly set title")
    @click.option(
        "--severity",
        type=click.Choice(["low", "medium", "high", "critical"]),
        help="Explicitly set severity",
    )
    @click.option("--service", help="Explicitly set service")
    @click.option("--prd", is_flag=True, help="Create as a PRD instead of an Issue")
    def add_item(prompt, title, severity, service, prd):
        """Create a new item (Issue/PRD) from a prompt."""
        if not prompt:
            from vibe_tools.commands.issue_add import get_interactive_prompt
            prompt = get_interactive_prompt()
            if not prompt:
                click.echo("Aborted.")
                return

        click.echo(f"🤖 Analyzing prompt and generating {'PRD' if prd else 'Issue'} details...")

        template_str = get_prompt("issue_add_prompt.txt")
        rendered_prompt = template_str.replace("{{ prompt }}", prompt)

        response = run_llm(rendered_prompt)

        # Parse JSON from response
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "{" in response:
                json_str = response[response.find("{") : response.rfind("}") + 1]
            else:
                json_str = response
            data = json.loads(json_str)
        except Exception as e:
            click.echo(f"Error parsing AI response: {e}")
            click.echo(f"Raw response: {response}")
            return

        # Apply overrides
        item_title = title or data.get("title", "Untitled Item")
        item_severity = severity or data.get("severity", "medium")
        item_service = service or data.get("service", "")
        item_summary = data.get("summary", "")

        now = datetime.datetime.now().isoformat()
        item_id = generate_prd_id(PRODUCT_DIR)

        # Create sanitized filename
        safe_title = re.sub(r"[^a-z0-9]+", "-", item_title.lower()).strip("-")
        filename = f"{item_id}-{safe_title}.md"
        if len(filename) > 64:
            filename = filename[:60] + ".md"

        target_path = PLANNING_INBOX_DIR / filename

        new_item = PRD(
            id=item_id,
            title=item_title,
            type="FEATURE" if prd else "ISSUE",
            status="backlog",
            created_at=now,
            updated_at=now,
            content=f"# {item_title}\n\n{item_summary}",
            metadata={
                "severity": item_severity,
                "service": item_service,
                "summary": item_summary,
            },
            path=target_path,
        )

        new_item.save()
        click.echo(f"✅ {'PRD' if prd else 'Issue'} created successfully!")
        click.echo(f"ID:       {new_item.id}")
        click.echo(f"Title:    {new_item.title}")
        click.echo(f"Location: {target_path}")

    @plan_group.command(name="test-setup")
    @click.argument("prompt", required=False)
    @click.pass_context
    def test_setup_cmd(ctx, prompt):
        """Setup tests from a prompt (Phase 6 pre-work)."""
        _run_test_setup_interactive(ctx, prompt)

    cli.add_command(plan_group)


def _run_test_setup_interactive(ctx, prompt: Optional[str] = None):
    """Internal helper to run test setup logic."""
    if not prompt:
        from prompt_toolkit import prompt as pt_prompt
        click.echo(click.style("\n🧪 Describe the tests you want to generate:", fg="cyan"))
        prompt = pt_prompt("> ")
        if not prompt:
            click.echo("Aborted.")
            return

    click.echo("🤖 Generating test specifications...")
    
    agent = ctx.obj.get("agent", "cursor-agent")
    stream = ctx.obj.get("stream", True)
    
    # We use Ralph to actually implement the tests
    from vibe_tools.ralph import RalphLoop
    from vibe_tools.utils import get_agent_command, run_agent
    
    # First, let the agent decide what tests to create
    system_prompt = f"""You are a Test Engineer.
Based on the user's request: "{prompt}"
Decide which test files need to be created or updated.
Output a plan in markdown format.
"""
    cmd = get_agent_command(agent, system_prompt)
    output, code = run_agent(cmd, stream=stream)
    
    if code == 0:
        click.echo("\n✅ Test plan generated. Now implementing...")
        # Now use a RalphLoop to actually write the tests
        loop = RalphLoop(
            name="Test Implementation",
            desired_content=output,
            desired_file_name="test_plan.md",
            agent=agent,
            stream=stream,
        )
        loop.instructions = [
            "Implement the tests described in the test plan.",
            "Use existing testing frameworks (pytest for backend, vitest for frontend).",
            "Ensure tests are placed in the correct directories (tests/ or frontend/src/).",
            "Verify that the tests can be run via 'make test'.",
        ]
        loop.run()
    else:
        click.echo("❌ Failed to generate test plan.")

def load_prd_by_id(item_id: str) -> Optional[PRD]:
    """Helper to find an item by ID across all directories."""
    all_files = list(PRODUCT_DIR.rglob("*.md"))
    found_path = next((f for f in all_files if item_id.upper() in f.name), None)
    if found_path:
        return load_prd(found_path)
    return None
