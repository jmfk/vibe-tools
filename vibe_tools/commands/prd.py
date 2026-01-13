import click
import pathlib
import shutil
from typing import Optional

from vibe_tools.utils import (
    collect_all_prd_info,
    load_project_state,
    reset_prd_state,
    PLANNING_INBOX_DIR,
    PLANNING_BACKLOG_DIR,
    PLANNING_HISTORY_DIR,
    PLANNING_REJECTED_DIR,
    PLANNING_DIR,
    ensure_dir,
    logger
)
from vibe_tools.pm import InteractivePM


def register_prd(cli):
    @click.group(invoke_without_command=True)
    @click.pass_context
    def prd(ctx):
        """Manage PRDs and specifications."""
        if ctx.invoked_subcommand is None:
            ctx.invoke(list_prds)

    @prd.command(name="list")
    def list_prds():
        """List the status of all PRDs."""
        prds = collect_all_prd_info()
        if not prds:
            click.echo("No PRD files found.")
            return

        click.echo(f"{'PRD':<40} {'MD':<5} {'YAML':<5} {'Status':<15}")
        click.echo("-" * 70)

        state = load_project_state()
        completed_prds = state.get("completed_prds", [])
        started_prds = state.get("started_prds", [])
        plans = state.get("plans", {})

        for info in prds:
            project_name = info["name"]
            display_name = project_name
            
            if info["has_yaml"] and info["yaml_path"]:
                prd_stem = info["yaml_path"].stem
                if prd_stem.startswith("v"):
                    display_name = prd_stem
            elif info["has_md"] and info["md_path"]:
                prd_stem = info["md_path"].stem
            else:
                prd_stem = project_name

            md_status = "✅" if info["has_md"] else "❌"
            yaml_status = "✅" if info["has_yaml"] else "❌"

            # Check status in plans first (Source of Truth)
            plan_status = None
            prd_id = f"prd_{project_name}"
            if prd_stem in plans:
                plan_status = plans[prd_stem].get("status")
            elif project_name in plans:
                plan_status = plans[project_name].get("status")
            elif prd_id in plans:
                plan_status = plans[prd_id].get("status")

            if plan_status == "completed" or prd_stem in completed_prds or project_name in completed_prds or prd_id in completed_prds:
                status = click.style("✅ DONE", fg="green")
            elif plan_status == "in_progress" or prd_stem in started_prds or project_name in started_prds or prd_id in started_prds:
                status = click.style("⏳ IN_PROGRESS", fg="blue")
            else:
                status = click.style("⚪️ PENDING", fg="white", dim=True)

            click.echo(f"{display_name:<40} {md_status:<5} {yaml_status:<5} {status:<15}")

    @prd.command(name="manage")
    def manage_prds():
        """List implemented PRDs (batched) and optionally reset them."""
        state = load_project_state()
        completed = state.get("completed_prds", [])

        if not completed:
            click.echo("No implemented PRDs found.")
            return

        # Sort reverse (last implemented first)
        completed = list(reversed(completed))

        batch_size = 10
        current_idx = 0

        while current_idx < len(completed):
            batch = completed[current_idx : current_idx + batch_size]
            click.echo(
                click.style(
                    f"\n--- Implemented PRDs (Batch {current_idx // batch_size + 1}) ---",
                    fg="green",
                    bold=True,
                )
            )
            for i, prd_name in enumerate(batch, 1):
                click.echo(f"  {i}. {prd_name}")

            click.echo("-" * 40)
            options = ["q"]
            prompt_parts = ["[q]uit"]

            if current_idx + batch_size < len(completed):
                options.append("n")
                prompt_parts.append("[n]ext batch")

            # Add number options
            num_options = [str(i) for i in range(1, len(batch) + 1)]
            options.extend(num_options)
            prompt_parts.append("[1-10] to reset")

            prompt_text = f"Select an option ({', '.join(prompt_parts)})"
            choice = click.prompt(prompt_text, type=click.Choice(options), default="q")

            if choice == "q":
                break
            elif choice == "n":
                current_idx += batch_size
            elif choice in num_options:
                selected_prd = batch[int(choice) - 1]
                if click.confirm(
                    f"Are you sure you want to reset '{selected_prd}'?", default=False
                ):
                    messages = reset_prd_state(selected_prd)
                    for msg in messages:
                        click.echo(f"✅ {msg}")
                    # Update completed list for display
                    completed.remove(selected_prd)
                    if not completed:
                        click.echo("No more implemented PRDs.")
                        break
                else:
                    click.echo("Reset cancelled.")

        click.echo("Done.")

    @prd.command(name="pm")
    @click.argument("query", required=False)
    @click.pass_context
    def pm_command(ctx, query):
        """Phase 1: Interactive PRD and specification manager."""
        pm_tool = InteractivePM(
            agent_type=ctx.obj.get("agent", "cursor-agent"),
            stream=ctx.obj.get("stream", True),
        )
        pm_tool.run(query)

    @prd.command(name="move")
    @click.argument("prd_name")
    @click.argument("target", type=click.Choice(["inbox", "backlog", "history", "rejected"]))
    def move_prd(prd_name, target):
        """Move a PRD to a new planning stage."""
        prd_info = collect_all_prd_info()
        found_info = None
        for info in prd_info:
            if info["name"] == prd_name or (info["has_md"] and info["md_path"].stem == prd_name):
                found_info = info
                break
        
        if not found_info or not found_info["has_md"]:
            click.echo(f"❌ PRD MD file not found: {prd_name}")
            return
            
        md_path = found_info["md_path"]
        
        target_map = {
            "inbox": PLANNING_INBOX_DIR,
            "backlog": PLANNING_BACKLOG_DIR,
            "history": PLANNING_HISTORY_DIR,
            "rejected": PLANNING_REJECTED_DIR,
        }
        
        target_dir = target_map[target]
        ensure_dir(target_dir)
        
        target_path = target_dir / md_path.name
        
        if target_path.exists():
            click.echo(f"❌ Target path already exists: {target_path}")
            return
            
        click.echo(f"🚚 Moving {md_path.name} to {target}...")
        shutil.move(str(md_path), str(target_path))
        click.echo(f"✅ Moved to {target_path}")
        click.echo("💡 Tip: Run 'vibe sync' to update implementation state.")

    cli.add_command(prd)
