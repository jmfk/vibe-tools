import click
import sys
from vibe_tools.stats import (
    aggregate_usage_data,
    list_usage_files,
    get_date_range,
)
from vibe_tools.utils import COSTS_DIR, logger

def register_stats(cli):
    @click.command()
    @click.option("--month", "period", flag_value="month", help="Use current month range.")
    @click.option("--prev-month", "period", flag_value="prev-month", help="Use previous month range.")
    @click.option("--last-3-months", "period", flag_value="3-months", help="Use last 3 months range.")
    @click.option("--last-6-months", "period", flag_value="6-months", help="Use last 6 months range.")
    @click.option("--year", "period", flag_value="year", help="Use last year range.")
    @click.pass_context
    def stats(ctx, period):
        """Get detailed resource usage statistics for the UI."""
        server_mode = "--server" in sys.argv
        
        if not period:
            period = "month"
            
        start, end = get_date_range(period)
        files = list_usage_files(COSTS_DIR)
        
        if not files:
            if server_mode:
                from vibe_tools.command_output import output_manager
                output_manager.emit_server_message("stats_result", {
                    "type": "stats_result",
                    "total_cost": 0,
                    "request_count": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cache_read": 0,
                    "by_model": {},
                    "by_kind": {},
                    "by_phase": {},
                    "by_prd": {},
                    "by_agent": {}
                })
            else:
                click.echo("No usage data found.")
            return

        data = aggregate_usage_data(files, start, end)
        
        if server_mode:
            from vibe_tools.command_output import output_manager
            # Flatten defaultdicts for JSON serialization
            clean_data = {
                "type": "stats_result",
                "total_cost": data["total_cost"],
                "total_input_tokens": data["total_input_tokens"],
                "total_output_tokens": data["total_output_tokens"],
                "total_cache_read": data.get("total_cache_read", 0),
                "request_count": len(data["rows"]),
                "by_model": dict(data["by_model"]),
                "by_kind": dict(data["by_kind"]),
                "by_phase": dict(data["by_phase"]),
                "by_prd": dict(data["by_prd"]),
                "by_agent": dict(data["by_agent"]),
            }
            output_manager.emit_server_message("stats_result", clean_data)
        else:
            click.echo(f"Total Cost: ${data['total_cost']:.4f}")
            click.echo(f"Requests:   {len(data['rows'])}")

    cli.add_command(stats)
