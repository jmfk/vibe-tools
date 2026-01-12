import csv
import datetime
import pathlib
from typing import Any, Dict, List, Optional, Tuple

from vibe_tools.utils import COSTS_DIR, logger

# Pricing per 1M tokens (USD)
# Source: Standard LLM pricing as of late 2024 / early 2025
PRICING = {
    "gemini-3-flash": {"input": 0.1, "output": 0.4},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.3},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
}

AGENT_DEFAULT_MODEL = {
    "cursor-agent": "gemini-3-flash",
    "claude": "claude-3-5-sonnet",
    "antigravity": "gpt-4o",
}

DEFAULT_PRICING = {"input": 1.0, "output": 1.0}  # Fallback
USAGE_LOG_CSV = COSTS_DIR / "usage.csv"

# Track runs in the current session for final reporting
_session_runs: List[Dict[str, Any]] = []


class CostLogger:
    def __init__(self, config_data: dict):
        self.config = config_data
        self.google_sheet_id = config_data.get("google_sheet_id")
        self.use_google_sheets = config_data.get("use_google_sheets", False)
        self.enabled_google = self.use_google_sheets and bool(self.google_sheet_id)

    def estimate_tokens(self, text: str) -> int:
        """Estimates token count (~4 chars per token)."""
        if not text:
            return 0
        return len(text) // 4

    def calculate_cost(
        self, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        pricing = PRICING.get(model, DEFAULT_PRICING)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def log_run(
        self,
        agent: str,
        model: str,
        prompt: str,
        output: str,
        prd_name: str = "N/A",
        iteration: int = 1,
        phase: str = "N/A",
        purpose: str = "N/A",
    ):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        input_tokens = self.estimate_tokens(prompt)
        output_tokens = self.estimate_tokens(output)
        cost = self.calculate_cost(model, input_tokens, output_tokens)

        row = [
            timestamp,
            prd_name,
            phase,
            str(iteration),
            agent,
            model,
            str(input_tokens),
            str(output_tokens),
            f"{cost:.6f}",
            purpose,
        ]

        # Track for session report
        _session_runs.append(
            {
                "timestamp": timestamp,
                "prd": prd_name,
                "phase": phase,
                "iteration": iteration,
                "agent": agent,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "purpose": purpose,
            }
        )

        # Continuous reporting to console
        logger.info(f"💰 Step Cost: ${cost:.6f} USD (Model: {model}, Phase: {phase})")

        # 1. Local Sink (CSV)
        self._log_to_csv(row)

        # 2. Google Sink (Google Sheets)
        if self.enabled_google:
            self._log_to_google(row)

    def _log_to_csv(self, row):
        file_exists = USAGE_LOG_CSV.exists()
        header = [
            "Timestamp",
            "PRD",
            "Phase",
            "Iteration",
            "Agent",
            "Model",
            "Input Tokens",
            "Output Tokens",
            "Cost (USD)",
            "Purpose",
        ]

        # Check if we need to write a new header due to column change
        write_header = not file_exists
        if file_exists:
            try:
                with open(USAGE_LOG_CSV, newline="") as f:
                    reader = csv.reader(f)
                    first_row = next(reader, None)
                    if first_row and len(first_row) != len(header):
                        write_header = True
            except Exception:
                pass

        with open(USAGE_LOG_CSV, mode="a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                # If file exists but we need a new header, add a separator
                if file_exists:
                    f.write("\n")
                writer.writerow(header)
            writer.writerow(row)

    def _log_to_google(self, row):
        from vibe_tools.utils import logger

        try:
            import gspread

            authorized_user_path = pathlib.Path(".vibe_authorized_user.json")
            creds_path = pathlib.Path(".vibe_google_creds.json")

            # 1. Try OAuth2 (Browser Login) first
            if authorized_user_path.exists():
                client_secrets_path = pathlib.Path(".vibe_client_secrets.json")
                if client_secrets_path.exists():
                    gc = gspread.oauth(
                        credentials_filename=str(client_secrets_path),
                        authorized_user_filename=str(authorized_user_path),
                    )
                else:
                    # gspread might still work with just authorized_user if already logged in
                    gc = gspread.oauth(
                        authorized_user_filename=str(authorized_user_path)
                    )
            # 2. Fallback to Service Account
            elif creds_path.exists():
                gc = gspread.service_account(filename=str(creds_path))
            else:
                logger.warning(
                    "⚠️ Google Sheets logging enabled but no credentials found (.vibe_authorized_user.json or .vibe_google_creds.json). Run 'vibe config google'."
                )
                return

            if not self.google_sheet_id:
                return

            try:
                sh = gc.open_by_key(self.google_sheet_id)
            except gspread.exceptions.APIError as e:
                # If 404, try opening by name instead
                if hasattr(e, "response") and e.response.status_code == 404:
                    sh = gc.open(self.google_sheet_id)
                else:
                    raise
            except gspread.exceptions.SpreadsheetNotFound:
                # Some versions/configurations might raise SpreadsheetNotFound
                sh = gc.open(self.google_sheet_id)

            worksheet = sh.get_worksheet(0)
            worksheet.append_row(row)
        except Exception as e:
            logger.warning(
                f"⚠️ Failed to log to Google Sheets: {e}. Logging locally to CSV instead."
            )


def get_total_cost():
    if not USAGE_LOG_CSV.exists():
        return 0.0

    total = 0.0
    try:
        with open(USAGE_LOG_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += float(row.get("Cost (USD)", 0.0))
    except Exception:
        pass
    return total


def get_session_cost():
    """Returns the total cost incurred in the current execution session."""
    return sum(run["cost"] for run in _session_runs)


def finalize_cost_report():
    """Aggregates session costs and writes a summary to the log and terminal."""
    if not _session_runs:
        return

    total_cost = sum(run["cost"] for run in _session_runs)

    # Format detailed table for log file
    report_lines = [
        "\n" + "=" * 80,
        "SESSION COST REPORT",
        "=" * 80,
        f"{'PRD':<20} {'Phase':<10} {'Iter':<5} {'Model':<20} {'Cost (USD)':<10}",
        "-" * 80,
    ]

    for run in _session_runs:
        report_lines.append(
            f"{run['prd'][:19]:<20} {run['phase'][:9]:<10} {run['iteration']:<5} "
            f"{run['model'][:19]:<20} ${run['cost']:>9.6f}"
        )

    report_lines.append("-" * 80)
    report_lines.append(f"{'TOTAL SESSION COST:':<56} ${total_cost:>9.6f}")
    report_lines.append("=" * 80 + "\n")

    report = "\n".join(report_lines)

    # Log the full report to the log file (DEBUG level ensures it goes to file)
    logger.debug(report)

    # Print total cost to terminal
    import click

    click.echo(f"\n✅ Command completed. Total session cost: ${total_cost:.6f} USD")
