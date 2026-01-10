# Cost Tracking

## Overview

vibe-tools includes comprehensive cost tracking for LLM usage. All agent interactions are automatically logged with token counts and cost estimates, enabling budget management and cost analysis.

## Automatic Cost Tracking

Cost tracking is automatic for all agent interactions:
- Reconciliation loops
- Implementation loops
- Coverage improvement
- Test fixing
- Normalization
- Interactive tools

### What Gets Tracked

For each agent run:
- **Timestamp**: When the run occurred
- **PRD**: Associated PRD name
- **Phase**: Implementation phase (normalize, implement, coverage, etc.)
- **Iteration**: Loop iteration number
- **Agent**: Agent type used (cursor-agent, claude, etc.)
- **Model**: LLM model used
- **Input Tokens**: Estimated input token count
- **Output Tokens**: Estimated output token count
- **Cost (USD)**: Calculated cost
- **Purpose**: Purpose of the run

## Viewing Costs

### Current Session Cost

Costs are displayed during execution:
```
💰 Step Cost: $0.001234 USD (Model: gemini-3-flash, Phase: implement)
```

At the end of each command:
```
✅ Command completed. Total session cost: $0.012345 USD
```

### Total Project Cost

View total cost for the project:
```bash
vibe cost
```

Output:
```
Total estimated cost: $X.XX USD
```

### Detailed Cost Report

View detailed session report in logs:
```bash
tail -f implementation/logs/<command>.log
```

Report format:
```
================================================================================
SESSION COST REPORT
================================================================================
PRD                  Phase      Iter  Model                Cost (USD)
--------------------------------------------------------------------------------
prd_01_feature       implement  1     gemini-3-flash       $0.001234
prd_01_feature       implement  2     gemini-3-flash       $0.001456
--------------------------------------------------------------------------------
TOTAL SESSION COST:                                          $0.002690
================================================================================
```

## Cost Storage

### Local CSV Log

Costs are logged to `implementation/costs/usage.csv`:

```csv
Timestamp,PRD,Phase,Iteration,Agent,Model,Input Tokens,Output Tokens,Cost (USD),Purpose
2024-01-15 10:30:00,prd_01_feature,implement,1,cursor-agent,gemini-3-flash,1500,800,0.001234,implementation
```

### Google Sheets Integration

Optional integration with Google Sheets for centralized cost tracking.

**Setup:**
```bash
vibe-setup google
```

**Configuration:**
- Enable in `implementation/config.json`:
  ```json
  {
    "use_google_sheets": true,
    "google_sheet_id": "YOUR_SHEET_ID"
  }
  ```

**Authentication:**
- OAuth2 (browser login): `.vibe_authorized_user.json`
- Service Account: `.vibe_google_creds.json`

**Automatic Logging:**
- Costs are automatically appended to the configured sheet
- Same format as CSV log
- Real-time updates during execution

## Pricing Models

### Supported Models

Default pricing (per 1M tokens):

| Model | Input | Output |
|-------|-------|--------|
| gemini-3-flash | $0.10 | $0.40 |
| gemini-1.5-flash | $0.075 | $0.30 |
| claude-3-5-sonnet | $3.00 | $15.00 |
| claude-3-opus | $15.00 | $75.00 |
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |

### Default Agent Models

- **cursor-agent**: `gemini-3-flash`
- **claude**: `claude-3-5-sonnet`
- **antigravity**: `gpt-4o`

### Token Estimation

Tokens are estimated at ~4 characters per token:
- Simple character count divided by 4
- Reasonable approximation for cost tracking
- Actual tokenization may vary by model

## Budget Management

### Setting Budgets

Configure default budget in `implementation/config.json`:
```json
{
  "default_budget": 5.0
}
```

Budget is checked before automated runs:
- Prevents runaway costs
- Can be overridden per run
- Warns when approaching limit

### Cost Monitoring

**During execution:**
```bash
vibe monitor
# Shows cost accumulation in real-time
```

**After execution:**
```bash
vibe cost
vibe stats
```

## Cost Analysis

### By PRD

View costs per PRD:
```bash
# Check CSV file
cat implementation/costs/usage.csv | grep "prd_01_feature"
```

### By Phase

Analyze costs by implementation phase:
- `normalize`: PRD normalization
- `implement`: Implementation loops
- `coverage`: Coverage improvement
- `test_fix`: Test fixing
- `debug`: Debugging loops

### By Model

Compare costs across models:
- Different models have different pricing
- Choose appropriate model for task
- Balance cost vs capability

## Billing Groups

Organize costs by billing groups:

```bash
vibe billing-groups
```

Useful for:
- Multi-project cost allocation
- Team cost tracking
- Client billing

## Best Practices

### Cost Optimization

1. **Use appropriate models**: 
   - `gemini-3-flash` for routine tasks
   - `claude-3-5-sonnet` for complex reasoning
   - `gpt-4o` only when needed

2. **Set iteration limits**:
   ```json
   {
     "iterations": {
       "implementation": 10,
       "coverage": 5
     }
   }
   ```

3. **Monitor during runs**: Use `vibe monitor`

4. **Review costs regularly**: Check `vibe cost` after major operations

5. **Use fast mode**: `--fast` for test-fix reduces test execution

### Budget Management

1. **Set realistic budgets**: Based on project scope
2. **Monitor accumulation**: Check costs during long runs
3. **Use Google Sheets**: For centralized tracking across projects
4. **Review regularly**: Weekly/monthly cost reviews

### Cost Tracking

1. **Enable Google Sheets**: For team visibility
2. **Keep CSV logs**: For local analysis
3. **Tag purposes**: Helps categorize costs
4. **Review session reports**: Understand cost drivers

## Troubleshooting

### Costs Not Logging

**Check configuration:**
```bash
vibe status
# Verify use_google_sheets and google_sheet_id
```

**Check file permissions:**
```bash
ls -la implementation/costs/
# Ensure directory is writable
```

**Check Google Sheets setup:**
```bash
vibe-setup google
# Reconfigure if needed
```

### Incorrect Costs

**Verify model pricing:**
- Check `vibe_tools/cost.py` for current pricing
- Update if model prices changed

**Check token estimation:**
- Estimation is approximate
- Actual costs may vary slightly

### Google Sheets Issues

**Authentication problems:**
```bash
# Re-authenticate
vibe-setup google
```

**Sheet not found:**
- Verify `google_sheet_id` in config
- Check sheet permissions
- Ensure credentials have access

**Missing data:**
- Check CSV log: `implementation/costs/usage.csv`
- Verify Google Sheets API is enabled
- Check network connectivity

## Cost Reporting

### Session Reports

Automatically generated at command completion:
- Written to log files
- Summary to terminal
- Detailed breakdown available

### Custom Reports

Analyze CSV data:
```bash
# Total by PRD
cat implementation/costs/usage.csv | awk -F',' '{sum[$2]+=$10} END {for (i in sum) print i, sum[i]}'

# Total by phase
cat implementation/costs/usage.csv | awk -F',' '{sum[$3]+=$10} END {for (i in sum) print i, sum[i]}'
```

### Google Sheets Analysis

Use Google Sheets features:
- Pivot tables
- Charts and graphs
- Filtering and sorting
- Date range analysis

## Future Enhancements

Potential improvements:
- Cost alerts at thresholds
- Budget enforcement
- Cost forecasting
- Per-user cost tracking
- Integration with billing systems

See [Troubleshooting](12-troubleshooting.md) for more help.
