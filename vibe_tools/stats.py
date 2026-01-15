import base64
import csv
import datetime
import io
import pathlib
import re
import time
import sys
import webbrowser
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import click
import requests

from vibe_tools.utils import COSTS_DIR, logger, get_cursor_api_key


def download_and_process_usage(backtrack: int = 1, agent_name: str = "cursor-agent"):
    """Download usage CSV and process it."""
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=backtrack)

    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)

    from vibe_tools.utils import get_cursor_api_key

    api_key = get_cursor_api_key()

    if api_key:
        try:
            logger.info(f"📊 Fetching usage events via API...")
            csv_content = fetch_usage_events_csv(api_key, start_date, end_date)
            process_usage_csv(csv_content, agent_name)
            return True
        except Exception as e:
            logger.error(f"❌ API download failed: {e}")
            # Fallback to browser method if API fails

    url = f"https://cursor.com/api/dashboard/export-usage-events-csv?startDate={start_ms}&endDate={end_ms}&strategy=tokens"

    server_mode = "--server" in sys.argv
    if not server_mode:
        click.echo(
            f"\n📊 To get usage for the last {backtrack} day(s), download the CSV manually. Download to ~/Downloads folder:"
        )
        click.echo(f"🔗 {url}")

    downloads_dir = pathlib.Path.home() / "Downloads"
    # Snapshot existing files to detect the NEW one
    existing_files = set(downloads_dir.glob("usage-events-*.csv"))

    webbrowser.open(url)

    # Monitor Downloads folder
    if not server_mode:
        click.echo(f"⏳ Monitoring {downloads_dir} for NEW download (timeout 2m)...")

    start_wait = time.time()
    found_file = None

    while time.time() - start_wait < 120:
        current_files = set(downloads_dir.glob("usage-events-*.csv"))
        new_files = current_files - existing_files

        if new_files:
            # Pick the most recently modified one among the new ones
            found_file = max(new_files, key=lambda p: p.stat().st_mtime)
            break

        time.sleep(2)

    if not found_file:
        if not server_mode:
            click.echo("❌ Timeout: Downloaded file not found in Downloads folder.")
        return False

    if not server_mode:
        click.echo(f"✅ Found downloaded file: {found_file}")

    try:
        csv_content = found_file.read_text(encoding="utf-8")
        process_usage_csv(csv_content, agent_name)

        # Delete the original downloaded file to keep Downloads clean
        if found_file.exists():
            found_file.unlink()
            if not server_mode:
                click.echo(f"🗑️ Removed source file: {found_file}")
        return True
    except Exception as e:
        if not server_mode:
            click.echo(f"❌ Error processing file: {e}")
        return False


def process_usage_csv(csv_content: str, agent_name: str = "cursor-agent"):
    """Process usage CSV content, grouping by date and saving to COSTS_DIR."""
    f = io.StringIO(csv_content)
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = reader.fieldnames

    rows_by_date = {}
    for row in rows:
        # Cursor CSV has "Date" or "date" column
        date_val = row.get("Date") or row.get("date")
        if date_val:
            # Ensure date_str is just YYYY-MM-DD regardless of format (ISO or space)
            clean_date = date_val.split("T")[0].split(" ")[0]
            if clean_date not in rows_by_date:
                rows_by_date[clean_date] = []
            rows_by_date[clean_date].append(row)

    # Fallback to today if no date column found
    if not rows_by_date:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        rows_by_date[date_str] = rows

    COSTS_DIR.mkdir(parents=True, exist_ok=True)

    for clean_date, d_rows in rows_by_date.items():
        target_filename = f"{agent_name}-{clean_date}.log"
        target_path = COSTS_DIR / target_filename

        # Re-serialize to CSV for this day
        out_f = io.StringIO()
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(d_rows)

        target_path.write_text(out_f.getvalue(), encoding="utf-8")
        click.echo(f"💾 Usage saved for {clean_date}: {target_path}")


def list_usage_files(costs_dir: pathlib.Path) -> List[pathlib.Path]:
    """List all CSV and .log files in costs directory, sorted by date (latest first)."""
    if not costs_dir.exists():
        return []

    files = []
    for ext in ["*.csv", "*.log"]:
        files.extend(list(costs_dir.glob(ext)))

    files.sort(key=lambda p: _extract_date_from_file(p), reverse=True)
    return files


