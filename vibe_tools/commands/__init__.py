def register_all_commands(cli):
    """Register all commands with the CLI group."""
    from vibe_tools.commands import (
        architect,
        billing_groups,
        branch,
        branch_resolve,
        branches,
        cost,
        coverage,
        demo_data,
        deploy,
        deps,
        docs,
        history,
        implement,
        implemented,
        infra,
        init,
        investigate,
        issue,
        kill,
        memory,
        migrate,
        monitor,
        normalize,
        pm,
        ps,
        quick_fix,
        rerun,
        setup,
        solve,
        stats,
        status,
        sync,
        test_fix,
        testing,
        view_implement,
    )

    init.register_init(cli)
    migrate.register_migrate(cli)
    view_implement.register_view_implement(cli)
    issue.register_issue(cli)
    test_fix.register_test_fix(cli)
    quick_fix.register_quick_fix(cli)
    coverage.register_coverage(cli)
    normalize.register_normalize(cli)
    history.register_history(cli)
    status.register_status(cli)
    sync.register_sync(cli)
    docs.register_docs(cli)
    cost.register_cost(cli)
    setup.register_setup(cli)
    deps.register_deps(cli)
    architect.register_architect(cli)
    pm.register_pm(cli)
    implement.register_implement(cli)
    # build.register_build(cli)  # TODO: Extract build command
    # devbug.register_devbug(cli)  # TODO: Extract devbug command
    infra.register_infra(cli)
    testing.register_testing(cli)
    deploy.register_deploy(cli)
    memory.register_memory(cli)
    rerun.register_rerun(cli)
    implemented.register_implemented(cli)
    branch.register_branch(cli)
    branches.register_branches(cli)
    branch_resolve.register_branch_resolve(cli)
    ps.register_ps(cli)
    kill.register_kill(cli)
    stats.register_stats(cli)
    billing_groups.register_billing_groups(cli)
    demo_data.register_demo_data(cli)
    investigate.register_investigate(cli)
    solve.register_solve(cli)
    monitor.register_monitor(cli)

    from vibe_tools.servers import servers_cli

    cli.add_command(servers_cli, name="servers")

    from vibe_tools.setup import setup_cli

    cli.add_command(setup_cli, name="config")
