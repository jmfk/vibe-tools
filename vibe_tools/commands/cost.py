import click
import datetime

from vibe_tools.cost import get_total_cost, get_cost_for_period, get_month_bounds
from vibe_tools.utils import COSTS_DIR, load_config


def register_cost(cli):
    @click.command()
    @click.option("--json", "json_format", is_flag=True, help="Output in JSON format.")
    def cost(json_format):
        """Display the total estimated cost of LLM usage for this project."""
        total = get_total_cost()
        
        now = datetime.datetime.now()
        
        # Current month
        curr_start, curr_next = get_month_bounds(now)
        current_month_cost = get_cost_for_period(curr_start, curr_next)
        
        # Last month
        last_month_date = curr_start - datetime.timedelta(days=1)
        last_start, last_next = get_month_bounds(last_month_date)
        last_month_cost = get_cost_for_period(last_start, last_next)

        import sys
        if json_format or "--server" in sys.argv:
            data = {
                "total_cost": total,
                "current_month_cost": current_month_cost,
                "last_month_cost": last_month_cost,
                "current_month_name": curr_start.strftime("%B %Y"),
                "last_month_name": last_start.strftime("%B %Y")
            }
            
            if "--server" in sys.argv:
                from vibe_tools.command_output import output_manager
                output_manager.emit_server_message("cost_result", data)
            
            if json_format:
                import json
                click.echo(json.dumps(data))
            return

        config = load_config()
        use_google = config.get("use_google_sheets", False)
        sheet_id = config.get("google_sheet_id")

        click.echo("\n--- Project Cost Tracking ---")
        click.echo(f"Total Project Cost:   ${total:.4f} USD")
        click.echo(f"Cost {curr_start.strftime('%B %Y')}:      ${current_month_cost:.4f} USD")
        click.echo(f"Cost {last_start.strftime('%B %Y')}:     ${last_month_cost:.4f} USD")
        
        click.echo(f"\nDetailed log: {COSTS_DIR}/usage.csv")

        if use_google and sheet_id:
            click.echo(f"Google Sheets: ENABLED (ID: {sheet_id})")
        else:
            click.echo("Google Sheets: DISABLED")

    cli.add_command(cost)
