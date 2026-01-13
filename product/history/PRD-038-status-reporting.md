# Status Reporting

## Overview
- **Problem statement**: Developers need a comprehensive system status report showing costs, PRDs, servers, and logs in one place. The report should be quick to generate and provide actionable information.
- **User benefits**: Single command for system overview, quick status check, cost summary, PRD status, server status, and log information.
- **Success criteria**: `vibe status` provides comprehensive, accurate, and useful status information in a clear format.

## Feature Inspiration
The `vibe status` command provides a comprehensive system status report. It aggregates information from multiple sources (costs, PRDs, servers, logs) and presents it in a formatted, easy-to-read report.

**Key capabilities**:
- Cost summary (total, recent, by PRD)
- PRD status (pending, in progress, completed)
- Server status (running services, ports)
- Log information (recent logs, errors)
- System health indicators

## Frontend
N/A - CLI formatted output.

## Backend
- **Status Aggregation**: `get_vibe_status_report()` function:
  - Reads cost data from CSV
  - Reads PRD state from project state files
  - Checks server status via Docker
  - Reads recent log files
  - Aggregates all information
- **Cost Summary**:
  - Total cost (all time)
  - Recent cost (last 7 days, 30 days)
  - Cost by PRD
  - Cost trends
- **PRD Status**:
  - Lists all PRDs
  - Shows status (pending, in progress, completed, failed)
  - Shows last updated time
  - Shows implementation progress
- **Server Status**:
  - Lists configured services
  - Shows running status
  - Shows port mappings
  - Shows container names
- **Log Information**:
  - Lists recent log files
  - Shows log sizes
  - Highlights errors/warnings
- **Formatting**: 
  - Uses colors and formatting for readability
  - Sections clearly separated
  - Key metrics highlighted

## Infrastructure
- **Data Sources**: CSV files, state files, Docker, log files.
- **Aggregation**: Reads from multiple sources, combines into report.

## Architecture and Constraints
- **Performance**: Must be fast (reads multiple files, Docker checks).
- **Accuracy**: Relies on data being up-to-date.
- **Formatting**: Terminal formatting may not work in all environments.

## Success Criteria
- Report comprehensive and accurate
- Fast generation (< 2 seconds)
- Clear formatting
- Useful information presented
- All sections populated correctly

## Acceptance Tests
1. **Status Generation**: Run `vibe status`, verify report generated
2. **Cost Summary**: Verify cost summary accurate
3. **PRD Status**: Verify PRD status correct
4. **Server Status**: Verify server status accurate
5. **Log Information**: Verify log information shown
6. **Formatting**: Verify formatting clear and readable
7. **Performance**: Verify report generated quickly

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-038
title: Status Reporting
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.018117'
updated_at: '2026-01-13T20:07:27.788281'
discussion_id: null
discussion_url: https://github.com/jmfk/vibe-tools/discussions/54
last_synced_at: null
sync_hash: null
issue_number: null
```
</details>

<!-- vibe-id: PRD-038 -->
