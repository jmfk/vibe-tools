# Demo Data Generation

## Overview
- **Problem statement**: Projects need demo data for testing and demonstrations. The system should provide tools to generate, manage, and clean demo data.
- **User benefits**: Easy demo data generation, data management, and cleanup tools.
- **Success criteria**: Demo data generation successfully creates useful demo data, manages it properly, and provides cleanup capabilities.

## Feature Inspiration
The `vibe demo-data` command provides demo data generation and management. It supports designing demo data schemas, generating data, and cleaning up demo data.

**Key capabilities**:
- Demo data design
- Data generation
- Data cleanup
- Schema management

## Frontend
N/A - CLI commands.

## Backend
- **Demo Data Commands**:
  - `vibe demo-data design`: Design demo data schema
  - `vibe demo-data setup [--clean]`: Generate demo data
  - `--clean`: Clean existing data before generating
- **Data Generation**: 
  - Generates data based on schema
  - May use AI to generate realistic data
  - Stores in database or files
- **Schema Management**: 
  - Defines data structure
  - Specifies relationships
  - Configures generation rules
- **Cleanup**: 
  - Removes demo data
  - Cleans database tables
  - Removes files

## Infrastructure
- **Database**: May use configured database for storage.
- **File System**: May store data in files.

## Architecture and Constraints
- **Data Quality**: Generated data should be realistic and useful.
- **Cleanup Safety**: Cleanup should be safe and reversible.

## Success Criteria
- Demo data generated successfully
- Data useful for testing/demos
- Cleanup works correctly
- Schema management functional

## Acceptance Tests
1. **Data Generation**: Generate demo data, verify created
2. **Data Quality**: Verify data realistic and useful
3. **Cleanup**: Clean demo data, verify removed
4. **Schema Management**: Design schema, verify saved

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-028
title: Demo Data Generation
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.015178'
updated_at: '2026-01-13T20:30:14.882685'
discussion_id: D_kwDOQzI0Lc4AjoSB
discussion_url: https://github.com/jmfk/vibe-tools/discussions/43
last_synced_at: '2026-01-13T20:30:14.882588'
sync_hash: f5525d69f398a9c5f0faf659f42002af5e596b1455e9455441e77c18fe35344f
issue_number: null
```
</details>

<!-- vibe-id: PRD-028 -->
