import click

from vibe_tools.utils import load_project_state, reset_prd_state


def register_implemented(cli):
    @click.command()
    def implemented():
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
    cli.add_command(implemented)