def get_date_range(period: str) -> Tuple[datetime.datetime, datetime.datetime]:
    """Calculate start and end dates for a given period."""
    now = datetime.datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "month":
        start = today.replace(day=1)
        return start, now
    elif period == "prev-month":
        last_month_end = today.replace(day=1) - datetime.timedelta(days=1)
        start = last_month_end.replace(day=1)
        return start, last_month_end.replace(hour=23, minute=59, second=59)
    elif period == "3-months":
        start = today - datetime.timedelta(days=90)
        return start, now
    elif period == "6-months":
        start = today - datetime.timedelta(days=180)
        return start, now
    elif period == "year":
        start = today - datetime.timedelta(days=365)
        return start, now
    elif period == "all":
        return datetime.datetime.min, now
    else:
        # Default to last 7 days if unknown
        start = today - datetime.timedelta(days=7)
        return start, now


def aggregate_usage_data(
    files: List[pathlib.Path],
    start_date: Optional[datetime.datetime] = None,
    end_date: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """Parse and merge data from multiple CSV/log files within a date range."""
    aggregated: Dict[str, Any] = {
        "rows": [],
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_read": 0,
        "by_model": defaultdict(
            lambda: {
                "count": 0,
                "cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read": 0,
            }
        ),
        "by_kind": defaultdict(lambda: {"count": 0, "cost": 0.0}),
        "by_phase": defaultdict(
            lambda: {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        ),
        "by_prd": defaultdict(
            lambda: {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        ),
        "by_agent": defaultdict(
            lambda: {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        ),
    }

    for file_path in files:
        file_date = _extract_date_from_file(file_path)
        if start_date and file_date < start_date:
            continue
        if end_date and file_date > end_date:
            continue

        fmt = detect_csv_format(file_path)
        if fmt == "usage":
            data = parse_usage_csv(file_path)
            _merge_usage_data(aggregated, data)
        elif fmt == "usage-events" or file_path.suffix == ".log":
            # .log files are generated by vibe usage and follow usage-events structure
            data = parse_usage_events_csv(file_path)
            _merge_usage_events_data(aggregated, data)

    return aggregated


def _merge_usage_data(target: Dict[str, Any], source: Dict[str, Any]):
    target["rows"].extend(source["rows"])
    target["total_cost"] += source["total_cost"]
    target["total_input_tokens"] += source.get("total_input_tokens", 0)
    target["total_output_tokens"] += source.get("total_output_tokens", 0)

    for key in ["by_phase", "by_model", "by_prd", "by_agent"]:
        if key in source:
            for subkey, stats in source[key].items():
                t = target[key][subkey]
                t["count"] += stats["count"]
                t["cost"] += stats["cost"]
                t["input_tokens"] += stats.get("input_tokens", 0)
                t["output_tokens"] += stats.get("output_tokens", 0)


def _merge_usage_events_data(target: Dict[str, Any], source: Dict[str, Any]):
    target["rows"].extend(source["rows"])
    target["total_cost"] += source["total_cost"]
    target["total_input_tokens"] += source.get("total_input_tokens", 0)
    target["total_output_tokens"] += source.get("total_output_tokens", 0)
    target["total_cache_read"] += source.get("total_cache_read", 0)

    for key in ["by_model", "by_kind"]:
        if key in source:
            for subkey, stats in source[key].items():
                t = target[key][subkey]
                t["count"] += stats["count"]
                t["cost"] += stats["cost"]
                if "input_tokens" in stats:
                    t["input_tokens"] += stats["input_tokens"]
                if "output_tokens" in stats:
                    t["output_tokens"] += stats["output_tokens"]
                if "cache_read" in stats:
                    t["cache_read"] += stats["cache_read"]


def _extract_date_from_file(file_path: pathlib.Path) -> datetime.datetime:
    """Extract date from filename, defaulting to file modification time if not found."""
    # Try to extract date from filename like "usage-events-2026-01-06.csv"
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)
    if date_match:
        try:
            return datetime.datetime.strptime(date_match.group(1), "%Y-%m-%d")
        except ValueError:
            pass

    # Fallback to file modification time
    if file_path.exists():
        return datetime.datetime.fromtimestamp(file_path.stat().st_mtime)

    return datetime.datetime.min


def detect_csv_format(file_path: pathlib.Path) -> str:
    """Detect the format of the CSV file."""
    with open(file_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return "unknown"

        header_str = ",".join(header).lower()

        if "date" in header_str and "kind" in header_str and "model" in header_str:
            return "usage-events"
        elif (
            "timestamp" in header_str and "prd" in header_str and "phase" in header_str
        ):
            return "usage"
        else:
            return "unknown"


def parse_usage_csv(file_path: pathlib.Path) -> Dict[str, Any]:
    """Parse usage.csv format."""
    data: Dict[str, Any] = {
        "rows": [],
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "by_phase": defaultdict(
            lambda: {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        ),
        "by_model": defaultdict(
            lambda: {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        ),
        "by_prd": defaultdict(
            lambda: {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        ),
        "by_agent": defaultdict(
            lambda: {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        ),
    }

    with open(file_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                cost = float(row.get("Cost (USD)", 0.0))
                input_tokens = int(row.get("Input Tokens", 0))
                output_tokens = int(row.get("Output Tokens", 0))
                phase = row.get("Phase", "N/A")
                model = row.get("Model", "N/A")
                prd = row.get("PRD", "N/A")
                agent = row.get("Agent", "N/A")

                data["rows"].append(row)
                data["total_cost"] += cost
                data["total_input_tokens"] += input_tokens
                data["total_output_tokens"] += output_tokens

                data["by_phase"][phase]["count"] += 1
                data["by_phase"][phase]["cost"] += cost
                data["by_phase"][phase]["input_tokens"] += input_tokens
                data["by_phase"][phase]["output_tokens"] += output_tokens

                data["by_model"][model]["count"] += 1
                data["by_model"][model]["cost"] += cost
                data["by_model"][model]["input_tokens"] += input_tokens
                data["by_model"][model]["output_tokens"] += output_tokens

                data["by_prd"][prd]["count"] += 1
                data["by_prd"][prd]["cost"] += cost
                data["by_prd"][prd]["input_tokens"] += input_tokens
                data["by_prd"][prd]["output_tokens"] += output_tokens

                data["by_agent"][agent]["count"] += 1
                data["by_agent"][agent]["cost"] += cost
                data["by_agent"][agent]["input_tokens"] += input_tokens
                data["by_agent"][agent]["output_tokens"] += output_tokens
            except (ValueError, KeyError):
                continue

    return data


def parse_usage_events_csv(file_path: pathlib.Path) -> Dict[str, Any]:
    """Parse usage-events CSV format."""
    data: Dict[str, Any] = {
        "rows": [],
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_read": 0,
        "by_model": defaultdict(
            lambda: {
                "count": 0,
                "cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read": 0,
            }
        ),
        "by_kind": defaultdict(lambda: {"count": 0, "cost": 0.0}),
    }

    with open(file_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                cost_str = row.get("Cost", "0").replace(",", "")
                cost = float(cost_str) if cost_str else 0.0

                # Handle different input token columns
                input_with_cache = int(row.get("Input (w/ Cache Write)", 0) or 0)
                input_without_cache = int(row.get("Input (w/o Cache Write)", 0) or 0)
                cache_read = int(row.get("Cache Read", 0) or 0)
                output_tokens = int(row.get("Output Tokens", 0) or 0)

                total_input = input_with_cache + input_without_cache

                model = row.get("Model", "N/A")
                kind = row.get("Kind", "N/A")

                # Only count included rows
                if "Included" in kind:
                    data["rows"].append(row)
                    data["total_cost"] += cost
                    data["total_input_tokens"] += total_input
                    data["total_output_tokens"] += output_tokens
                    data["total_cache_read"] += cache_read

                    data["by_model"][model]["count"] += 1
                    data["by_model"][model]["cost"] += cost
                    data["by_model"][model]["input_tokens"] += total_input
                    data["by_model"][model]["output_tokens"] += output_tokens
                    data["by_model"][model]["cache_read"] += cache_read

                    data["by_kind"][kind]["count"] += 1
                    data["by_kind"][kind]["cost"] += cost
            except (ValueError, KeyError):
                continue

    return data


def cursor_api_request(
    method: str, endpoint: str, api_key: str, data: Optional[Dict] = None
) -> Dict[str, Any]:
    """Make a request to the Cursor API."""
    url = f"https://api.cursor.com{endpoint}"
    auth = base64.b64encode(f"{api_key}:".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }

    if method == "GET":
        response = requests.get(url, headers=headers, params=data)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    elif method == "PATCH":
        response = requests.patch(url, headers=headers, json=data)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")

    response.raise_for_status()
    if response.status_code == 204:
        return {}
    return response.json()


def fetch_daily_usage_data(
    api_key: str, start_date: datetime.datetime, end_date: datetime.datetime
) -> Dict[str, Any]:
    """Fetch daily usage data from Cursor API."""
    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)
    return cursor_api_request(
        "POST",
        "/teams/daily-usage-data",
        api_key,
        {
            "startDate": start_ms,
            "endDate": end_ms,
        },
    )


def fetch_usage_events_csv(
    api_key: str, start_date: datetime.datetime, end_date: datetime.datetime
) -> str:
    """Fetch usage events CSV from Cursor."""
    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)

    url = f"https://cursor.com/api/dashboard/export-usage-events-csv?startDate={start_ms}&endDate={end_ms}&strategy=tokens"

    auth = base64.b64encode(f"{api_key}:".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def fetch_spending_data(
    api_key: str, search_term: Optional[str] = None, page: int = 1, page_size: int = 100
) -> Dict[str, Any]:
    """Fetch spending data from Cursor API."""
    data: Dict[str, Any] = {"page": page, "pageSize": page_size}
    if search_term:
        data["searchTerm"] = search_term
    return cursor_api_request("POST", "/teams/spend", api_key, data)


def fetch_usage_events(
    api_key: str,
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    email: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> Dict[str, Any]:
    """Fetch usage events from Cursor API."""
    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)
    data: Dict[str, Any] = {
        "startDate": start_ms,
        "endDate": end_ms,
        "page": page,
        "pageSize": page_size,
    }
    if email:
        data["email"] = email
    return cursor_api_request("POST", "/teams/filtered-usage-events", api_key, data)


def list_billing_groups(
    api_key: str, billing_cycle: Optional[str] = None
) -> Dict[str, Any]:
    """List all billing groups."""
    params = {}
    if billing_cycle:
        params["billingCycle"] = billing_cycle
    return cursor_api_request("GET", "/teams/groups", api_key, params)


def get_billing_group(
    api_key: str, group_id: str, billing_cycle: Optional[str] = None
) -> Dict[str, Any]:
    """Get a specific billing group."""
    params = {}
    if billing_cycle:
        params["billingCycle"] = billing_cycle
    return cursor_api_request("GET", f"/teams/groups/{group_id}", api_key, params)


def create_billing_group(api_key: str, name: str) -> Dict[str, Any]:
    """Create a new billing group."""
    return cursor_api_request("POST", "/teams/groups", api_key, {"name": name})


def update_billing_group(
    api_key: str,
    group_id: str,
    name: Optional[str] = None,
    directory_group_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Update a billing group."""
    data = {}
    if name is not None:
        data["name"] = name
    if directory_group_id is not None:
        data["directoryGroupId"] = directory_group_id
    return cursor_api_request("PATCH", f"/teams/groups/{group_id}", api_key, data)


def delete_billing_group(api_key: str, group_id: str):
    """Delete a billing group."""
    cursor_api_request("DELETE", f"/teams/groups/{group_id}", api_key)


def add_members_to_group(
    api_key: str, group_id: str, user_ids: List[str]
) -> Dict[str, Any]:
    """Add members to a billing group."""
    return cursor_api_request(
        "POST", f"/teams/groups/{group_id}/members", api_key, {"userIds": user_ids}
    )


def remove_members_from_group(
    api_key: str, group_id: str, user_ids: List[str]
) -> Dict[str, Any]:
    """Remove members from a billing group."""
    return cursor_api_request(
        "DELETE", f"/teams/groups/{group_id}/members", api_key, {"userIds": user_ids}
    )


def parse_api_usage_events(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse usage events from API response."""
    data: Dict[str, Any] = {
        "rows": [],
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_read": 0,
        "by_model": defaultdict(
            lambda: {
                "count": 0,
                "cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read": 0,
            }
        ),
        "by_kind": defaultdict(lambda: {"count": 0, "cost": 0.0}),
        "by_user": defaultdict(
            lambda: {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        ),
    }

    events = api_data.get("usageEvents", [])
    for event in events:
        try:
            token_usage = event.get("tokenUsage", {})
            input_tokens = token_usage.get("inputTokens", 0)
            output_tokens = token_usage.get("outputTokens", 0)
            cache_read = token_usage.get("cacheReadTokens", 0)
            # cache_write = token_usage.get("cacheWriteTokens", 0)
            model_cost_cents = token_usage.get("totalCents", 0.0)
            cursor_token_fee = event.get("cursorTokenFee", 0.0)
            total_cost = (model_cost_cents + cursor_token_fee) / 100.0

            model = event.get("model", "N/A")
            kind = event.get("kind", "N/A")
            user_email = event.get("userEmail", "N/A")

            data["rows"].append(event)
            data["total_cost"] += total_cost
            data["total_input_tokens"] += input_tokens
            data["total_output_tokens"] += output_tokens
            data["total_cache_read"] += cache_read

            data["by_model"][model]["count"] += 1
            data["by_model"][model]["cost"] += total_cost
            data["by_model"][model]["input_tokens"] += input_tokens
            data["by_model"][model]["output_tokens"] += output_tokens
            data["by_model"][model]["cache_read"] += cache_read

            data["by_kind"][kind]["count"] += 1
            data["by_kind"][kind]["cost"] += total_cost

            data["by_user"][user_email]["count"] += 1
            data["by_user"][user_email]["cost"] += total_cost
            data["by_user"][user_email]["input_tokens"] += input_tokens
            data["by_user"][user_email]["output_tokens"] += output_tokens
        except (ValueError, KeyError):
            continue

    return data


def parse_api_daily_usage(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse daily usage data from API response."""
    data: Dict[str, Any] = {
        "rows": [],
        "total_cost": 0.0,
        "by_user": defaultdict(
            lambda: {
                "count": 0,
                "cost": 0.0,
                "total_lines_added": 0,
                "total_lines_deleted": 0,
            }
        ),
        "by_model": defaultdict(lambda: {"count": 0}),
    }

    daily_data = api_data.get("data", [])
    for day in daily_data:
        data["rows"].append(day)
        email = day.get("email", "N/A")
        data["by_user"][email]["count"] += 1
        data["by_user"][email]["total_lines_added"] += day.get("totalLinesAdded", 0)
        data["by_user"][email]["total_lines_deleted"] += day.get("totalLinesDeleted", 0)

        model = day.get("mostUsedModel", "N/A")
        data["by_model"][model]["count"] += 1

    return data


def generate_markdown_report(
    file_path: Optional[pathlib.Path],
    data: Dict[str, Any],
    format_type: str,
    source: str = "file",
) -> str:
    """Generate markdown report with statistics and tables."""
    lines = []
    lines.append("# Usage Statistics Report")
    lines.append("")
    if file_path:
        lines.append(f"**Source:** `{file_path.name}` ({source})")
    else:
        lines.append(f"**Source:** Cursor API ({source})")
    lines.append(
        f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary Statistics
    lines.append("## Summary Statistics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Cost (USD) | ${data['total_cost']:.4f} |")
    if "total_input_tokens" in data:
        lines.append(f"| Total Input Tokens | {data['total_input_tokens']:,} |")
        lines.append(f"| Total Output Tokens | {data['total_output_tokens']:,} |")
        total_tokens = data["total_input_tokens"] + data["total_output_tokens"]
        lines.append(f"| Total Tokens | {total_tokens:,} |")
    if "total_cache_read" in data:
        lines.append(f"| Total Cache Read Tokens | {data['total_cache_read']:,} |")
    lines.append(f"| Total Requests | {len(data['rows']):,} |")
    if len(data["rows"]) > 0:
        avg_cost = data["total_cost"] / len(data["rows"])
        lines.append(f"| Average Cost per Request | ${avg_cost:.6f} |")
    lines.append("")

    # By Model
    if data.get("by_model"):
        lines.append("## Statistics by Model")
        lines.append("")
        if "input_tokens" in next(iter(data["by_model"].values()), {}):
            lines.append(
                "| Model | Requests | Cost (USD) | Input Tokens | Output Tokens | Avg Cost/Req |"
            )
            lines.append(
                "|-------|----------|------------|--------------|---------------|--------------|"
            )
            for model in sorted(
                data["by_model"].keys(),
                key=lambda m: data["by_model"][m].get("cost", 0),
                reverse=True,
            ):
                stats = data["by_model"][model]
                avg = stats["cost"] / stats["count"] if stats["count"] > 0 else 0
                lines.append(
                    f"| {model} | {stats['count']:,} | ${stats.get('cost', 0):.4f} | "
                    f"{stats.get('input_tokens', 0):,} | {stats.get('output_tokens', 0):,} | ${avg:.6f} |"
                )
        else:
            lines.append("| Model | Days Used |")
            lines.append("|-------|-----------|")
            for model in sorted(
                data["by_model"].keys(),
                key=lambda m: data["by_model"][m]["count"],
                reverse=True,
            ):
                stats = data["by_model"][model]
                lines.append(f"| {model} | {stats['count']:,} |")
        lines.append("")

    # By User
    if data.get("by_user"):
        lines.append("## Statistics by User")
        lines.append("")
        if "input_tokens" in next(iter(data["by_user"].values()), {}):
            lines.append(
                "| User | Requests | Cost (USD) | Input Tokens | Output Tokens | Avg Cost/Req |"
            )
            lines.append(
                "|------|----------|------------|--------------|---------------|--------------|"
            )
            for user in sorted(
                data["by_user"].keys(),
                key=lambda u: data["by_user"][u].get("cost", 0),
                reverse=True,
            ):
                stats = data["by_user"][user]
                avg = stats["cost"] / stats["count"] if stats["count"] > 0 else 0
                lines.append(
                    f"| {user} | {stats['count']:,} | ${stats.get('cost', 0):.4f} | "
                    f"{stats.get('input_tokens', 0):,} | {stats.get('output_tokens', 0):,} | ${avg:.6f} |"
                )
        else:
            lines.append("| User | Days Active | Lines Added | Lines Deleted |")
            lines.append("|------|-------------|--------------|---------------|")
            for user in sorted(
                data["by_user"].keys(),
                key=lambda u: data["by_user"][u]["count"],
                reverse=True,
            ):
                stats = data["by_user"][user]
                lines.append(
                    f"| {user} | {stats['count']:,} | {stats.get('total_lines_added', 0):,} | "
                    f"{stats.get('total_lines_deleted', 0):,} |"
                )
        lines.append("")

    # By Phase (for usage.csv format)
    if data.get("by_phase"):
        lines.append("## Statistics by Phase")
        lines.append("")
        lines.append(
            "| Phase | Requests | Cost (USD) | Input Tokens | Output Tokens | Avg Cost/Req |"
        )
        lines.append(
            "|-------|----------|------------|--------------|---------------|--------------|"
        )
        for phase in sorted(
            data["by_phase"].keys(),
            key=lambda p: data["by_phase"][p]["cost"],
            reverse=True,
        ):
            stats = data["by_phase"][phase]
            avg = stats["cost"] / stats["count"] if stats["count"] > 0 else 0
            lines.append(
                f"| {phase} | {stats['count']:,} | ${stats['cost']:.4f} | "
                f"{stats['input_tokens']:,} | {stats['output_tokens']:,} | ${avg:.6f} |"
            )
        lines.append("")

    # By PRD (for usage.csv format)
    if data.get("by_prd"):
        lines.append("## Top 20 PRDs by Cost")
        lines.append("")
        lines.append(
            "| PRD | Requests | Cost (USD) | Input Tokens | Output Tokens | Avg Cost/Req |"
        )
        lines.append(
            "|-----|----------|------------|--------------|---------------|--------------|"
        )
        sorted_prds = sorted(
            data["by_prd"].keys(), key=lambda p: data["by_prd"][p]["cost"], reverse=True
        )[:20]
        for prd in sorted_prds:
            stats = data["by_prd"][prd]
            avg = stats["cost"] / stats["count"] if stats["count"] > 0 else 0
            lines.append(
                f"| {prd} | {stats['count']:,} | ${stats['cost']:.4f} | "
                f"{stats['input_tokens']:,} | {stats['output_tokens']:,} | ${avg:.6f} |"
            )
        lines.append("")

    # By Agent (for usage.csv format)
    if data.get("by_agent"):
        lines.append("## Statistics by Agent")
        lines.append("")
        lines.append(
            "| Agent | Requests | Cost (USD) | Input Tokens | Output Tokens | Avg Cost/Req |"
        )
        lines.append(
            "|-------|----------|------------|--------------|---------------|--------------|"
        )
        for agent in sorted(
            data["by_agent"].keys(),
            key=lambda a: data["by_agent"][a]["cost"],
            reverse=True,
        ):
            stats = data["by_agent"][agent]
            avg = stats["cost"] / stats["count"] if stats["count"] > 0 else 0
            lines.append(
                f"| {agent} | {stats['count']:,} | ${stats['cost']:.4f} | "
                f"{stats['input_tokens']:,} | {stats['output_tokens']:,} | ${avg:.6f} |"
            )
        lines.append("")

    # By Kind (for usage-events format)
    if data.get("by_kind"):
        lines.append("## Statistics by Kind")
        lines.append("")
        lines.append("| Kind | Requests | Cost (USD) | Avg Cost/Req |")
        lines.append("|------|----------|------------|--------------|")
        for kind in sorted(
            data["by_kind"].keys(),
            key=lambda k: data["by_kind"][k]["cost"],
            reverse=True,
        ):
            stats = data["by_kind"][kind]
            avg = stats["cost"] / stats["count"] if stats["count"] > 0 else 0
            lines.append(
                f"| {kind} | {stats['count']:,} | ${stats['cost']:.4f} | ${avg:.6f} |"
            )
        lines.append("")

    # Cost Distribution Chart (ASCII)
    if data.get("by_model") and "cost" in next(iter(data["by_model"].values()), {}):
        lines.append("## Cost Distribution by Model")
        lines.append("")
        lines.append("```")
        max_cost = (
            max(s.get("cost", 0) for s in data["by_model"].values())
            if data["by_model"]
            else 1
        )
        for model in sorted(
            data["by_model"].keys(),
            key=lambda m: data["by_model"][m].get("cost", 0),
            reverse=True,
        ):
            stats = data["by_model"][model]
            cost = stats.get("cost", 0)
            bar_length = int((cost / max_cost) * 50) if max_cost > 0 else 0
            bar = "█" * bar_length
            lines.append(f"{model[:30]:<30} |{bar} ${cost:.4f}")
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def generate_billing_groups_report(groups_data: Dict[str, Any]) -> str:
    """Generate markdown report for billing groups."""
    lines = []
    lines.append("# Billing Groups Report")
    lines.append("")
    lines.append(
        f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    billing_cycle = groups_data.get("billingCycle", {})
    if billing_cycle:
        cycle_start = datetime.datetime.fromtimestamp(
            billing_cycle.get("cycleStart", 0) / 1000
        )
        cycle_end = datetime.datetime.fromtimestamp(
            billing_cycle.get("cycleEnd", 0) / 1000
        )
        lines.append(
            f"**Billing Cycle:** {cycle_start.strftime('%Y-%m-%d')} to {cycle_end.strftime('%Y-%m-%d')}"
        )
        lines.append("")

    lines.append("## Billing Groups")
    lines.append("")
    lines.append("| Group Name | Members | Spend (USD) | Daily Spend Trend |")
    lines.append("|------------|---------|-------------|-------------------|")

    groups = groups_data.get("groups", [])
    for group in groups:
        name = group.get("name", "N/A")
        member_count = group.get("memberCount", 0)
        spend_cents = group.get("spendCents", 0)
        spend_dollars = spend_cents / 100.0

        daily_spend = group.get("dailySpend", [])
        if daily_spend:
            trend = f"{len(daily_spend)} days"
        else:
            trend = "N/A"

        lines.append(f"| {name} | {member_count} | ${spend_dollars:.2f} | {trend} |")

    unassigned = groups_data.get("unassignedGroup")
    if unassigned:
        spend_cents = unassigned.get("spendCents", 0)
        spend_dollars = spend_cents / 100.0
        member_count = unassigned.get("memberCount", 0)
        lines.append(
            f"| {unassigned.get('name', 'Unassigned')} | {member_count} | ${spend_dollars:.2f} | N/A |"
        )

    lines.append("")

    # Detailed group information
    for group in groups:
        lines.append(f"### {group.get('name', 'Unknown Group')}")
        lines.append("")
        lines.append(f"- **ID:** `{group.get('id', 'N/A')}`")
        lines.append(f"- **Type:** {group.get('type', 'N/A')}")
        lines.append(f"- **Members:** {group.get('memberCount', 0)}")
        lines.append(f"- **Spend:** ${group.get('spendCents', 0) / 100.0:.2f}")
        lines.append("")

        current_members = group.get("currentMembers", [])
        if current_members:
            lines.append("#### Current Members")
            lines.append("")
            lines.append("| Name | Email | Spend (USD) |")
            lines.append("|------|-------|-------------|")
            for member in current_members:
                name = member.get("name", "N/A")
                email = member.get("email", "N/A")
                spend_cents = member.get("spendCents", 0)
                spend_dollars = spend_cents / 100.0
                lines.append(f"| {name} | {email} | ${spend_dollars:.2f} |")
            lines.append("")

        daily_spend = group.get("dailySpend", [])
        if daily_spend:
            lines.append("#### Daily Spend Trend")
            lines.append("")
            lines.append("| Date | Spend (USD) |")
            lines.append("|------|-------------|")
            for day in daily_spend[:30]:
                date = day.get("date", "N/A")
                spend_cents = day.get("spendCents", 0)
                spend_dollars = spend_cents / 100.0
                lines.append(f"| {date} | ${spend_dollars:.2f} |")
            lines.append("")

    return "\n".join(lines)


def generate_report(
    file_path: Optional[pathlib.Path],
    reports_dir: pathlib.Path,
    api_data: Optional[Dict[str, Any]] = None,
    source: str = "file",
    data: Optional[Dict[str, Any]] = None,
) -> pathlib.Path:
    """Generate statistics report for a usage file, API data, or pre-aggregated data."""
    reports_dir.mkdir(parents=True, exist_ok=True)

    format_type = "aggregated"
    if data:
        pass  # Use provided data
    elif api_data:
        if "usageEvents" in api_data:
            data = parse_api_usage_events(api_data)
            format_type = "api-usage-events"
        elif "data" in api_data:
            data = parse_api_daily_usage(api_data)
            format_type = "api-daily-usage"
        else:
            raise ValueError("Unknown API data format")
    else:
        if not file_path:
            raise ValueError("Either file_path, api_data or data must be provided")
        format_type = detect_csv_format(file_path)

        if format_type == "usage":
            data = parse_usage_csv(file_path)
        elif format_type == "usage-events":
            data = parse_usage_events_csv(file_path)
        else:
            raise ValueError(f"Unknown CSV format: {format_type}")

    markdown = generate_markdown_report(file_path, data, format_type, source)

    # Generate report filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if file_path:
        report_filename = f"report_{file_path.stem}_{timestamp}.md"
    elif format_type == "aggregated":
        report_filename = f"report_stats_{timestamp}.md"
    else:
        report_filename = f"report_api_{timestamp}.md"
    report_path = reports_dir / report_filename

    report_path.write_text(markdown, encoding="utf-8")

    return report_path
