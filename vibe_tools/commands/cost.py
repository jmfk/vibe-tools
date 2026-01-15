import click

from vibe_tools.cost import get_total_cost
from vibe_tools.utils import COSTS_DIR, load_config


def register_cost(cli):
    @click.command()
    @click.option("--json", "json_format", is_flag=True, help="Output in JSON format.")
    def cost(json_format):
        """Display the total estimated cost of LLM usage for this project."""
        total = get_total_cost()
        if json_format:
            import json

            click.echo(json.dumps({"total_cost": total}))
            return

        config = load_config()
        use_google = config.get("use_google_sheets", False)
        sheet_id = config.get("google_sheet_id")

        click.echo(f"\nTotal estimated cost: ${total:.4f} USD")
        click.echo(f"Detailed log available at: {COSTS_DIR}/usage.csv")

        if use_google and sheet_id:
            click.echo(f"Google Sheets Logging: ENABLED (ID: {sheet_id})")
        else:
            click.echo("Google Sheets Logging: DISABLED")

    cli.add_command(cost)
