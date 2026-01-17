# Troubleshooting

## Common Issues and Solutions

This guide covers common issues encountered when using vibe-tools and how to resolve them.

## Configuration Issues

### Configuration File Not Found

**Symptoms:**
- `implementation/config.json` not found
- Commands fail with configuration errors

**Solutions:**
```bash
# Initialize project
vibe init

# Or create manually
mkdir -p project
echo '{}' > implementation/config.json
```

### Configuration Not Loading

**Symptoms:**
- Changes to config not taking effect
- Default values always used

**Solutions:**
```bash
# Verify file exists and is readable
cat implementation/config.json

# Check JSON syntax
python -m json.tool implementation/config.json

# Re-run command to reload config
vibe status
```

### Service Configuration Missing

**Symptoms:**
- Service connection errors
- Services not found in config

**Solutions:**
```bash
# Configure service
vibe-setup <service>

# Verify configuration
vibe status

# Test connectivity
vibe-setup test
```

## Agent Issues

### Agent Not Responding

**Symptoms:**
- Agent commands hang
- No output from agent
- Timeout errors

**Solutions:**
```bash
# Check active processes
vibe ps

# Kill stuck processes
vibe kill

# Verify agent configuration
vibe status

# Check API keys
vibe-setup api
```

### Agent Completion Not Detected

**Symptoms:**
- Reconciliation loops don't complete
- Agent runs but doesn't signal completion

**Solutions:**
- Check agent output for `<promise>DONE</promise>`
- Verify prompt format
- Review agent logs: `implementation/logs/<command>.log`
- Try different agent: `--agent claude`

### Agent Errors

**Symptoms:**
- Agent returns errors
- Implementation fails

**Solutions:**
```bash
# Enable debug mode
vibe implement --debug

# Check logs
tail -f implementation/logs/implement.log

# Review agent output
# Look for error messages in logs
```

## PRD and Normalization Issues

### PRD Not Found

**Symptoms:**
- "No PRDs found" errors
- Normalization fails

**Solutions:**
```bash
# Check specs directory
ls product/

# Verify PRD files exist
find product/ -name "*.md"

# Create PRD if missing
vibe pm
```

### Normalization Fails

**Symptoms:**
- YAML generation fails
- Invalid YAML output

**Solutions:**
```bash
# Debug mode
vibe normalize --debug

# Check markdown syntax
# Verify spec file is valid markdown

# Re-normalize specific file
vibe normalize product/problematic.md

# Check YAML output
cat implementation/prds/prd_*.yaml | python -m yaml
```

### YAML Syntax Errors

**Symptoms:**
- Invalid YAML errors
- Parsing failures

**Solutions:**
```bash
# Validate YAML
python -c "import yaml; yaml.safe_load(open('implementation/prds/prd_01.yaml'))"

# Fix manually if needed
# Or re-normalize
vibe normalize product/01_feature.md --yes
```

## Implementation Issues

### Implementation Stuck

**Symptoms:**
- Implementation loop hangs
- No progress for long time

**Solutions:**
```bash
# Check processes
vibe ps

# Kill stuck processes
vibe kill

# Check branch status
git status

# Review logs
tail -f implementation/logs/implement.log

# Reset if needed
vibe rerun <prd_id>
```

### Reconciliation Fails

**Symptoms:**
- Reconciliation loops fail
- Desired vs current mismatch

**Solutions:**
```bash
# Check desired file
cat implementation/prds/architecture.yaml

# Check current file
cat implementation/architecture-current.yaml

# Verify files exist
ls implementation/prds/

# Re-run reconciliation
vibe setup  # or specific reconciliation step
```

### Branch Conflicts

**Symptoms:**
- Git merge conflicts
- Branch issues

**Solutions:**
```bash
# Check branch status
git status
vibe branches

# Resolve conflicts
vibe branch-resolve

# Or manually resolve
git merge <branch>
# Fix conflicts
git add .
git commit
```

## Service Issues

### Service Won't Start

**Symptoms:**
- Docker container fails to start
- Port already in use

**Solutions:**
```bash
# Check container status
vibe-servers status
docker ps -a

# View logs
vibe-servers logs <service>
docker logs <container_name>

# Remove and reinstall
vibe-servers remove <service>
vibe-servers install <service>

# Check port conflicts
lsof -i :5432  # For postgres
```

### Service Connection Fails

**Symptoms:**
- Cannot connect to service
- Connection refused errors

**Solutions:**
```bash
# Verify service is running
vibe-servers status

# Start service if stopped
vibe-servers start <service>

# Test connectivity
vibe-setup test

# Check configuration
vibe status

# Verify host/port
cat implementation/config.json | grep -A 5 "<service>"
```

### Docker Issues

**Symptoms:**
- Docker commands fail
- Container not found

**Solutions:**
```bash
# Verify Docker is running
docker ps

# Check Docker daemon
docker info

# Restart Docker if needed
# (platform-specific)

# Reinstall service
vibe-servers remove <service>
vibe-servers install <service>
```

## Test Issues

### Tests Failing

**Symptoms:**
- Test suite fails
- Linting errors

