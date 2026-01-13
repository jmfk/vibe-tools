# Cost Reconciliation

## Overview
- **Problem statement**: Teams need to reconcile costs logged by vibe-tools with costs exported from Cursor or other sources. The system should identify duplicates, find missing entries, and provide reconciliation reports.
- **User benefits**: Accurate cost tracking, duplicate detection, missing entry identification, and reconciliation reports for cost auditing.
- **Success criteria**: Reconciliation successfully identifies duplicates, finds missing entries, handles timestamp differences, and provides useful reconciliation reports.

## Feature Inspiration
The cost reconciliation system compares costs logged by vibe-tools (in `usage.csv`) with costs exported from Cursor (CSV export). It normalizes timestamps, matches events by time/model/cost, identifies duplicates, and finds missing entries in either source.

**Key capabilities**:
- CSV import and parsing
- Timestamp normalization (ISO vs local time)
- Event matching (by timestamp, model, cost)
- Duplicate detection
- Missing entry identification
- Reconciliation reporting

## Frontend
N/A - CLI command or utility function.

## Backend
- **Input Files**:
  - Registered: `implementation/costs/usage.csv` (vibe-tools logs)
  - Exported: Cursor export CSV file
- **Parsing**:
  - `parse_iso_timestamp()`: Parses ISO timestamps from Cursor export
  - `parse_registered_timestamp()`: Parses local timestamps from usage.csv
  - Normalizes to UTC for comparison
- **Model Normalization**: 
  - `normalize_model()`: Normalizes model names for comparison
  - Handles variations (gemini-3-flash vs gemini-3-flash-preview)
- **Matching Logic**:
  - Matches events by:
    - Timestamp (within tolerance, e.g., 5 minutes)
    - Model (normalized)
    - Cost (within tolerance)
  - Identifies duplicates (same event in both files)
  - Identifies missing (in one file but not other)
- **Reconciliation Report**:
  - Lists duplicates found
  - Lists missing from registered
  - Lists missing from exported
  - Provides summary statistics
- **Tolerance Settings**:
  - Timestamp tolerance: 5 minutes (default)
  - Cost tolerance: Small percentage difference allowed

## Infrastructure
- **CSV Processing**: Reads and parses CSV files.
- **Timestamp Handling**: Converts between timezones, handles ISO and local formats.

## Architecture and Constraints
- **Matching Accuracy**: Matching by timestamp/model/cost may have false positives/negatives.
- **Timestamp Tolerance**: Must handle clock skew, timezone differences.
- **Model Variations**: Must handle model name variations.
- **Cost Tolerance**: Must handle rounding differences.

## Success Criteria
- Duplicates identified correctly
- Missing entries found
- Timestamp normalization works
- Model normalization works
- Reconciliation reports useful

## Acceptance Tests
1. **CSV Import**: Import both files, verify parsed correctly
2. **Timestamp Parsing**: Test various timestamp formats, verify normalized
3. **Model Normalization**: Test model name variations, verify normalized
4. **Matching**: Test event matching, verify duplicates found
5. **Missing Detection**: Test missing entries, verify identified
6. **Tolerance**: Test with timestamp/cost differences, verify tolerance works
7. **Report**: Generate report, verify useful and accurate

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-024
title: Cost Reconciliation
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.013290'
updated_at: '2026-01-13T20:33:01.852408'
discussion_id: D_kwDOQzI0Lc4AjoSq
discussion_url: https://github.com/jmfk/vibe-tools/discussions/36
last_synced_at: '2026-01-13T20:33:01.852304'
sync_hash: 715412d2cffec1e9ab32187d6380ac780d7da8a303377e99527d6420ff8dae39
issue_number: null
```
</details>

<!-- vibe-id: PRD-024 -->
