import click
import datetime
import json
from vibe_tools.issues import Issue, IssueBody, save_issue, generate_issue_id, BACKLOG_DIR
from vibe_tools.utils import run_llm, get_prompt

def get_interactive_prompt():
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.formatted_text import HTML

    kb = KeyBindings()

    @kb.add("c-s")
    @kb.add("c-a")
    def _(event):
        event.app.exit(result=event.app.current_buffer.text)

    @kb.add("c-q")
    def _(event):
        event.app.exit(result=None)

    session = PromptSession(key_bindings=kb)
    
    click.echo(click.style("Enter issue prompt (Ctrl-S or Ctrl-A to save, Ctrl-Q to quit):", fg="cyan"))
    click.echo(click.style("-" * 60, fg="bright_black"))
    
    result = session.prompt(multiline=True)
    return result

def register_issue_add(issue_group):
    @issue_group.command(name="add")
    @click.argument("prompt", required=False)
    @click.option("--title", help="Explicitly set title")
    @click.option("--severity", type=click.Choice(["low", "medium", "high", "critical"]), help="Explicitly set severity")
    @click.option("--service", help="Explicitly set service")
    @click.pass_context
    def add_issue(ctx, prompt, title, severity, service):
        """Create a new local issue from a prompt."""
        if not prompt:
            prompt = get_interactive_prompt()
            if not prompt:
                click.echo("Aborted.")
                return

        click.echo("🤖 Analyzing prompt and generating issue details...")
        
        template_str = get_prompt("issue_add_prompt.txt")
        rendered_prompt = template_str.replace("{{ prompt }}", prompt)
        
        response = run_llm(rendered_prompt)
        
        # Parse JSON from response
        try:
            # Simple JSON extraction in case there's markdown
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "{" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
            else:
                json_str = response
            
            data = json.loads(json_str)
        except Exception as e:
            click.echo(f"Error parsing AI response: {e}")
            click.echo(f"Raw response: {response}")
            return

        # Apply overrides
        issue_title = title or data.get("title", "Untitled Issue")
        issue_severity = severity or data.get("severity", "medium")
        issue_service = service or data.get("service", "")
        issue_summary = data.get("summary", "")
        
        now = datetime.datetime.now().isoformat()
        issue_id = generate_issue_id()
        
        issue = Issue(
            id=issue_id,
            title=issue_title,
            status="backlog",
            severity=issue_severity,
            service=issue_service,
            created_at=now,
            updated_at=now,
            body=IssueBody(summary=issue_summary),
        )
        
        save_issue(issue)
        
        from vibe_tools.commands.sync import sync_issues
        sync_issues(quiet=True)
        
        issue_path = BACKLOG_DIR / f"{issue.id}.md"
        
        click.echo(f"✅ Issue initialized!")
        click.echo(f"ID:       {issue.id}")
        click.echo(f"Title:    {issue.title}")
        click.echo(f"Location: {issue_path.absolute()}")

        # Phase 2: Clarity Check and Agentic Refinement
        click.echo("\n🔍 Checking if more context is needed...")
        clarity_template = get_prompt("issue_clarity_check_prompt.txt")
        clarity_prompt = clarity_template.replace("{{ prompt }}", prompt)\
                                       .replace("{{ title }}", issue.title)\
                                       .replace("{{ summary }}", issue.body.summary)\
                                       .replace("{{ issue_path }}", str(issue_path.absolute()))
        
        clarity_response = run_llm(clarity_prompt)
        try:
            if "```json" in clarity_response:
                json_str = clarity_response.split("```json")[1].split("```")[0].strip()
            elif "{" in clarity_response:
                json_str = clarity_response[clarity_response.find("{"):clarity_response.rfind("}")+1]
            else:
                json_str = clarity_response
            clarity_data = json.loads(json_str)
        except Exception:
            clarity_data = {"needs_more_context": False}

        if clarity_data.get("needs_more_context"):
            click.echo("🛠️  Agent starting research for more context...")
            agent_type = ctx.obj.get("agent", "cursor-agent")
            stream = ctx.obj.get("stream", False)
            
            agent_prompt = clarity_data.get("agent_prompt")
            user_feedback = ""
            
            from vibe_tools.utils import get_agent_command, run_agent
            
            while True:
                full_prompt = agent_prompt
                if user_feedback:
                    full_prompt += f"\n\nUser Feedback to your questions:\n{user_feedback}"
                
                cmd = get_agent_command(agent_type, full_prompt)
                output, _ = run_agent(cmd, stream=stream)
                
                # Check for questions from the agent
                lines = output.splitlines()
                questions = [line.replace("QUESTION:", "").strip() for line in lines if "QUESTION:" in line]
                
                if questions:
                    click.echo("\n❓ The agent has some questions for you:")
                    user_feedback = ""
                    for q in questions:
                        answer = click.prompt(f"  > {q}")
                        user_feedback += f"Q: {q}\nA: {answer}\n"
                    click.echo("\n🔄 Feeding back your answers to the agent...")
                    continue
                else:
                    break
            
            click.echo("✅ Agent refinement complete.")
            # Reload issue to show updated path if needed (though it shouldn't change)
            # but we show the location again
            click.echo(f"Updated Issue Location: {issue_path.absolute()}")
