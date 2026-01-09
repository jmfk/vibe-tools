# Stats and Billing

## Overview
- **Problem statement**: Teams need usage statistics and billing group management for cost allocation and analysis. The system should provide cost breakdowns by API, billing groups, time periods, and support billing group operations.
- **User benefits**: Usage statistics, cost breakdowns, billing group management, time-period analysis, and cost allocation.
- **Success criteria**: Stats command provides useful statistics, billing groups work correctly, time filtering works, and cost allocation accurate.

## Feature Inspiration
The `vibe stats` and `vibe billing-groups` commands provide usage statistics and billing group management. Stats can be filtered by API, billing groups, date ranges, and provide cost breakdowns. Billing groups allow organizing users/costs for allocation.

**Key capabilities**:
- Usage statistics (costs, tokens, operations)
- Cost breakdowns (by API, model, PRD, phase)
- Time period filtering (days, date ranges)
- Billing group management
- Billing group cost allocation

## Frontend
N/A - CLI commands with formatted output.

## Backend
- **Stats Command** (`vibe stats`):
  - Reads `usage.csv`
  - Filters by:
    - `--api`: Filter by API/agent
    - `--billing-groups`: Filter by billing groups
    - `--days`: Last N days
    - `--start-date`, `--end-date`: Date range
  - Calculates statistics:
    - Total cost
    - Total tokens (input + output)
    - Operation count
    - Cost by model
    - Cost by PRD
    - Cost by phase
  - Displays formatted report
- **Billing Groups** (`vibe billing-groups`):
  - `list [billing_cycle]`: List billing groups
  - `create <name>`: Create billing group
  - `get <group_id> [billing_cycle]`: Get group details
  - `add-members <group_id> <user_ids...>`: Add members
  - `remove-members <group_id> <user_ids...>`: Remove members
- **Billing Group Storage**: 
  - Stored in database or config file
  - Associates users with groups
  - Tracks costs per group
- **Cost Allocation**: 
  - Allocates costs to billing groups
  - Supports multiple billing cycles
  - Provides group-level cost reports

## Infrastructure
- **Data Source**: `project/costs/usage.csv`.
- **Billing Group Storage**: Database or config file (TBD).
- **Date Processing**: Parses and filters by dates.

## Architecture and Constraints
- **Data Source**: Relies on CSV format, may need migration if format changes.
- **Billing Groups**: Implementation may vary (database vs config).
- **Time Filtering**: Must handle timezone issues.
- **Performance**: CSV parsing may be slow for large datasets.

## Success Criteria
- Stats provide useful information
- Filtering works correctly
- Billing groups manageable
- Cost allocation accurate
- Reports formatted clearly

## Acceptance Tests
1. **Stats Display**: Run `vibe stats`, verify statistics shown
2. **API Filtering**: Filter by API, verify correct subset
3. **Date Filtering**: Filter by date range, verify correct period
4. **Billing Group Creation**: Create billing group, verify saved
5. **Member Management**: Add/remove members, verify updated
6. **Cost Allocation**: Verify costs allocated to groups correctly
7. **Report Format**: Verify reports formatted clearly
