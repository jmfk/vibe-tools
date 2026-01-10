TEMPLATES = {
    "ralph_base_prompt.txt": """You are running inside a RALPH LOOP.

This prompt will be executed repeatedly until you emit the completion promise.

TASK:
Generate full-stack code strictly according to the provided PRD.
Follow all constraints in the PRD and system instructions.

INTEGRATION RULES:
- Ensure the Frontend correctly integrates with the Backend.
- Generate TypeScript interfaces in the frontend that match data schemas in the backend.
- Create or update tests using established patterns.
- Ensure the Frontend is modern, responsive, and matches the platform vision.

MAKEFILE & TESTING RULES:
- A `Makefile` exists in the project root with the following targets: `test-backend`, `test-frontend`, `test-infra`, `test-integration`, `test-regression`, `lint-backend`, `lint-frontend`.
- As you develop the system, you MUST update these targets in the `Makefile` to run the relevant test suite for the stack you are building.
- Do NOT leave them as dummy echo commands if you have implemented the corresponding components.
- The `test` target should remain as a wrapper that calls all other test targets.
- DEPENDENCY MANAGEMENT: If you introduce new packages, update `pyproject.toml` (backend) or `package.json` (frontend). The system will automatically attempt to install them.

GENERAL RULES:
- Do NOT ask questions.
- Do NOT explain your reasoning.
- Do NOT stop early.
- Do NOT claim completion unless ALL conditions are met.
- If something is missing or ambiguous, continue refining output until resolved or explicitly blocked.

COMPLETION CONDITIONS:
You must emit the exact string:

<promise>DONE</promise>

ONLY when:
- Backend implementation is complete.
- Frontend implementation is complete.
- Appropriate tests have been added/updated.
- No BLOCKER comments remain.
- Output is internally consistent.
- No required work is left undone.

If the completion conditions are NOT met:
- Continue working.
- Improve or extend the output.
- Do NOT emit the completion promise.

OUTPUT FORMAT:
- Output code only.
- No prose.
- No markdown.
- The completion promise must appear on its own line, at the very end.
""",
    "pdr_normalization_prompt.txt": """🔒 PRD NORMALIZATION PROMPT


You are a PRD NORMALIZER.

Your task is to convert the input PRD into a STRICT, MACHINE-CONSUMABLE FORMAT.

Rules:
- Do NOT add, infer, or improve requirements.
- Do NOT rephrase intent.
- Extract only what is explicitly stated.
- If information is missing, mark it as: MISSING.
- If a section explicitly states there are NONE or NO items, mark it as: []
- Preserve ambiguity; do not resolve it.
- Use only the section headers defined below.
- Output valid YAML only.
- DO NOT wrap the output in markdown code blocks (e.g., no ```yaml).
- No explanations.

REQUIRED SECTIONS (in this exact order):
1. SYSTEM_CONTRACT
2. DOMAIN_MODEL
3. CAPABILITIES
4. OUTPUT_TARGETS

If a section has no data, include it with value: MISSING.

BEGIN INPUT PRD
<<<
{PASTE HUMAN PRD HERE}
>>>
END INPUT PRD
""",
    "review_prompt.txt": """You are a Senior Full-Stack Developer. Review the recent changes in 'backend/' and 'frontend/' against the provided PRD.

CONTEXT:
- PRD: {prd_path}

TASK:
1. Verify all requirements in the PRD are met.
2. Check for architectural consistency.
3. Check for security or performance issues.
4. Ensure frontend and backend are correctly integrated.

If everything looks correct, respond with: <review>PASSED</review>
Otherwise, list the issues and do NOT include the pass tag.
""",
    "reconciliation_prompt.txt": """You are in the '{name}' phase of the project lifecycle.
Your goal is to reconcile the DESIRED state with the ACTUAL state of the codebase.

PHASE: {name}
MODE: {mode}  # INITIALIZATION or MIGRATION
DESIRED FILE: {desired_file}
CURRENT FILE: {current_file}

DESIRED STATE content:
---
{desired_content}
---

ACTUAL STATE content (from {current_file}):
---
{current_content}
---

INSTRUCTIONS for {mode}:
1. Examine the current codebase and compare it against the DESIRED state.
2. If mode is MIGRATION, identify the deltas between the ACTUAL state and the DESIRED state.
3. Perform all necessary actions (coding, configuration, setup, migrations) to bring the codebase into alignment with the DESIRED state.
4. Ensure all changes are robust, follow project patterns, and are documented in the code where appropriate.
5. IMPORTANT: Once the reconciliation is complete, you MUST update '{current_file}' to exactly match the new state (which should now align with the DESIRED state).
6. {custom_instructions}
7. Include <promise>DONE</promise> in your response ONLY when the reconciliation is successful and '{current_file}' has been updated.
""",
    "prd_generation_prompt.txt": """You are an expert product writer who turns discussions into concise PRDs.

The user has supplied this information:

- Title: {title}
- Summary: {summary}
- Context: {context}
- Question/Answer Log:
{qa}

Produce a Markdown PRD with the following structure and cover all sections:

# {title}

## Overview
- Problem statement: what we are solving
- User benefits
- Success criteria

## Feature Inspiration
- Describe the main feature, flow, or capability.
- Mention data inputs/outputs if relevant.

## Frontend
- Key screens, components, and interactions.
- UX constraints, accessibility, or performance notes.

## Backend
- APIs, data models, validation, and integrations.
- Scaling, data consistency, or reliability concerns.

## Infrastructure
- Deployment targets, monitoring, storage, or ops work.
- Dependencies on databases, queues, caches, or third parties.

## Architecture and Constraints
- High-level architecture diagrams or service boundaries.
- Security, compliance, or platform guardrails.

## Success Criteria
- Measurable outcomes (e.g., metrics, KPIs).
- How we’ll know it is ready to ship.

## Acceptance Tests
- List scenarios or checks that prove the feature works.
- Include happy path plus key edge cases when possible.

Always keep the output limited to Markdown. If the QA log is empty, use \"No follow-up questions were needed.\"""",
    "prd_questions_prompt.txt": """You are an expert product analyst. Your task is to analyze the current state of a PRD discussion and generate follow-up questions to clarify requirements.

Current State:
- Title: {title}
- Summary: {summary}
- Context: {context}

Conversation History:
{history}

Based on the above, please provide:
1. A concise updated summary of the feature (if more information was gathered).
2. A list of 1-3 specific, high-impact questions to further define the product.
   - Questions can be open-ended or multiple choice.
   - For multiple choice, format as: "Question? \n a) Option 1 \n b) Option 2"
3. A flag "satisfied" (true/false) indicating if you have enough information to write a comprehensive PRD.

Output MUST be in valid JSON format:
{{
  "summary": "Updated summary...",
  "questions": [
    "Question 1?",
    "Question 2?"
  ],
  "satisfied": false
}}
""",
    "test_fix_prompt.txt": """The codebase currently has test or linting failures. Please fix them.

ERROR OUTPUT:
{test_output}

TASK:
1. Analyze the errors provided above.
2. Fix the underlying issues in the backend or frontend.
3. Ensure that after your changes, the project builds and tests pass.
4. Include <promise>DONE</promise> in your response once you believe the issues are fixed.
""",
    "coverage_improvement_prompt.txt": """You are in TEST COVERAGE IMPROVEMENT MODE.

CURRENT COVERAGE REPORT:
{report}

TASK:
Improve the test coverage of the backend implementation.
Focus on the files with the highest number of 'Missing' lines as shown in the report.
Create new test files or update existing ones to cover the missing lines.
Your goal is to increase the total coverage from {current_cov}% towards the target of {target_cov:.1f}%.

RULES:
- Do not break existing tests.
- Use established testing patterns for the project.
- Once you have added/updated tests that you believe significantly improve coverage, include <promise>DONE</promise> in your final response.

Output code only. No extra text.
""",
    "monitor_prompt.txt": """You are a PROGRESS INSPECTOR for an automated code generation loop.
Current Time: {timestamp}
Current Branch: {current_branch}

GIT STATUS (short):
{git_status}

RECENT DIFFS (backend/):
{last_diff}

TASK:
1. Identify which PRD is likely being processed (look at branch name).
2. Summarize the progress in 'backend/'.
3. Detect any "BLOCKER" messages in files or signs of failure/stalling.
4. Provide a HEALTH STATUS: [HEALTHY], [STALLED], or [FAILED].
5. Keep it very concise (max 10 lines).
""",
    "implementation_prompt.txt": """You are the Implementation Agent. Your task is to execute a specific plan.

PLAN TO EXECUTE:
Title: {title}
Description: {description}
Success Criteria:
{success_criteria}

TASK:
1. Implement the code and configuration required for THIS PLAN.
2. Verify your changes against the success criteria.
3. Include <promise>DONE</promise> in your response when the implementation is finished.
""",
    "implementation_review_prompt.txt": """Review the changes for the following plan:
TITLE: {title}
DESCRIPTION: {description}
SUCCESS CRITERIA:
{success_criteria}

If the implementation meets all requirements, respond with: <review>PASSED</review>
Otherwise, list the issues.
""",
    "issue_solve_prompt.txt": """You are the Issue Solver Agent. Your task is to resolve the following issue.

ISSUE DETAILS:
ID: {issue_id}
Title: {issue_title}

ISSUE BODY:
{issue_body}

TASK:
1. Analyze the issue and the current state of the codebase.
2. Implement the necessary changes to fix the issue.
3. Verify your changes against the acceptance criteria if provided.
4. Include <promise>DONE</promise> in your response when the fix is implemented.
""",
    "issue_fail_report_template.md": """# Issue Failure Report: {issue_id}

## Issue Details
- **ID:** {issue_id}
- **Title:** {issue_title}
- **Status:** FAILED
- **Iterations:** {iterations}

## Summary of Attempts
{attempts_summary}

## Final Codebase State
The following files were modified during the attempts:
{modified_files}

## Analysis of Failure
The agent was unable to resolve the issue within the maximum number of iterations. Check the logs for detailed iteration outputs.
""",
    "git_fix_prompt.txt": """A git operation failed while trying to switch to branch '{branch_name}' for PRD '{project_name}'.

ERROR:
{error}

CURRENT GIT STATUS:
{git_status}

TASK:
Please resolve this git issue so the automated pipeline can continue.
You may need to stash changes, commit them, reset the branch, or merge.
Ensure the end state is that we are on branch '{branch_name}' and ready to work.
""",
    "git_resolve_prompt.txt": """You are a Git Expert. The user's branch stack or history has become tangled or has conflicts.

GIT STATUS:
{git_status}

GIT LOG (recent):
{git_log}

ALL BRANCHES:
{git_branches}

VIBE BRANCH LINEAGE (Desired):
{lineage}

TASK:
1. Analyze the current git state and the desired lineage.
2. Resolve any conflicts, failed rebases, or detached HEAD states.
3. Ensure that the branch stack matches the desired lineage as closely as possible.
4. If a branch should be based on another but isn't, rebase it.
5. Provide the exact commands you are running or have run.
6. When the history is clean and aligned with the lineage, include <promise>DONE</promise>.

Respond with the actions you are taking. Output code only where possible, or clear step-by-step resolution.
""",
    "discovery_prompt.txt": """Analyze the current codebase and generate the following four files:
1. '{architecture_current}': YAML describing the ACTUAL tech stack, directory structure, key dependencies, and test suites (including test entry points like pytest or npm test).
2. '{infra_current}': YAML describing the ACTUAL infrastructure including databases, external services, caches, queues, and object storage.
3. '{architecture_spec}': Markdown specification of the DESIRED architecture, based on the codebase but cleaned up for a specification.
4. '{infra_spec}': Markdown specification of the DESIRED infrastructure.

The '-current.yaml' files must describe what is CURRENTLY implemented. Pay special attention to identifying how tests are currently run for both frontend and backend.
The '.md' files in 'product/' should be human-readable specifications that we can review and then 'vibe normalize' into the desired '.yaml' files.

ACTUAL CODEBASE:
(The agent has access to the filesystem to perform this analysis)

Once you have analyzed the codebase and written ALL four files, include <promise>DONE</promise>.
""",
    "architecture_proposal_prompt.txt": """Analyze the PRDs in implementation/prds/ and propose a comprehensive 'architecture.yaml' file that defines the tech stack, database schema, and project structure.""",
    "Makefile": """.PHONY: test test-backend test-frontend test-infra test-integration test-regression lint lint-backend lint-frontend

test: test-backend test-frontend test-infra test-integration test-regression lint

test-backend:
	@echo "Running backend tests..."
	pytest backend/tests/

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && npm test -- --run

test-infra:
	@echo "Running infra tests..."
	pytest backend/tests/test_infra.py

test-integration:
	@echo "Running integration tests..."
	pytest backend/tests/integration/

test-regression:
	@echo "Running regression tests..."
	pytest backend/tests/regression/

lint: lint-backend lint-frontend

lint-backend:
	@echo "Running backend linting..."
	ruff check backend/

lint-frontend:
	@echo "Running frontend linting..."
	cd frontend && npm run lint
""",
    "dummy_backend_test": """def test_dummy():
    assert True
""",
    "dummy_frontend_test": """describe('dummy test', () => {
  it('should pass', () => {
    expect(true).toBe(true);
  });
});
""",
    "architect_prompt.txt": """You are an expert software architect. You are helping the user refine their project's architecture and infrastructure specifications.

Currently, you have access to two main specification files:
1. Architecture Specification (architecture.md)
2. Infrastructure Specification (infrastructure.md)

MODE: {mode}

{mode_instructions}

TASK:
Your goal is to refine these specifications or provide guidance based on user instructions.

CRITICAL RULES FOR UPDATING FILES:
- If you are updating the Architecture Specification, you MUST start your response with 'FILE_UPDATE: arch'.
- If you are updating the Infrastructure Specification, you MUST start your response with 'FILE_UPDATE: infra'.
- DO NOT mix content from one file into the other unless explicitly asked to move information.
- Provide the FULL content of the file after your changes.

CURRENT ARCHITECTURE (architecture.md):
{architecture_content}

CURRENT INFRASTRUCTURE (infrastructure.md):
{infrastructure_content}

{instructions}

{user_memory}

CONVERSATION HISTORY:
{history}

GOAL:
Respond to the user's latest query or instruction.
If they ask a question, answer it clearly based on the provided specifications.
If they provide an instruction to modify one of the files, perform the logic and output the FULL updated content of that file using the FILE_UPDATE header (ONLY in AGENT mode).

USER QUERY:
{query}
""",
    "pm_prompt.txt": """You are an expert Product Manager (PM). You are helping the user create, refine, and manage Product Requirements Documents (PRDs) in the 'product/' directory.

Currently, you have access to the existing specifications in the 'product/' directory.

MODE: {mode}

{mode_instructions}

TASK:
Your goal is to refine existing PRDs or create new ones in the 'product/' directory.

CRITICAL RULES FOR UPDATING FILES:
- If you are updating or creating a file in 'product/', you MUST start your response with 'FILE_UPDATE: <filename>'.
- For example, if updating 'product/01_auth.md', use 'FILE_UPDATE: 01_auth.md'.
- Provide the FULL content of the file after your changes.
- IMPORTANT: You are NOT allowed to edit PRDs that have already been implemented. These are listed in the 'IMPLEMENTED PRDS' section below. If the user wants to change an implemented PRD, suggest creating a NEW PRD (a 'v2' or refinement) that builds upon it, but DO NOT modify the original file.
- If creating a NEW PRD, ensure the filename is descriptive and follows the existing naming convention (e.g., 'product/XX_feature_name.md').

EXISTING SPECS:
{specs_content}

IMPLEMENTED PRDS:
{implemented_prds}

{instructions}

{user_memory}

CONVERSATION HISTORY:
{history}

GOAL:
Respond to the user's latest query or instruction.
If they ask a question, answer it clearly based on the provided specifications.
If they provide an instruction to modify or create a PRD, perform the logic and output the FULL updated content of that file using the FILE_UPDATE header (ONLY in AGENT mode).

USER QUERY:
{query}
""",
    "README": """
Global commands for Cursor Ralph loop and coverage improvement.

## Configuration

The tools use a `.vibe_config.json` file in the project root for configuration. This file is automatically created and updated when running `vibe config google`.

### Example `.vibe_config.json`

```json
{
  "ralph": {
    "review": true,
    "tests": true,
    "auto_merge": false
  },
  "caffeinate": true,
  "use_google_sheets": true,
  "google_sheet_id": "YOUR_SHEET_ID_HERE",
  "verbose": false,
  "default_budget": 5.0,
  "services": {
    "postgres": {
      "host": "localhost",
      "port": 5432,
      "user": "postgres",
      "password": "",
      "database": "app_db",
      "docker_container_name": "postgres-local"
    },
    "redis": {
      "host": "localhost",
      "port": 6379,
      "password": "",
      "database": 0,
      "docker_container_name": "redis-local"
    },
    "rabbitmq": {
      "host": "localhost",
      "port": 5672,
      "user": "guest",
      "password": "guest",
      "virtual_host": "/",
      "docker_container_name": "rabbitmq-local"
    },
    "elasticsearch": {
      "host": "localhost",
      "port": 9200,
      "scheme": "http",
      "username": "",
      "password": "",
      "docker_container_name": "es-local"
    },
    "s3-linode": {
      "host": "localhost",
      "port": 9000,
      "access_key": "minioadmin",
      "secret_key": "minioadmin",
      "region": "us-east-1",
      "addressing_style": "path",
      "signature_version": "s3v4"
    },
    "s3-aws": {
      "host": "localhost",
      "port": 9010,
      "access_key": "minioadmin",
      "secret_key": "minioadmin",
      "region": "us-east-1",
      "addressing_style": "virtual",
      "signature_version": "s3v4"
    }
  }
}
```

- `caffeinate`: Prevent system sleep during long-running tasks.
- `use_google_sheets`: Whether to log LLM costs to Google Sheets.
- `google_sheet_id`: The ID of the Google Sheet to log to.
- `verbose`: Whether to output detailed logs (like prompts) to the terminal.
- `default_budget`: Max budget in USD for automated runs (can be overridden per run).
- `services`: Connection details for supporting servers (Postgres, Redis, RabbitMQ, Elasticsearch, etc.). Entries under this map store host, port, credentials, and any detected Docker container so every project command can reuse a shared backend.

### Service Configuration

Use the `vibe config` command to record connection details for the supporting services your projects rely on:

- `vibe config postgres`
- `vibe config redis`
- `vibe config rabbitmq`
- `vibe config elasticsearch`
- `vibe config s3-linode`
- `vibe config s3-aws`
- `vibe config imgproxy`
- `vibe config api`
- `vibe config google`
- `vibe config test`: Verify connectivity for all configured services.

Each command walks you through host, port, and credential prompts and attempts to detect a running Docker container for that service (`docker ps`/`docker inspect`) so the host and port default to what is already running locally. The answers are stored under the `services` map in `.vibe_config.json` and can be reused by every tool that needs a database, queue, cache, or search backend.

## Installation

```bash
pip install -e .
```

## Usage

### CLI

The `vibe` command is the main entry point:

```bash
vibe --help
```

### Key Commands

- `vibe init`: Initialize templates and prompt directories.
- `vibe status`: Display a comprehensive system status report (costs, PRDs, servers, logs).
- `vibe docs`: Display the project documentation (README.md).
- `vibe architect`: Interactive Architecture & Infrastructure manager (preferred for system design).
- `vibe pm`: Interactive PRD & Specification manager (preferred for requirement gathering).
- `vibe prd`: Interactive PRD writer with slash commands.
- `vibe rerun <prd_id>`: Reset a PRD's state and branch to allow rerunning from scratch.
- `vibe cleanup`: Clean up stale pytest, agent, and caffeinate processes.
- `vibe memory`: Save a global instruction ("memory") always sent to the agent.
- `vibe remember`: Alias for `vibe memory`.
- `vibe history`: Check the status of all PRDs.
- `vibe cost`: View total estimated cost of LLM usage.
- `vibe config api`: Configure API keys for Google Gemini/DSPy.
- `vibe config google`: Configure Google Sheets for cost logging.

## Vibe Architect

`vibe architect` is an interactive shell for managing and refining your project's **Architecture** and **Infrastructure** specifications. It uses an AI agent to help you reason about your system and automatically update your `.md` files in `product/`.

### Key Features

- **Interactive Shell**: Persistent history, tab completion for slash commands, and multi-line prompt support.
- **Two Modes**:
  - **ASK** (Default): The agent provides analysis and guidance without modifying files.
  - **AGENT**: The agent is authorized to propose machine-readable updates to `architecture.md` and `infrastructure.md`.
- **Session Persistence**: Your history, pending prompts, and attached context files are saved between sessions in `implementation/architect-session.json`.
- **Editor Integration**: Configure your favorite Markdown or Code editor (e.g., Typora, VS Code) to open response files or specifications.
- **Context Management**: Attach additional files to the agent's context using `/f add`.
- **Session Memory**: Add persistent instructions that are sent with every prompt using `/a` or `/add`.

### Slash Commands

- `/send`, `/s`: Dispatch the current pending prompt to the Architect.
- `/reset`, `/r`: Clear the current session memory and pending prompt.
- `/add`, `/a <text>`: Add persistent instructions to the session memory.
- `/mode`, `/m [ASK|AGENT]`: Switch between interaction modes.
- `/files`, `/f [list|add <path>|remove <path>]`: Manage additional files included in the prompt context.
- `/list memory`, `/l`: View your pending prompt, session memory, and history summary.
- `/conf [md|code] <cmd>`: Configure external editors (e.g., `/conf md typora`).
- `/help`, `/h`: Show available commands.
- `/c`: Clear the terminal prompt history.
- `/exit`, `/q`: Exit the session.

### Local Infrastructure

Manage local development servers via Docker using `vibe servers`:

- `vibe servers list`: List supported servers (Postgres, Redis, RabbitMQ, Elasticsearch, MailHog, MinIO-Linode, MinIO-AWS, imgproxy) and their status.
- `vibe servers install <service>`: Pull and run the Docker container for a service. Use `minio` as a shorthand to choose between Linode and AWS styles.
- `vibe servers start/stop <service>`: Start or stop one or all servers.
- `vibe servers logs <service>`: View logs for one or all servers.
- `vibe servers status`: Show detailed status and port mappings.
- `vibe servers remove <service>`: Remove a service container.

### Linode Object Storage Compatibility

The local MinIO setup is configured to be "Linode-first," ensuring that development on MinIO seamlessly transitions to Linode Object Storage:

- **Path-Style Addressing**: Uses `endpoint/bucket/file` format (standard for Linode).
- **Signature Version**: Enforces `s3v4` authentication.
- **Protocol Detection**: Supports both `http` (local) and `https` (production) via endpoint URL configuration.
- **S3 Protocol URLs**: Overrides default behavior to support `s3://` protocol for internal services like `imgproxy`.

### Loop Scripts

- `vibe coverage`: Run the loop to improve test coverage.
- `vibe test-fix`: Run the loop to fix failing tests.
- `vibe normalize`: Normalize human-written specs into PRDs.

## Specs & PRDs

1. **Start with a human spec.** Write a normative spec in `product/` (for example `product/01_platform_vision.md`). That markdown is the source of truth for requirements.
2. **Global Truths.** Certain files in `product/` represent the persistent state of the system and are injected into every Ralph prompt as context:
   - `architecture.md` -> `prds/architecture.yaml`
   - `project_overview.md` -> `prds/project_overview.yaml`
   - `infrastructure.md` -> `prds/infrastructure.yaml`
   - `cicd.md` -> `prds/cicd.yaml`
3. **Convert specs into Ralph-ready PRDs.** Ralph only reads `prds/prd_*.yaml` for implement tasks. Transform each spec into a YAML file using `vibe normalize`. Global truths are converted without the `prd_` prefix and are used purely for context.
4. **Global Agent Instructions.** Use `vibe remember` to save global guidelines into `instructions/`. Ralph reads all files in this directory and injects them into every agent prompt.
5. **Understand the Ralph loop.** [DEPRECATED] `vibe ralph` reads the `prds/` directory, loads the global truth context files, and sequentially processes `prd_*.yaml` files. It prompts the agent until it emits `<promise>DONE</promise>` before moving on to quality gates.

## Development

Monitor the status of loops using `vibe monitor`:

```bash
vibe monitor
```
""",
}
