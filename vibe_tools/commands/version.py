import click
import pathlib
import re
from vibe_tools import __version__

def register_version(cli):
    @cli.group()
    def version():
        """Manage package version."""
        pass

    @version.command()
    def show():
        """Show current version."""
        # We import here to get the actual value if it changed in-process (unlikely for CLI)
        from vibe_tools import __version__ as current_v
        click.echo(current_v)

    @version.command()
    @click.argument("part", type=click.Choice(["major", "minor", "patch"]))
    def bump(part):
        """Bump the version (major, minor, or patch)."""
        from vibe_tools import __version__ as current
        
        # Simple semver parsing
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", current)
        if not match:
            click.echo(f"Error: Current version '{current}' is not in major.minor.patch format.")
            return

        major, minor, patch = map(int, match.groups())

        if part == "major":
            major += 1
            minor = 0
            patch = 0
        elif part == "minor":
            minor += 1
            patch = 0
        elif part == "patch":
            patch += 1

        new_version = f"{major}.{minor}.{patch}"
        
        # Update __init__.py
        init_path = pathlib.Path("vibe_tools/__init__.py")
        if init_path.exists():
            content = init_path.read_text()
            new_content = re.sub(r'__version__\s*=\s*".*?"', f'__version__ = "{new_version}"', content)
            init_path.write_text(new_content)
        
        # Update pyproject.toml
        pyproject_path = pathlib.Path("pyproject.toml")
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            # Only update the version in the [project] section
            new_content = re.sub(r'(name\s*=\s*"vibe-tools"\s*\n\s*version\s*=\s*)".*?"', r'\1' + f'"{new_version}"', content)
            pyproject_path.write_text(new_content)

        # Update setup.py
        setup_path = pathlib.Path("setup.py")
        if setup_path.exists():
            content = setup_path.read_text()
            new_content = re.sub(r'(name\s*=\s*"vibe-tools",\s*\n\s*version\s*=\s*)".*?"', r'\1' + f'"{new_version}"', content)
            setup_path.write_text(new_content)

        click.echo(f"✅ Bumped version from {current} to {new_version}")

    cli.add_command(version)
