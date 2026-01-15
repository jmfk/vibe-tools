import datetime
import pathlib
import re
import traceback

import click

from vibe_tools.stats import (
    fetch_usage_events,
    generate_billing_groups_report,
    generate_report,
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
    @click.pass_context
    def stats(ctx, api, billing_groups, days, start_date, end_date):
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
            except Exception as e:
                click.echo(f"❌ Error fetching API data: {e}")
                traceback.print_exc()
            return

        # Local file processing
        stats_dir = pathlib.Path("stats")

        if not stats_dir.exists():
            click.echo(f"❌ Stats directory '{stats_dir}' not found.")
            return

        files = list_usage_files(stats_dir)
        if not files:
            click.echo(f"No CSV files found in '{stats_dir}'.")
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
        except Exception as e:
            click.echo(f"❌ Error generating report: {e}")
            traceback.print_exc()

    cli.add_command(stats)
