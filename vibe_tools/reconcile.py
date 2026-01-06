import csv
import datetime
import pathlib
import sys
from typing import List, Dict, Any, Optional

def parse_iso_timestamp(ts: str) -> Optional[datetime.datetime]:
    """Parse ISO timestamp from Cursor export."""
    try:
        # Cursor format: 2026-01-06T21:37:35.793Z
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def parse_registered_timestamp(ts: str) -> Optional[datetime.datetime]:
    """Parse registered timestamp from usage.csv and convert to UTC."""
    try:
        # usage.csv format: 2026-01-05 20:32:58
        dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        # Assume it's in the system's local timezone
        local_tz = datetime.datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=local_tz)
        # Convert to UTC for comparison
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return None

def normalize_model(model: str) -> str:
    """Normalize model names for comparison."""
    model = model.lower()
    if "gemini-3-flash" in model:
        return "gemini-3-flash"
    if "gemini-3-flash-preview" in model:
        return "gemini-3-flash-preview"
    return model

def reconcile(registered_path: pathlib.Path, exported_path: pathlib.Path):
    registered_events = []
    if registered_path.exists():
        with open(registered_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = parse_registered_timestamp(row["Timestamp"])
                if ts:
                    registered_events.append({
                        "timestamp": ts,
                        "prd": row["PRD"],
                        "model": normalize_model(row["Model"]),
                        "cost": float(row["Cost (USD)"]),
                        "input": int(row["Input Tokens"]),
                        "output": int(row["Output Tokens"]),
                        "matched": False
                    })

    exported_events = []
    if exported_path.exists():
        with open(exported_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = parse_iso_timestamp(row["Date"])
                if ts:
                    exported_events.append({
                        "timestamp": ts,
                        "model": normalize_model(row["Model"]),
                        "cost": float(row["Cost"]),
                        "input": int(row["Input (w/o Cache Write)"]), # Using this as standard input
                        "output": int(row["Output Tokens"]),
                        "kind": row["Kind"],
                        "matched": False
                    })

    # Sort both by timestamp
    registered_events.sort(key=lambda x: x["timestamp"])
    exported_events.sort(key=lambda x: x["timestamp"])

    matches = []
    unmatched_registered = []
    
    # Matching logic: Time window (e.g., 2 minutes) and model name
    time_window = datetime.timedelta(minutes=2)

    for reg in registered_events:
        found_match = False
        for exp in exported_events:
            if exp["matched"]:
                continue
            
            # Check model and time window
            if reg["model"] == exp["model"] and abs(reg["timestamp"] - exp["timestamp"]) <= time_window:
                exp["matched"] = True
                reg["matched"] = True
                matches.append((reg, exp))
                found_match = True
                break
        
        if not found_match:
            unmatched_registered.append(reg)

    unmatched_exported = [exp for exp in exported_events if not exp["matched"]]

    # Print Report
    print("=" * 60)
    print(f"COST RECONCILIATION REPORT")
    print("=" * 60)
    print(f"Registered File: {registered_path}")
    print(f"Exported File:   {exported_path}")
    print("-" * 60)
    
    total_reg_cost = sum(r["cost"] for r in registered_events)
    total_exp_cost = sum(e["cost"] for e in exported_events)
    
    print(f"Total Registered Cost: ${total_reg_cost:.4f}")
    print(f"Total Exported Cost:   ${total_exp_cost:.4f}")
    print(f"Difference:            ${abs(total_reg_cost - total_exp_cost):.4f}")
    print("-" * 60)
    print(f"Total Matches:         {len(matches)}")
    print(f"Unmatched Registered:  {len(unmatched_registered)}")
    print(f"Unmatched Exported:    {len(unmatched_exported)}")
    print("-" * 60)

    if unmatched_registered:
        print("\nUNMATCHED REGISTERED EVENTS (In usage.csv but not in export):")
        for reg in unmatched_registered[:10]:
            print(f"  {reg['timestamp']} | {reg['model']} | ${reg['cost']:.4f} | {reg['prd']}")
        if len(unmatched_registered) > 10:
            print(f"  ... and {len(unmatched_registered) - 10} more")

    if unmatched_exported:
        print("\nUNMATCHED EXPORTED EVENTS (In export but not in usage.csv):")
        for exp in unmatched_exported[:10]:
            print(f"  {exp['timestamp']} | {exp['model']} | ${exp['cost']:.4f} | {exp['kind']}")
        if len(unmatched_exported) > 10:
            print(f"  ... and {len(unmatched_exported) - 10} more")

    print("\nSUMMARY OF DISCREPANCIES IN MATCHES:")
    discrepancies = []
    for reg, exp in matches:
        cost_diff = abs(reg["cost"] - exp["cost"])
        if cost_diff > 0.0001:
            discrepancies.append((reg, exp, cost_diff))
    
    if discrepancies:
        discrepancies.sort(key=lambda x: x[2], reverse=True)
        for reg, exp, diff in discrepancies[:10]:
            print(f"  Match at {reg['timestamp']}: Reg ${reg['cost']:.4f} vs Exp ${exp['cost']:.4f} (Diff: ${diff:.4f})")
        
        # Calculate average multiplier
        multipliers = [exp["cost"] / reg["cost"] for reg, exp in matches if reg["cost"] > 0]
        if multipliers:
            avg_mult = sum(multipliers) / len(multipliers)
            print(f"\nAverage Cost Multiplier (Exported / Registered): {avg_mult:.2f}x")
    else:
        print("  No major discrepancies found in matched events.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        # Default to the files mentioned in the prompt if they exist
        reg = pathlib.Path("stats/usage.csv")
        exp = pathlib.Path("stats/usage-events-2026-01-06.csv")
        if reg.exists() and exp.exists():
            reconcile(reg, exp)
        else:
            print("Usage: python reconcile.py <registered_csv> <exported_csv>")
    else:
        reconcile(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))

