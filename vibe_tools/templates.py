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
    "Makefile": """.PHONY: test test-backend test-frontend test-infra test-integration test-regression lint lint-backend lint-frontend

test: test-backend test-frontend test-infra test-integration test-regression lint

test-backend:
	@echo "Running backend tests..."
	pytest backend/tests/

test-frontend:
	@echo "Running frontend tests..."
	npm --prefix frontend test -- --run

test-infra:
	@echo "Running infra tests..."
	pytest backend/tests/test_infra.py || echo "No infra tests found"

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
	npm --prefix frontend run lint
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
    "README": """# vibe-tools

Global commands for Cursor Ralph loop and coverage improvement.

## Configuration

The tools use a `.vibe_config.json` file in the project root for configuration. This file is automatically created and updated when running `vibe-setup google` or on the first run of `vibe ralph`.

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

- `ralph`: Default quality gates for the `vibe ralph` loop.
- `caffeinate`: Prevent system sleep during long-running tasks.
- `use_google_sheets`: Whether to log LLM costs to Google Sheets.
- `google_sheet_id`: The ID of the Google Sheet to log to.
- `verbose`: Whether to output detailed logs (like prompts) to the terminal.
- `default_budget`: Max budget in USD for automated runs (can be overridden per run).
- `services`: Connection details for supporting servers (Postgres, Redis, RabbitMQ, Elasticsearch, etc.). Entries under this map store host, port, credentials, and any detected Docker container so every project command can reuse a shared backend.

### Service Configuration

Use the `vibe-setup` command to record connection details for the supporting services your projects rely on:

- `vibe-setup postgres`
- `vibe-setup redis`
- `vibe-setup rabbitmq`
- `vibe-setup elasticsearch`
- `vibe-setup s3-linode`
- `vibe-setup s3-aws`
- `vibe-setup api`
- `vibe-setup google`
- `vibe-setup test`: Verify connectivity for all configured services.

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
- `vibe prd`: Interactive PRD writer with slash commands (preferred).
- `vibe rerun <prd_id>`: Reset a PRD's state and branch to allow rerunning from scratch.
- `vibe cleanup`: Clean up stale pytest, agent, and caffeinate processes.
- `vibe memory`: Save a global instruction ("memory") always sent to the agent.
- `vibe remember`: Alias for `vibe memory`.
- `vibe history`: Check the status of all PRDs.
- `vibe cost`: View total estimated cost of LLM usage.
- `vibe ralph`: Run the main PRD processing loop.
- `vibe write-prd`: [DEPRECATED] Use `vibe prd` instead.
- `vibe review-prd`: [DEPRECATED] List and view markdown specs with optional agentic review.
- `vibe-setup api`: Configure API keys for Google Gemini/DSPy.
- `vibe-setup google`: Configure Google Sheets for cost logging.

### Local Infrastructure

Manage local development servers via Docker using `vibe-servers`:

- `vibe-servers list`: List supported servers (Postgres, Redis, RabbitMQ, Elasticsearch, MailHog, MinIO-Linode, MinIO-AWS) and their status.
- `vibe-servers install <service>`: Pull and run the Docker container for a service. Use `minio` as a shorthand to choose between Linode and AWS styles.
- `vibe-servers start/stop <service>`: Start or stop one or all servers.
- `vibe-servers logs <service>`: View logs for one or all servers.
- `vibe-servers status`: Show detailed status and port mappings.
- `vibe-servers remove <service>`: Remove a service container.

### Linode Object Storage Compatibility

The local MinIO setup is configured to be "Linode-first," ensuring that development on MinIO seamlessly transitions to Linode Object Storage:

- **Path-Style Addressing**: Uses `endpoint/bucket/file` format (standard for Linode).
- **Signature Version**: Enforces `s3v4` authentication.
- **Protocol Detection**: Supports both `http` (local) and `https` (production) via endpoint URL configuration.
- **S3 Protocol URLs**: Overrides default behavior to support `s3://` protocol for internal services like `imgproxy`.

### Loop Scripts

- `vibe ralph`: Run the Ralph loop for automated coding.
- `vibe coverage`: Run the loop to improve test coverage.
- `vibe test-fix`: Run the loop to fix failing tests.
- `vibe normalize`: Normalize human-written specs into PRDs.

## Specs & PRDs

1. **Start with a human spec.** Write a normative spec in `specs/` (for example `specs/01_platform_vision.md`). That markdown is the source of truth for requirements.
2. **Global Truths.** Certain files in `specs/` represent the persistent state of the system and are injected into every Ralph prompt as context:
   - `architecture.md` -> `prds/architecture.yaml`
   - `project_overview.md` -> `prds/project_overview.yaml`
   - `infrastructure.md` -> `prds/infrastructure.yaml`
   - `cicd.md` -> `prds/cicd.yaml`
3. **Convert specs into Ralph-ready PRDs.** Ralph only reads `prds/prd_*.yaml` for implementation tasks. Transform each spec into a YAML file using `vibe normalize`. Global truths are converted without the `prd_` prefix and are used purely for context.
4. **Global Agent Instructions.** Use `vibe remember` to save global guidelines into `instructions/`. Ralph reads all files in this directory and injects them into every agent prompt.
5. **Understand the Ralph loop.** `vibe ralph` reads the `prds/` directory, loads the global truth context files, and sequentially processes `prd_*.yaml` files. It prompts the agent until it emits `<promise>DONE</promise>` before moving on to quality gates.

## Development

Monitor the status of loops using `vibe monitor`:

```bash
vibe monitor
```
""",
}
