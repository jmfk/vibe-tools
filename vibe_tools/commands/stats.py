import datetime
import pathlib
import re
import sys
import traceback

import click

from vibe_tools.stats import (
    aggregate_usage_data,
    fetch_usage_events,
    generate_billing_groups_report,
    generate_report,
    get_date_range,
    list_billing_groups,
    list_usage_files,
)
from vibe_tools.utils import get_cursor_api_key


def register_stats(cli):
    @click.command()
    @click.option(
        "--api", is_flag=True, help="Fetch data from Cursor API instead of local files."
    )
    @click.option("--billing-groups", is_flag=True, help="Show billing groups report.")
    @click.option(
        "--days",
        type=int,
        default=7,
        help="Number of days to fetch from API (default: 7).",
    )
    @click.option("--start-date", help="Start date for API query (YYYY-MM-DD).")
    @click.option("--end-date", help="End date for API query (YYYY-MM-DD).")
    @click.option(
        "--month", "period", flag_value="month", help="Show current month statistics."
    )
    @click.option(
        "--prev-month",
        "period",
        flag_value="prev-month",
        help="Show previous month statistics.",
    )
    @click.option(
        "--last-3-months",
        "period",
        flag_value="3-months",
        help="Show last 3 months statistics.",
    )
    @click.option(
        "--last-6-months",
        "period",
        flag_value="6-months",
        help="Show last 6 months statistics.",
    )
    @click.option(
        "--year", "period", flag_value="year", help="Show last year statistics."
    )
    @click.pass_context
    def stats(ctx, api, billing_groups, days, start_date, end_date, period):
        """Generate statistics report from usage files or Cursor API."""
        reports_dir = pathlib.Path("reports")

        if billing_groups or api:
            api_key = get_cursor_api_key()
            if not api_key:
                click.echo(
                    "❌ CURSOR_API_KEY not found. Set it in .env file or environment."
                )
                click.echo(
                    "   You can get your API key from: https://cursor.com/settings/api-keys"
                )
                return

            if billing_groups:
                try:
                    click.echo("📊 Fetching billing groups...")
                    groups_data = list_billing_groups(api_key)
                    markdown = generate_billing_groups_report(groups_data)

                    reports_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    report_path = reports_dir / f"report_billing_groups_{timestamp}.md"
                    report_path.write_text(markdown, encoding="utf-8")
                    click.echo(f"✅ Billing groups report generated: {report_path}")
                    if "--server" not in sys.argv:
                        click.launch(str(report_path))
                except Exception as e:
                    click.echo(f"❌ Error fetching billing groups: {e}")
                    traceback.print_exc()
                return

            # API data fetching
            try:
                if start_date and end_date:
                    start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                    end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                else:
                    end = datetime.datetime.now()
                    start = end - datetime.timedelta(days=days)

                click.echo(
                    f"📊 Fetching usage events from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}..."
                )

                all_events = []
                page = 1
                while True:
                    api_data = fetch_usage_events(
                        api_key, start, end, page=page, page_size=100
                    )
                    events = api_data.get("usageEvents", [])
                    if not events:
                        break
                    all_events.extend(events)

                    pagination = api_data.get("pagination", {})
                    if not pagination.get("hasNextPage", False):
                        break
                    page += 1

                if not all_events:
                    click.echo("No usage events found for the specified period.")
                    return

                api_data["usageEvents"] = all_events
                report_path = generate_report(
                    None, reports_dir, api_data, source="Cursor API"
                )
                click.echo(f"✅ Report generated: {report_path}")
                if "--server" not in sys.argv:
                    click.launch(str(report_path))
            except Exception as e:
                click.echo(f"❌ Error fetching API data: {e}")
                traceback.print_exc()
            return

        # Local file processing
        from vibe_tools.utils import COSTS_DIR
        stats_dir = COSTS_DIR

        if not stats_dir.exists():
            click.echo(f"❌ Stats directory '{stats_dir}' not found.")
            return

        files = list_usage_files(stats_dir)
        if not files:
            click.echo(f"No CSV or log files found in '{stats_dir}'.")
            return

        if period:
            start, end = get_date_range(period)
            click.echo(
                f"📊 Aggregating usage from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}..."
            )
            data = aggregate_usage_data(files, start, end)

            if not data["rows"]:
                click.echo("No usage data found for the specified period.")
                return

            try:
                report_path = generate_report(
                    None, reports_dir, data=data, source=f"Local Files ({period})"
                )
                click.echo(f"✅ Report generated: {report_path}")

                if "--server" not in sys.argv:
                    click.launch(str(report_path))

                # If in server mode, output the data as JSON
                if "--server" in sys.argv:
                    from vibe_tools.command_output import output_manager

                    # Clean up data for JSON (remove defaultdicts)
                    clean_data = {
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

            except Exception as e:
                click.echo(f"❌ Error generating report: {e}")
                traceback.print_exc()
            return

        click.echo("Available usage files (latest first):")
        for idx, file_path in enumerate(files, start=1):
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)
            if date_match:
                date_str = date_match.group(1)
            else:
                date_str = datetime.datetime.fromtimestamp(
                    file_path.stat().st_mtime
                ).strftime("%Y-%m-%d")
            click.echo(f"  {idx}. {file_path.name} ({date_str})")

        while True:
            try:
                selection = click.prompt(
                    "\nSelect a file to analyze",
                    type=int,
                    default=1,
                )
                if 1 <= selection <= len(files):
                    selected_file = files[selection - 1]
                    break
                click.echo("Invalid selection. Please choose a number from the list.")
            except (ValueError, KeyboardInterrupt):
                click.echo("Aborted.")
                return

        click.echo(f"\n📊 Analyzing {selected_file.name}...")

        try:
            report_path = generate_report(selected_file, reports_dir)
            click.echo(f"✅ Report generated: {report_path}")
            if "--server" not in sys.argv:
                click.launch(str(report_path))
        except Exception as e:
            click.echo(f"❌ Error generating report: {e}")
            traceback.print_exc()

    cli.add_command(stats)
