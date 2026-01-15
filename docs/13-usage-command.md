# Usage Command

The `vibe usage` command provides comprehensive tracking of LLM costs, request statistics, and detailed usage reports. It consolidates previous commands like `cost` and `stats` into a single, unified tool.

## Overview

```bash
vibe usage [OPTIONS]
```

By default, running `vibe usage` without any flags provides a quick overview of the total project cost, cost for the current month, and cost for the previous month.

## Options

### Data Management

*   **`--download`**: Downloads the latest usage data from the Cursor API.
    *   If `CURSOR_API_KEY` is configured, it performs a direct API fetch.
    *   Otherwise, it opens the browser to the Cursor export URL and monitors your `~/Downloads` folder for the exported CSV file.
    *   This operation is non-interactive.

*   **`--file PATH`**: Processes a specific usage CSV file manually downloaded from Cursor.

### Reporting

*   **`--report`**: Generates a detailed Markdown report in the `reports/` directory. The report includes:
    *   Summary statistics (Total cost, tokens, requests).
    *   Breakdown by Model.
    *   Breakdown by Agent.
    *   Cost distribution charts (ASCII).

### Filtering & Date Ranges

You can filter both the quick overview and the generated reports using these flags:

*   **`--days N`**: Number of days to include (default: 7).
*   **`--start-date YYYY-MM-DD`**: Specific start date.
*   **`--end-date YYYY-MM-DD`**: Specific end date.
*   **`--month`**: Use the current month range.
*   **`--prev-month`**: Use the previous month range.
*   **`--last-3-months`**: Use the last 3 months range.
*   **`--last-6-months`**: Use the last 6 months range.
*   **`--year`**: Use the last year range.

## Examples

### View Quick Summary
```bash
vibe usage
```

### Download Recent Usage
```bash
vibe usage --download
```

### Generate a Report for Last Month
```bash
vibe usage --report --prev-month
```

### Generate a Report for a Specific Range
```bash
vibe usage --report --start-date 2026-01-01 --end-date 2026-01-15
```

## Server Mode

When running with the `--server` global flag, `vibe usage` returns JSON-formatted data instead of human-readable text.

### Example Server Call:
```bash
vibe --server usage --month
```

### JSON Response Structure (Quick Summary):
```json
{
  "total_cost": 12.34,
  "current_month_cost": 5.67,
  "last_month_cost": 4.56,
  "current_month_name": "January 2026",
  "last_month_name": "December 2025"
}
```

### JSON Response Structure (Report):
```json
{
  "report_path": "reports/report_stats_20260115_120000.md",
  "total_cost": 1.23,
  "total_input_tokens": 100000,
  "total_output_tokens": 50000,
  "request_count": 150,
  "by_model": { ... },
  "by_agent": { ... }
}
```

## Storage

*   **Local CSV**: All raw data is processed and stored in `implementation/costs/`.
*   **Session Logs**: Individual command costs are still logged in the session log files in `implementation/logs/`.
