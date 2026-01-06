import pathlib

import pytest

from vibe_tools.prd_writer import PRDWriter


def _create_prompt_template(target: pathlib.Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    prompt_path = target / "prd_generation_prompt.txt"
    prompt_path.write_text("TITLE: {title}\nSUMMARY: {summary}\nQA:\n{qa}")


def test_next_spec_path_increments(tmp_path: pathlib.Path) -> None:
    prompts_dir = tmp_path / "prompts"
    specs_dir = tmp_path / "specs"
    _create_prompt_template(prompts_dir)
    specs_dir.mkdir()
    (specs_dir / "prd_01_existing.md").write_text("Existing")

    writer = PRDWriter(specs_dir=specs_dir, prompts_dir=prompts_dir)
    next_path = writer._next_spec_path("New Feature")

    assert next_path.name.startswith("prd_02_new-feature")


def test_interview_writes_spec(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompts_dir = tmp_path / "prompts"
    specs_dir = tmp_path / "specs"
    _create_prompt_template(prompts_dir)
    specs_dir.mkdir()

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/dspy")
    answers = iter(["Primary benefit", "Key constraint"])
    monkeypatch.setattr(
        "click.prompt", lambda prompt, default="", show_default=False: next(answers)
    )

    responses = [
        {"questions": ["What is the user impact?"], "satisfied": False, "summary": "step 1"},
        {"questions": ["Any constraints?"], "satisfied": True, "summary": "final"},
    ]

    def fake_dspy(_payload):
        return responses.pop(0)

    writer = PRDWriter(
        prompts_dir=prompts_dir,
        specs_dir=specs_dir,
        dspy_runner=fake_dspy,
        agent_runner=lambda prompt: ("# Generated PRD\n", 0),
    )

    generated = writer.create_prd("User Onboarding")

    assert generated.exists()
    assert generated.name.startswith("prd_01_user-onboarding")
    assert generated.read_text() == "# Generated PRD\n"


def test_next_spec_path_increments_infra(tmp_path: pathlib.Path) -> None:
    prompts_dir = tmp_path / "prompts"
    specs_dir = tmp_path / "specs" / "infra"
    _create_prompt_template(prompts_dir)
    specs_dir.mkdir(parents=True)
    (specs_dir / "prd_infra_01_existing.md").write_text("Existing")

    writer = PRDWriter(specs_dir=specs_dir, prompts_dir=prompts_dir, prd_type="infra")
    next_path = writer._next_spec_path("Kubernetes")

    assert next_path.name.startswith("prd_infra_02_kubernetes")

