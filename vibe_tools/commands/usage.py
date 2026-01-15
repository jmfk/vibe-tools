import click
import datetime
import pathlib
import sys
import re
import traceback

from vibe_tools.stats import (
    download_and_process_usage,
    process_usage_csv,
    aggregate_usage_data,
    list_usage_files,
    get_date_range,
    generate_report,
    fetch_usage_events,
)
from vibe_tools.cost import get_total_cost, get_cost_for_period, get_month_bounds
from vibe_tools.utils import COSTS_DIR, load_config, get_cursor_api_key


def register_usage(cli):
    @click.command()
    @click.option(
        "--download",
        is_flag=True,
        help="Download latest usage data from Cursor API.",
    )
    @click.option(
        "--report",
        is_flag=True,
        help="Generate a statistics report in /reports.",
    )
    @click.option(
        "--file",
        type=click.Path(exists=True),
        help="Path to a downloaded usage CSV file to process.",
    )
    @click.option(
        "--days",
        type=int,
        default=7,
        help="Number of days for report or download (default: 7).",
    )
    @click.option("--start-date", help="Start date (YYYY-MM-DD).")
    @click.option("--end-date", help="End date (YYYY-MM-DD).")
    @click.option(
        "--today", "period", flag_value="today", help="Use today's range."
    )
    @click.option(
        "--yesterday", "period", flag_value="yesterday", help="Use yesterday's range."
    )
    @click.option(
        "--week", "period", flag_value="week", help="Use current week range."
    )
    @click.option(
        "--prev-week", "period", flag_value="prev-week", help="Use previous week range."
    )
    @click.option(
        "--month", "period", flag_value="month", help="Use current month range."
    )
    @click.option(
        "--prev-month",
        "period",
        flag_value="prev-month",
        help="Use previous month range.",
    )
    @click.option(
        "--last-3-months",
        "period",
        flag_value="3-months",
        help="Use last 3 months range.",
    )
    @click.option(
        "--last-6-months",
        "period",
        flag_value="6-months",
        help="Use last 6 months range.",
    )
    @click.option(
        "--year", "period", flag_value="year", help="Use last year range."
    )
    @click.pass_context
    def usage(ctx, download, report, file, days, start_date, end_date, period):
        """Get Cursor usage and cost statistics."""
        agent_name = ctx.obj.get("agent", "cursor-agent")
        server_mode = "--server" in sys.argv

        # 1. Handle File Processing
        if file:
            try:
                csv_path = pathlib.Path(file)
                csv_content = csv_path.read_text(encoding="utf-8")
                if not server_mode:
                    click.echo(f"📄 Processing provided file: {file}")
                process_usage_csv(csv_content, agent_name)
            except Exception as e:
                click.echo(f"❌ Error processing file: {e}")
                return

        # 2. Handle Download
        if download:
            if not server_mode:
                click.echo("📊 Downloading usage data...")
            
            # If period or days specified, use those for download range
            backtrack = days
            if period:
                start, end = get_date_range(period)
                backtrack = (end - start).days + 1
            
            if not download_and_process_usage(backtrack, agent_name):
                return

        # 3. Handle Report Generation
        if report:
            reports_dir = pathlib.Path("reports")
            
            # Use period or specific dates
            if start_date and end_date:
                start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            elif period:
                start, end = get_date_range(period)
            else:
                end = datetime.datetime.now()
                start = end - datetime.timedelta(days=days)

            if not server_mode:
                click.echo(f"📊 Generating report from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}...")

            files = list_usage_files(COSTS_DIR)
            if not files:
                click.echo("No usage data found to generate report.")
                return

            data = aggregate_usage_data(files, start, end)
            if not data["rows"]:
                click.echo("No usage data found for the specified period.")
                return

            try:
                report_path = generate_report(
                    None, reports_dir, data=data, source=f"Local Files ({period or f'{days} days'})"
                )
                if not server_mode:
                    click.echo(f"✅ Report generated: {report_path}")
                    # click.launch(str(report_path)) # User requested no interactive feedback/no need for feedback
                
                if server_mode:
                    from vibe_tools.command_output import output_manager
                    clean_data = {
                        "report_path": str(report_path),
                        "total_cost": data["total_cost"],
                        "total_input_tokens": data["total_input_tokens"],
                        "total_output_tokens": data["total_output_tokens"],
                        "request_count": len(data["rows"]),
                        "by_model": dict(data["by_model"]),
                        "by_agent": dict(data["by_agent"]),
                    }
                    output_manager.emit_server_message("usage_report_result", clean_data)
            except Exception as e:
                click.echo(f"❌ Error generating report: {e}")
                if not server_mode:
                    traceback.print_exc()
            return

        # 4. Default: Display Summary (Quick Overview)
        if start_date and end_date:
            start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        elif period:
            start, end = get_date_range(period)
        else:
            # Traditional summary view
            total_cost = get_total_cost()
            now = datetime.datetime.now()
            
            # Current month
            curr_start, curr_next = get_month_bounds(now)
            current_month_cost = get_cost_for_period(curr_start, curr_next)
            
            # Last month
            last_month_date = curr_start - datetime.timedelta(days=1)
            last_start, last_next = get_month_bounds(last_month_date)
            last_month_cost = get_cost_for_period(last_start, last_next)

            if server_mode:
                from vibe_tools.command_output import output_manager
                from vibe_tools.agent import AgentManager

                agent_manager = AgentManager()
                active_agents = agent_manager.get_active_agents()

                # Get aggregated data for the UI
                files = list_usage_files(COSTS_DIR)
                agg_data = aggregate_usage_data(files, curr_start, curr_next)

                data = {
                    "type": "stats_result",  # UI expects this type
                    "total_cost": total_cost,
                    "current_month_cost": current_month_cost,
                    "last_month_cost": last_month_cost,
                    "current_month_name": curr_start.strftime("%B %Y"),
                    "last_month_name": last_start.strftime("%B %Y"),
                    "active_agents": active_agents,
                    # Include stats fields
                    "total_input_tokens": agg_data["total_input_tokens"],
                    "total_output_tokens": agg_data["total_output_tokens"],
                    "total_cache_read": agg_data.get("total_cache_read", 0),
                    "request_count": len(agg_data["rows"]),
                    "by_model": dict(agg_data["by_model"]),
                    "by_kind": dict(agg_data["by_kind"]),
                    "by_phase": dict(agg_data["by_phase"]),
                    "by_prd": dict(agg_data["by_prd"]),
                    "by_agent": dict(agg_data["by_agent"]),
                }
                output_manager.emit_server_message("stats_result", data)
                return

            click.echo("\n--- Cursor Usage & Cost Summary ---")
            click.echo(f"Total Project Cost:   ${total_cost:.4f} USD")
            click.echo(f"Cost {curr_start.strftime('%B %Y')}:      ${current_month_cost:.4f} USD")
            click.echo(f"Cost {last_start.strftime('%B %Y')}:     ${last_month_cost:.4f} USD")
            
            # Show recent aggregation info if not report or download
            files = list_usage_files(COSTS_DIR)
            if files:
                agg_data = aggregate_usage_data(files[:7]) # Last 7 files for quick tokens view
                total_tokens = agg_data["total_input_tokens"] + agg_data["total_output_tokens"]
                click.echo(f"Tokens (recent):      {total_tokens:,}")
            
            click.echo(f"\nDetailed log: {COSTS_DIR}/usage.csv")
            click.echo("Use 'vibe usage --report' for full breakdown.")
            return

        # Summary for a specific range
        cost_range = get_cost_for_period(start, end)
        
        if server_mode:
            from vibe_tools.command_output import output_manager
            
            # For the UI (StatsView), we need detailed stats
            files = list_usage_files(COSTS_DIR)
            data = aggregate_usage_data(files, start, end)
            
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
            return

        click.echo(f"\n--- Cursor Usage Summary ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}) ---")
        click.echo(f"Total Cost for Period: ${cost_range:.4f} USD")
        
        files = list_usage_files(COSTS_DIR)
        if files:
            agg_data = aggregate_usage_data(files, start, end)
            total_tokens = agg_data["total_input_tokens"] + agg_data["total_output_tokens"]
            click.echo(f"Total Tokens:         {total_tokens:,}")
            click.echo(f"Total Requests:       {len(agg_data['rows']):,}")

    cli.add_command(usage)
