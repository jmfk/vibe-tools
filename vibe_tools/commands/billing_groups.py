import datetime
import pathlib
import traceback

import click

from vibe_tools.stats import (
    add_members_to_group,
    create_billing_group,
    generate_billing_groups_report,
    get_billing_group,
    list_billing_groups,
    remove_members_from_group,
)
from vibe_tools.utils import get_cursor_api_key


def register_billing_groups(cli):
    @click.group(name="billing-groups")
    @click.pass_context
    def billing_groups_group(ctx):
        """Manage billing groups for tracking costs per project."""
        pass

    @billing_groups_group.command(name="list")
    @click.option("--billing-cycle", help="Billing cycle date (YYYY-MM-DD).")
    @click.pass_context
    def billing_groups_list(ctx, billing_cycle):
        """List all billing groups."""
        api_key = get_cursor_api_key()
        if not api_key:
            click.echo(
                "❌ CURSOR_API_KEY not found. Set it in .env file or environment."
            )
            return

        try:
            groups_data = list_billing_groups(api_key, billing_cycle)
            reports_dir = pathlib.Path("reports")
            reports_dir.mkdir(parents=True, exist_ok=True)

            markdown = generate_billing_groups_report(groups_data)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = reports_dir / f"report_billing_groups_{timestamp}.md"
            report_path.write_text(markdown, encoding="utf-8")
            click.echo(f"✅ Billing groups report generated: {report_path}")
        except Exception as e:
            click.echo(f"❌ Error: {e}")
            traceback.print_exc()

    @billing_groups_group.command(name="create")
    @click.argument("name")
    @click.pass_context
    def billing_groups_create(ctx, name):
        """Create a new billing group."""
        api_key = get_cursor_api_key()
        if not api_key:
            click.echo("❌ CURSOR_API_KEY not found.")
            return

        try:
            result = create_billing_group(api_key, name)
            group = result.get("group", {})
            click.echo(
                f"✅ Created billing group: {group.get('name')} (ID: {group.get('id')})"
            )
        except Exception as e:
            click.echo(f"❌ Error: {e}")

    @billing_groups_group.command(name="get")
    @click.argument("group_id")
    @click.option("--billing-cycle", help="Billing cycle date (YYYY-MM-DD).")
    @click.pass_context
    def billing_groups_get(ctx, group_id, billing_cycle):
        """Get details of a specific billing group."""
        api_key = get_cursor_api_key()
        if not api_key:
            click.echo("❌ CURSOR_API_KEY not found.")
            return

        try:
            result = get_billing_group(api_key, group_id, billing_cycle)
            groups_data = {"groups": [], "billingCycle": result.get("billingCycle", {})}
            if "group" in result:
                groups_data["groups"] = [result["group"]]

            reports_dir = pathlib.Path("reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            markdown = generate_billing_groups_report(groups_data)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = (
                reports_dir / f"report_billing_group_{group_id}_{timestamp}.md"
            )
            report_path.write_text(markdown, encoding="utf-8")
            click.echo(f"✅ Report generated: {report_path}")
        except Exception as e:
            click.echo(f"❌ Error: {e}")

    @billing_groups_group.command(name="add-members")
    @click.argument("group_id")
    @click.argument("user_ids", nargs=-1, required=True)
    @click.pass_context
    def billing_groups_add_members(ctx, group_id, user_ids):
        """Add members to a billing group."""
        api_key = get_cursor_api_key()
        if not api_key:
            click.echo("❌ CURSOR_API_KEY not found.")
            return

        try:
            result = add_members_to_group(api_key, group_id, list(user_ids))
            group = result.get("group", {})
            click.echo(
                f"✅ Added {len(user_ids)} member(s) to group: {group.get('name')}"
            )
        except Exception as e:
            click.echo(f"❌ Error: {e}")

    @billing_groups_group.command(name="remove-members")
    @click.argument("group_id")
    @click.argument("user_ids", nargs=-1, required=True)
    @click.pass_context
    def billing_groups_remove_members(ctx, group_id, user_ids):
        """Remove members from a billing group."""
        api_key = get_cursor_api_key()
        if not api_key:
            click.echo("❌ CURSOR_API_KEY not found.")
            return

        try:
            result = remove_members_from_group(api_key, group_id, list(user_ids))
            group = result.get("group", {})
            click.echo(
                f"✅ Removed {len(user_ids)} member(s) from group: {group.get('name')}"
            )
        except Exception as e:
            click.echo(f"❌ Error: {e}")

    cli.add_command(billing_groups_group, name="billing-groups")