**Solutions:**
```bash
# Run test fix loop
vibe test-fix

# Fast mode (changed files only)
vibe test-fix --fast

# Check specific test
pytest tests/test_specific.py

# Review test output
make test
```

### Coverage Not Improving

**Symptoms:**
- Coverage loop doesn't improve coverage
- Stuck at same percentage

**Solutions:**
```bash
# Check current coverage
vibe status

# Review coverage report
# Check which files need coverage

# Manually review
# Agent may need more context
```

## Cost Tracking Issues

### Costs Not Logging

**Symptoms:**
- No cost data in CSV
- Google Sheets not updating

**Solutions:**
```bash
# Check directory exists
ls implementation/costs/

# Verify permissions
ls -la implementation/costs/

# Check Google Sheets config
vibe status
# Verify use_google_sheets and google_sheet_id

# Reconfigure if needed
vibe-setup google
```

### Incorrect Costs

**Symptoms:**
- Cost estimates seem wrong
- Unexpected high costs

**Solutions:**
- Check model pricing in `vibe_tools/cost.py`
- Verify token estimation (approximate)
- Review actual usage in logs
- Check for multiple agent runs

## File and Path Issues

### Files Not Found

**Symptoms:**
- "File not found" errors
- Path resolution issues

**Solutions:**
```bash
# Verify file exists
ls -la <path>

# Check current directory
pwd

# Use absolute paths if needed
vibe normalize /absolute/path/to/spec.md

# Check project structure
vibe status
```

### Migration Issues

**Symptoms:**
- Old file locations still used
- Migration not working

**Solutions:**
```bash
# Run init to trigger migration
vibe init

# Check for old files in root
ls -la | grep -E "(prds|logs|costs)"

# Manually migrate if needed
# Move files to implementation/ directory
```

## Performance Issues

### Slow Execution

**Symptoms:**
- Commands take very long
- Agent responses slow

**Solutions:**
- Check agent selection (some are slower)
- Use `--fast` flag for test-fix
- Reduce iteration limits in config
- Check network connectivity for API calls

### High Memory Usage

**Symptoms:**
- System becomes slow
- Memory warnings

**Solutions:**
- Kill stuck processes: `vibe kill`
- Check for memory leaks in logs
- Restart if needed
- Review large file operations

## Interactive Tools Issues

### Session Not Loading

**Symptoms:**
- Session data lost
- History not persisting

**Solutions:**
```bash
# Check session file
cat implementation/architect-session.json
cat implementation/pm-session.json

# Verify file permissions
ls -la implementation/*-session.json

# Reset if corrupted
rm implementation/architect-session.json
vibe architect  # Creates new session
```

### Editor Not Opening

**Symptoms:**
- `/edit` command fails
- Editor doesn't launch

**Solutions:**
```bash
# Configure editor
vibe architect
/conf code code  # or vim, etc.

# Verify editor command works
code --version

# Use absolute path if needed
/conf code /usr/local/bin/code
```

### Tab Completion Not Working

**Symptoms:**
- Tab completion doesn't work
- Commands not completing

**Solutions:**
- Verify readline is available (Linux/Mac)
- Check terminal compatibility
- Try different terminal
- Commands still work without completion

## Getting Help

### Debug Information

Collect debug information:

```bash
# System status
vibe status > debug-status.txt

# Configuration
cat implementation/config.json > debug-config.json

# Recent logs
tail -100 implementation/logs/*.log > debug-logs.txt

# Process list
vibe ps > debug-processes.txt
```

### Log Files

Check log files for details:

```bash
# List log files
ls implementation/logs/

# View recent logs
tail -f implementation/logs/<command>.log

# Search logs
grep "error" implementation/logs/*.log
```

### Common Commands for Debugging

```bash
# Check overall status
vibe status

# List processes
vibe ps

# Kill stuck processes
vibe kill

# Test services
vibe-setup test

# Check configuration
cat implementation/config.json

# View project state
cat implementation/state.json
```

## Prevention

### Best Practices

1. **Regular status checks**: `vibe status` regularly
2. **Monitor processes**: `vibe ps` before long operations
3. **Clean up**: `vibe kill` if processes stuck
4. **Backup state**: Commit `implementation/state.json` regularly
5. **Test services**: `vibe-setup test` after changes

### Maintenance

1. **Update dependencies**: Keep packages current
2. **Review logs**: Check for recurring issues
3. **Clean old data**: Remove obsolete PRDs/plans
4. **Verify config**: Ensure configuration is valid
5. **Test workflows**: Verify common workflows work

## Still Having Issues?

If issues persist:

1. **Check logs**: Review `implementation/logs/` for errors
2. **Verify setup**: Run `vibe init` and `vibe-setup api`
3. **Test minimal case**: Try with simple PRD
4. **Check dependencies**: Verify all services available
5. **Review documentation**: Check relevant docs sections

For persistent issues, consider:
- Creating minimal reproduction case
- Checking for known issues
- Reviewing recent changes
- Testing in clean environment

---

<details>
<summary>Metadata</summary>

```yaml
id: DOC-012
title: Troubleshooting
type: DOCUMENTATION
status: active
```

</details>

<!-- vibe-id: DOC-012 -->
