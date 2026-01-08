import click
from rich.console import Console
from rich.markdown import Markdown
from rich.theme import Theme

from vibe_tools.templates import TEMPLATES


def register_docs(cli):
    @click.command()
    def docs():
        """Display the project documentation (README.md)."""
        content = TEMPLATES.get("README", "Documentation not found in templates.")

        # Custom milder theme
        custom_theme = Theme(
            {
                "markdown.header": "bold white",
                "markdown.h1": "bold white",
                "markdown.h2": "bold white",
                "markdown.h3": "bold white",
                "markdown.link": "blue",
                "markdown.link_url": "dim blue",
                "markdown.code": "cyan",
                "markdown.code_block": "cyan",
                "markdown.item.bullet": "white",
                "markdown.item.number": "white",
                "markdown.block_quote": "dim white",
            }
        )

        console = Console(theme=custom_theme)
        # Using a milder code theme for syntax highlighting
        md = Markdown(content, code_theme="friendly")
        console.print(md)
    cli.add_command(docs)
