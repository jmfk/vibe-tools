import click
import pathlib
from vibe_tools.utils import GlobalProjectRegistry, out_success, out_info, out_error, get_project_name

def register_project(cli):
    @cli.group()
    def project():
        """Manage global vibe projects."""
        pass

    @project.command(name="list")
    def list_projects():
        """List all registered projects."""
        projects = GlobalProjectRegistry.list_projects()
        if not projects:
            out_info("No projects registered.")
            return

        click.echo(f"{'ID':<38} {'NAME':<20} {'PATH'}")
        click.echo("-" * 80)
        for p in projects:
            click.echo(f"{p['id']:<38} {p['name']:<20} {p['path']}")

    @project.command(name="add")
    @click.argument("path", type=click.Path(exists=True), default=".")
    @click.option("--name", help="Custom name for the project.")
    def add_project(path, name):
        """Add a folder as a vibe project."""
        path_obj = pathlib.Path(path).resolve()
        if not name:
            # Try to get project name from the path or git
            import os
            old_cwd = os.getcwd()
            os.chdir(path_obj)
            try:
                name = get_project_name()
            finally:
                os.chdir(old_cwd)
        
        GlobalProjectRegistry.add_project(name, str(path_obj))
        out_success(f"✅ Registered project '{name}' at {path_obj}")

    @project.command(name="remove")
    @click.argument("name_or_id")
    def remove_project(name_or_id):
        """Remove a project from the registry."""
        GlobalProjectRegistry.remove_project(name_or_id)
        out_success(f"✅ Removed project '{name_or_id}' from registry.")
