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
    "review_prompt.txt": """You are a Senior Full-Stack Developer. Review the recent changes in 'src/' and 'frontend/' against the provided PRD.

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

RECENT DIFFS (src/):
{last_diff}

TASK:
1. Identify which PRD is likely being processed (look at branch name).
2. Summarize the progress in 'src/'.
3. Detect any "BLOCKER" messages in files or signs of failure/stalling.
4. Provide a HEALTH STATUS: [HEALTHY], [STALLED], or [FAILED].
5. Keep it very concise (max 10 lines).
""",
    "Makefile": """.PHONY: test test-backend test-frontend test-infra test-integration test-regression lint lint-backend lint-frontend

test: test-backend test-frontend test-infra test-integration test-regression lint

test-backend:
	@echo "Running backend tests... (dummy)"
	@exit 0

test-frontend:
	@echo "Running frontend tests... (dummy)"
	@exit 0

test-infra:
	@echo "Running infra tests... (dummy)"
	@exit 0

test-integration:
	@echo "Running integration tests... (dummy)"
	@exit 0

test-regression:
	@echo "Running regression tests... (dummy)"
	@exit 0

lint: lint-backend lint-frontend

lint-backend:
	@echo "Running backend linting... (dummy)"
	@exit 0

lint-frontend:
	@echo "Running frontend linting... (dummy)"
	@exit 0
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
}

