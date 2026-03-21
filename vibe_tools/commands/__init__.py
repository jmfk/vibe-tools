def register_all_commands(cli):
    from vibe_tools.commands import docs, kill, project, ps, status, version
    from vibe_tools.servers import servers_cli
    from vibe_tools.setup import setup_cli

    status.register_status(cli)
    docs.register_docs(cli)
    project.register_project(cli)
    ps.register_ps(cli)
    kill.register_kill(cli)
    version.register_version(cli)

    cli.add_command(servers_cli, name="servers")
    cli.add_command(setup_cli, name="config")
