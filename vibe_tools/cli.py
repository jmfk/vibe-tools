import atexit
import builtins
import logging
import os
import pathlib
import sys
from typing import List

import click
from dotenv import find_dotenv, load_dotenv

import vibe_tools
from vibe_tools import __version__
from vibe_tools.command_output import output_manager
from vibe_tools.commands import register_all_commands
from vibe_tools.cost import finalize_cost_report
from vibe_tools.setup import SERVICE_DEFINITIONS
from vibe_tools.utils import (
    CONFIG_FILE,
    COSTS_DIR,
    LOGS_DIR,
    VIBE_PROJECT_DIR,
    enable_console_debug,
    get_cursor_api_key,
    get_google_api_key,
    get_project_root,
    load_config,
    logger,
    set_console_level,
    setup_logging,
)

load_dotenv(find_dotenv() or ".env")


if "--server" in sys.argv:
    if len([arg for arg in sys.argv if not arg.startswith("-")]) <= 1:
        import json

        try:
            line = sys.stdin.readline()
            if line:
                payload = json.loads(line)
                command = payload.get("command")
                args = payload.get("args", [])
                settings = payload.get("settings", {})

                new_argv = [sys.argv[0], "--server"]
                for arg in sys.argv[1:]:
                    if arg.startswith("-") and arg != "--server":
                        new_argv.append(arg)

                if settings.get("debug") or payload.get("debug"):
                    new_argv.append("--debug")
                if settings.get("verbose") or payload.get("verbose"):
                    new_argv.append("--verbose")
                if settings.get("stream") is not None:
                    new_argv.append("--stream" if settings["stream"] else "--no-stream")
                if settings.get("agent"):
                    new_argv.extend(["--agent", settings["agent"]])

                if command and command != "vibe":
                    new_argv.append(command)
                new_argv.extend(args)
                sys.argv = new_argv
        except Exception:
            pass

    output_manager.set_server_mode(True)

    def server_prompt(
        text,
        default=None,
        hide_input=False,
        confirmation_prompt=False,
        type=None,
        value_proc=None,
        prompt_suffix=": ",
        show_default=True,
        err=False,
        show_choices=True,
    ):
        del default, hide_input, confirmation_prompt, type, value_proc
        del prompt_suffix, show_default, err, show_choices
        return output_manager.get_input(text)

    def server_confirm(
        text,
        default=False,
        abort=False,
        prompt_suffix=": ",
        show_default=True,
        err=False,
    ):
        del default, abort, prompt_suffix, show_default, err
        return output_manager.get_input(f"{text} (y/n)").lower() in {
            "y",
            "yes",
            "true",
            "1",
        }

    click.prompt = server_prompt
    click.confirm = server_confirm
    builtins.input = lambda prompt="": output_manager.get_input(prompt)


class OrderedGroup(click.Group):
    def list_commands(self, ctx: click.Context) -> List[str]:
        order = [
            "status",
            "config",
            "servers",
            "project",
            "docs",
            "ps",
            "kill",
            "version",
        ]
        commands = super().list_commands(ctx)
        ordered = [command for command in order if command in commands]
        return ordered + sorted(command for command in commands if command not in order)


@click.group(invoke_without_command=True, cls=OrderedGroup)
@click.option("--server", is_flag=True, default=False, help="Enable JSON server mode.")
@click.option("--debug", is_flag=True, default=False, help="Enable debug logging.")
@click.option("--verbose/--no-verbose", default=None, help="Show extra terminal output.")
@click.option("--log/--no-log", default=None, help="Write logs under .vibe-tools/logs.")
@click.option("--stream/--no-stream", default=None, help="Default agent stream mode.")
@click.option(
    "--agent",
    type=click.Choice(["cursor-agent", "claude", "antigravity", "gemini"]),
    default=None,
    help="Default agent.",
)
@click.option("--model", default=None, help="Override model.")
@click.version_option(
    version=__version__,
    message="%(prog)s, version %(version)s\n(package: "
    + str(getattr(vibe_tools, "__file__", "?"))
    + ")",
)
@click.pass_context
def cli(ctx, server, debug, verbose, log, stream, agent, model):
    project_root = get_project_root()
    if project_root != pathlib.Path.cwd():
        os.chdir(project_root)
        logger.debug(f"Changed cwd to {project_root}")

    setup_logging(ctx.invoked_subcommand or "info", log=bool(log) if log is not None else True)
    atexit.register(finalize_cost_report)

    if server:
        def server_exit_handler():
            try:
                sys.stdout.flush()
            except Exception:
                pass
            code, data = output_manager.get_final_result()
            output_manager.emit_server_message("result", {"code": code, "data": data})

        atexit.register(server_exit_handler)

    config = load_config()
    if stream is None:
        stream = config.get("agent", {}).get("stream", config.get("stream", False))
    if agent is None:
        agent = config.get("agent", {}).get("agent", "cursor-agent")

    if debug:
        enable_console_debug()
        verbose = True if verbose is None else verbose
    elif verbose:
        set_console_level(logging.INFO)
    else:
        set_console_level(logging.WARNING)

    ctx.ensure_object(dict)
    ctx.obj["agent"] = agent
    ctx.obj["model"] = model
    ctx.obj["stream"] = stream
    ctx.obj["verbose"] = verbose if verbose is not None else False
    ctx.obj["default_budget"] = config.get("default_budget", 5.0)

    if ctx.invoked_subcommand is None:
        click.echo("vibe-tools")
        click.echo(f"  Project Root:  {project_root}")
        click.echo(f"  Runtime Dir:   {project_root / VIBE_PROJECT_DIR}")
        click.echo(f"  Config File:   {project_root / CONFIG_FILE}")
        click.echo(f"  Logs Dir:      {project_root / LOGS_DIR}")
        click.echo(f"  Costs Dir:     {project_root / COSTS_DIR}")
        click.echo(f"  Agent:         {agent}")
        if model:
            click.echo(f"  Model:         {model}")
        click.echo(f"  Stream:        {'ON' if stream else 'OFF'}")
        click.echo(f"  Default Budget:${ctx.obj['default_budget']:.2f}")
        click.echo(f"  Google API:    {'SET' if get_google_api_key() else 'NOT SET'}")
        click.echo(f"  Cursor API:    {'SET' if get_cursor_api_key() else 'NOT SET'}")

        services = config.get("services", {})
        if services:
            click.echo("  Services:")
            for service_key in sorted(services):
                metadata = SERVICE_DEFINITIONS.get(service_key, {})
                display_name = metadata.get("display", service_key)
                host = services[service_key].get("host", "localhost")
                port = services[service_key].get("port", "n/a")
                click.echo(f"    {display_name}: {host}:{port}")

        click.echo("\nAvailable commands:")
        for command in cli.list_commands(ctx):
            command_obj = cli.get_command(ctx, command)
            if command_obj:
                click.echo(f"  {command:<10} {command_obj.get_short_help_str()}")
        click.echo("\nRun 'vibe --help' for full options.")


register_all_commands(cli)


if __name__ == "__main__":
    cli()
