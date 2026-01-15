def register_all_commands(cli):
    """Register all commands with the CLI group."""
    from vibe_tools.commands import (
        billing_groups,
        coverage,
        demo_data,
        deploy,
        deps,
        docs,
        implement,
        infra,
        init,
        kill,
        memory,
        migrate,
        plan,
        project,
        ps,
        quick_fix,
        setup,
        start,
        status,
        sync,
        test_fix,
        testing,
        usage,
    )

    init.register_init(cli)
    migrate.register_migrate(cli)
    plan.register_plan(cli)
    # issue.register_issue(cli) # Integrated into plan
    # prd.register_prd(cli)     # Integrated into plan
    test_fix.register_test_fix(cli)
    quick_fix.register_quick_fix(cli)
    coverage.register_coverage(cli)
    project.register_project(cli)
    status.register_status(cli)
    sync.register_sync(cli)
    docs.register_docs(cli)
    setup.register_setup(cli)
    start.register_start(cli)
    deps.register_deps(cli)
    implement.register_implement(cli)
    # build.register_build(cli)  # TODO: Extract build command
    # devbug.register_devbug(cli)  # TODO: Extract devbug command
    infra.register_infra(cli)
    testing.register_testing(cli)
    deploy.register_deploy(cli)
    memory.register_memory(cli)
    ps.register_ps(cli)
    kill.register_kill(cli)
    billing_groups.register_billing_groups(cli)
    demo_data.register_demo_data(cli)
    usage.register_usage(cli)

    from vibe_tools.servers import servers_cli

    cli.add_command(servers_cli, name="servers")

    from vibe_tools.setup import setup_cli

    cli.add_command(setup_cli, name="config")
