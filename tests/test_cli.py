from click.testing import CliRunner

from vibe_tools.cli import cli


def test_cli_base_output():
    runner = CliRunner()

    result = runner.invoke(cli)

    assert result.exit_code == 0
    assert "vibe-tools" in result.output
    assert ".vibe-tools" in result.output


def test_cli_help_only_lists_cli_commands():
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "status" in result.output
    assert "config" in result.output
    assert "servers" in result.output
    assert "project" in result.output
    assert "implement" not in result.output
    assert "plan" not in result.output
    assert "deploy" not in result.output


def test_project_commands_register_repo():
    runner = CliRunner()

    add_result = runner.invoke(cli, ["project", "add", "."])
    list_result = runner.invoke(cli, ["project", "list"])

    assert add_result.exit_code == 0
    assert list_result.exit_code == 0
    assert "PATH" in list_result.output
