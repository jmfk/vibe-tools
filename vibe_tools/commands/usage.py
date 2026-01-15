import click
import datetime
import io
import csv
import pathlib

from vibe_tools.stats import download_and_process_usage, process_usage_csv, COSTS_DIR


def register_usage(cli):
    @click.command()
    @click.option(
        "--file",
        type=click.Path(exists=True),
        help="Path to a downloaded usage CSV file to process.",
    )
    @click.option(
        "--backtrack",
        type=int,
        default=1,
        help="Number of days to go back in time for the download URL.",
    )
    @click.option(
        "--month",
        is_flag=True,
        help="Fetch usage for the entire current month.",
    )
    @click.pass_context
    def usage(ctx, file, backtrack, month):
        """Get Cursor usage from a downloaded CSV file."""
        agent_name = ctx.obj.get("agent", "cursor-agent")

        if file:
            try:
                csv_path = pathlib.Path(file)
                csv_content = csv_path.read_text(encoding="utf-8")
                click.echo(f"📄 Processing provided file: {file}")
                process_usage_csv(csv_content, agent_name)
            except Exception as e:
                click.echo(f"❌ Error processing file: {e}")
                return
        else:
            # Calculate dates based on backtrack or month
            if month:
                end_date = datetime.datetime.now()
                start_date = end_date.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
                backtrack = (end_date - start_date).days + 1

            if not download_and_process_usage(backtrack, agent_name):
                return

        # Display summary of all usage
        from vibe_tools.stats import list_usage_files, aggregate_usage_data

        files = list_usage_files(COSTS_DIR)
        if not files:
            click.echo("No usage data found.")
            return

        data = aggregate_usage_data(files)
        total_tokens = data["total_input_tokens"] + data["total_output_tokens"]
        total_cost = data["total_cost"]
        rows_count = len(data["rows"])

        click.echo(f"\n--- Cursor Usage Summary ---")
        click.echo(f"Total Requests: {rows_count:,}")
        click.echo(f"Total Tokens:   {total_tokens:,}")
        click.echo(f"Total Cost:     ${total_cost:.4f}")

        click.echo("\nFor more detailed reports, use 'vibe stats'.")

    cli.add_command(usage)
