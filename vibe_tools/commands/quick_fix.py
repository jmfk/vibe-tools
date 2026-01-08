import pathlib
import re
from typing import Callable, Dict, List, Optional

import click

from vibe_tools.ralph import QuickFixLoop
from vibe_tools.utils import get_prompt, logger, log_issue, log_start, log_success, run_llm, run_command


def register_quick_fix(cli):
    @click.command()
    @click.option(
        "--files",
        "-f",
        multiple=True,
        type=click.Path(exists=True),
        help="Files to fix (can specify multiple times)",
    )
    @click.option(
        "--errors",
        "-e",
        type=str,
        help="Error messages or description of issues",
    )
    @click.option(
        "--context",
        "-c",
        type=str,
        help="Additional context about the problem",
    )
    @click.option(
        "--success-command",
        "-s",
        type=str,
        help="Command to run to check if fix succeeded (returns 0 on success)",
    )
    @click.option(
        "--max-iterations",
        "-m",
        type=int,
        default=5,
        help="Maximum number of fix attempts (default: 5)",
    )
    @click.option(
        "--model",
        type=str,
        default="gemini-3-flash",
        help="LLM model to use (default: gemini-3-flash)",
    )
    @click.option(
        "--debug",
        is_flag=True,
        help="Enable debug logging",
    )
    @click.pass_context
    def quick_fix(
        ctx,
        files,
        errors,
        context,
        success_command,
        max_iterations,
        model,
        debug,
    ):
        """
        Quick fix loop using direct LLM calls (no agent wrapper).
        Faster than agent-based loops for targeted fixes.
        """
        if not files:
            click.echo("❌ Error: At least one file must be specified with --files")
            return 1

        if not errors:
            click.echo("❌ Error: Error messages must be provided with --errors")
            return 1

        if not success_command:
            click.echo("❌ Error: Success command must be provided with --success-command")
            return 1

        # Read file contents
        file_contents = {}
        for file_path in files:
            path = pathlib.Path(file_path)
            try:
                file_contents[str(path)] = path.read_text()
            except Exception as e:
                logger.error(f"Error reading {path}: {e}")
                click.echo(f"❌ Error reading {path}: {e}")
                return 1

        # Build success function
        def success_fn() -> bool:
            stdout, code = run_command(
                success_command.split() if isinstance(success_command, str) else success_command,
                check=False,
            )
            if code == 0:
                return True
            if debug:
                logger.debug(f"Success check failed (code {code}): {stdout}")
            return False

        # Track LLM outputs for retry context
        llm_outputs = []

        # Build prompt builder
        def prompt_builder(iteration: int) -> str:
            try:
                template = get_prompt("quick_fix_prompt.txt")
            except FileNotFoundError as e:
                raise RuntimeError(f"Quick fix prompt template not found: {e}")

            # Format files section
            files_section = "\n".join(
                [f"- {path} ({len(content)} chars)" for path, content in file_contents.items()]
            )

            # Build context with file contents
            context_with_files = context or ""
            if context_with_files:
                context_with_files += "\n\n"
            context_with_files += "FILE CONTENTS:\n"
            for path, content in file_contents.items():
                context_with_files += f"\n--- {path} ---\n{content}\n"

            # Include previous attempt info if retrying
            if iteration > 1 and llm_outputs:
                context_with_files += f"\n\nPREVIOUS ATTEMPT (iteration {iteration - 1}):\n"
                context_with_files += llm_outputs[-1][:1000] + "..."

            return template.format(
                context=context_with_files or "No additional context provided.",
                errors=errors,
                files=files_section,
            )

        # Custom loop that applies fixes
        log_start("Quick Fix", f"Quick fix loop (max {max_iterations} iterations)")
        logger.info("🔄 Starting Quick Fix Loop...")

        # Check if already successful
        if success_fn():
            log_success("Quick Fix", "Already successful, no fix needed")
            logger.info("✅ Quick fix is already successful.")
            return 0

        for iteration in range(1, max_iterations + 1):
            logger.info(f"🔧 [Quick Fix] Fix attempt {iteration}/{max_iterations}...")

            # Build prompt for this iteration
            try:
                prompt = prompt_builder(iteration)
            except Exception as e:
                logger.error(f"Error building prompt: {e}")
                log_issue("Quick Fix", iteration, max_iterations, f"Prompt build error: {e}")
                return 1

            # Call LLM directly
            try:
                llm_output = run_llm(prompt, model=model, debug=debug)
                llm_outputs.append(llm_output)
                logger.debug(f"LLM output (iteration {iteration}): {llm_output[:500]}...")
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                log_issue("Quick Fix", iteration, max_iterations, f"LLM call error: {e}")
                if iteration < max_iterations:
                    continue
                else:
                    return 1

            # Parse and apply fixes from LLM output
            def apply_fixes_from_output(output: str) -> bool:
                """Parse LLM output and apply file fixes."""
                # Parse <file path="...">...</file> tags
                file_pattern = r'<file\s+path=["\']([^"\']+)["\']>([\s\S]*?)</file>'
                matches = re.findall(file_pattern, output)

                if not matches:
                    # Try alternative format without quotes
                    file_pattern = r'<file\s+path=([^\s>]+)>([\s\S]*?)</file>'
                    matches = re.findall(file_pattern, output)

                if not matches:
                    logger.warning("No <file> tags found in LLM output")
                    if debug:
                        logger.debug(f"LLM output: {output[:500]}")
                    return False

                applied_count = 0
                for file_path, content in matches:
                    # Normalize path
                    file_path = file_path.strip().strip('"').strip("'")
                    path = pathlib.Path(file_path)

                    # Check if this is one of our target files
                    target_path = None
                    for target_file in files:
                        target = pathlib.Path(target_file)
                        if str(path) == str(target) or path.name == target.name:
                            target_path = target
                            break

                    if not target_path:
                        logger.debug(f"Skipping file not in target list: {file_path}")
                        continue

                    try:
                        # Write the fixed content
                        content = content.strip()
                        target_path.write_text(content)
                        applied_count += 1
                        logger.info(f"✅ Applied fix to {target_path}")
                        # Update our file_contents for next iteration
                        file_contents[str(target_path)] = content
                    except Exception as e:
                        logger.error(f"Error writing {target_path}: {e}")
                        return False

                if applied_count == 0:
                    logger.warning("No files were updated from LLM output")
                    return False

                logger.info(f"Applied fixes to {applied_count} file(s)")
                return True

            # Apply fixes
            if not apply_fixes_from_output(llm_output):
                logger.warning(f"Failed to apply fixes from iteration {iteration}")
                if iteration < max_iterations:
                    continue

            # Check if fix succeeded
            try:
                if success_fn():
                    log_success("Quick Fix", f"Fix succeeded after {iteration} iteration(s)")
                    logger.info(f"✅ Quick fix succeeded after {iteration} iteration(s).")
                    click.echo(f"\n✅ Quick fix succeeded after {iteration} iteration(s)!")
                    return 0
            except Exception as e:
                logger.warning(f"Error checking success: {e}")
                log_issue("Quick Fix", iteration, max_iterations, f"Success check error: {e}")

            # Not successful yet
            if iteration < max_iterations:
                log_issue("Quick Fix", iteration, max_iterations, "Fix attempt did not succeed, retrying...")
                logger.info(f"⚠️  Fix attempt {iteration} did not succeed, retrying...")
            else:
                log_issue("Quick Fix", iteration, max_iterations, "Fix failed after all iterations")
                logger.error(f"❌ Quick fix failed after {max_iterations} iterations.")
                click.echo(f"\n❌ Quick fix failed after {max_iterations} iterations.")
                return 1

        return 1
