import csv
import datetime
import json
import os
import pathlib
from typing import Optional

from vibe_tools.utils import LOGS_DIR

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

DEFAULT_PRICING = {"input": 1.0, "output": 1.0}  # Fallback
USAGE_LOG_CSV = LOGS_DIR / "vibe_usage_log.csv"

class CostLogger:
    def __init__(self, config_data: dict):
        self.config = config_data
        self.google_sheet_id = config_data.get("google_sheet_id")
        self.enabled_google = bool(self.google_sheet_id)

    def estimate_tokens(self, text: str) -> int:
        """Estimates token count (~4 chars per token)."""
        if not text:
            return 0
        return len(text) // 4

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = PRICING.get(model, DEFAULT_PRICING)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def log_run(
        self,
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
            model,
            str(input_tokens),
            str(output_tokens),
            f"{cost:.6f}",
            purpose,
        ]

        # 1. Local Sink (CSV)
        self._log_to_csv(row)

        # 2. Google Sink (Google Sheets)
        if self.enabled_google:
            self._log_to_google(row)

    def _log_to_csv(self, row):
        file_exists = USAGE_LOG_CSV.exists()
        with open(USAGE_LOG_CSV, mode="a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Timestamp", "PRD", "Phase", "Iteration", 
                    "Model", "Input Tokens", "Output Tokens", 
                    "Cost (USD)", "Purpose"
                ])
            writer.writerow(row)

    def _log_to_google(self, row):
        try:
            import gspread
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request

            # Define the scopes
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
            
            creds = None
            token_path = pathlib.Path(".vibe_google_token.json")
            creds_path = pathlib.Path(".vibe_google_creds.json")

            if not creds_path.exists():
                return

            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    return
                
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

            gc = gspread.authorize(creds)
            sh = gc.open_by_key(self.google_sheet_id)
            worksheet = sh.get_worksheet(0)
            worksheet.append_row(row)
        except Exception as e:
            from vibe_tools.utils import logger
            logger.error(f"Failed to log to Google Sheets: {e}")

def get_total_cost():
    if not USAGE_LOG_CSV.exists():
        return 0.0
    
    total = 0.0
    try:
        with open(USAGE_LOG_CSV, mode="r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += float(row.get("Cost (USD)", 0.0))
    except Exception:
        pass
    return total
