# PRD Normalization

## Overview
- **Problem statement**: Human-written markdown specifications need to be converted into machine-readable YAML PRDs that the Ralph loop engine can process. The conversion must preserve all information, handle edge cases, and support both individual files and batch processing.
- **User benefits**: Automatic conversion from human specs to machine PRDs, batch processing of multiple specs, validation of normalized PRDs, and support for global truth files (architecture, infrastructure, etc.).
- **Success criteria**: Normalization successfully converts all spec types, handles edge cases, validates output, supports overwrite protection, and produces correct YAML structure.

## Feature Inspiration
The `vibe normalize` command converts markdown specification files in `specs/` into YAML PRD files in `implementation/prds/`. It uses an AI agent to perform the conversion, ensuring the YAML structure matches the expected format. The process supports both individual file conversion and batch processing of all specs.

**Key capabilities**:
- Markdown to YAML conversion
- Batch processing of all specs
- Individual file processing
- Overwrite protection (ask, yes, no modes)
- Global truth handling (architecture, infrastructure, CICD, testing)
- PRD file naming (prd_*.yaml for implementation PRDs, *.yaml for global truths)
- Validation of normalized output

## Frontend
N/A - CLI command with progress output.

## Backend
- **File Discovery**: Finds all `.md` files in `specs/` directory (recursive), or processes specified file(s).
- **Conversion Process**:
  - Reads markdown spec file
  - Loads normalization prompt template
  - Calls AI agent with spec content and prompt
  - Agent generates YAML PRD
  - Validates YAML structure
  - Saves to `implementation/prds/` directory
- **Naming Convention**:
  - Implementation PRDs: `prd_{stem}.yaml` (from `specs/prd_*.md` or `specs/*.md`)
  - Global truths: `{stem}.yaml` (architecture.yaml, infrastructure.yaml, etc.)
  - Strips leading "prd" markers, normalizes dashes/spaces to underscores
- **Overwrite Protection**:
  - `--yes`: Auto-overwrite existing files
  - `--no`: Skip existing files
  - Default: Ask per file
- **Global Truth Files**: Special handling for:
  - `architecture.md` → `architecture.yaml`
  - `infrastructure.md` → `infrastructure.yaml`
  - `cicd.md` → `cicd.yaml`
  - `testing.md` → `testing.yaml`
  - `project_overview.md` → `project_overview.yaml`
- **Validation**: Checks YAML syntax, verifies required fields present, warns on potential issues.

## Infrastructure
- **Input**: Markdown files in `specs/` directory.
- **Output**: YAML files in `implementation/prds/` directory.
- **Prompt Templates**: Normalization prompt in `prompts/prd_normalization_prompt.txt`.
- **AI Agent**: Uses configured agent for conversion.

## Architecture and Constraints
- **Idempotency**: Normalizing same file multiple times should produce consistent results.
- **Information Preservation**: All information from markdown must be preserved in YAML.
- **YAML Structure**: Output must match expected PRD YAML schema.
- **Error Handling**: Graceful handling of invalid markdown, agent failures, YAML errors.
- **Batch Processing**: Efficient processing of multiple files, progress indication.

## Success Criteria
- All spec types successfully normalized
- YAML structure matches expected format
- Global truth files handled correctly
- Overwrite protection works
- Batch processing completes successfully
- Validation catches errors

## Acceptance Tests
1. **Single File**: Normalize one spec file, verify YAML created correctly
2. **Batch Processing**: Normalize all specs, verify all converted
3. **Overwrite Protection**: Try to normalize existing file, verify prompt/behavior
4. **Global Truth**: Normalize architecture.md, verify architecture.yaml created (not prd_architecture.yaml)
5. **Naming**: Normalize files with various names, verify correct YAML names
6. **Validation**: Create invalid spec, verify error handling
7. **Information Preservation**: Compare markdown and YAML, verify all info present
8. **Idempotency**: Normalize same file twice, verify consistent output

---
<details>
<summary>Metadata</summary>

```yaml
id: PRD-016
title: PRD Normalization
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.010016'
updated_at: '2026-01-13T20:22:57.138678'
discussion_id: D_kwDOQzI0Lc4AjoRl
discussion_url: https://github.com/jmfk/vibe-tools/discussions/25
last_synced_at: '2026-01-13T20:22:57.138556'
sync_hash: a1a2fbbf5ffa9d1895bf996588fca0f3589bc5fac6119521b83c5d498f3e299a
issue_number: null
```
</details>

<!-- vibe-id: PRD-016 -->
