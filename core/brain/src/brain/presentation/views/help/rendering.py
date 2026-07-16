# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Rendered help documents for the brain CLI."""

from __future__ import annotations

# Application Modules Imports
from brain.application.memory.paths import BrainStoreError
from brain.presentation.commands.models import CommandSchema
from brain.presentation.terminal import render_help
from brain.presentation.views.help.formatting import format_flag_documentation, get_syntax


def get_help_text(color: bool = False, domain: str | None = None) -> str:
    """
    Generate CLI usage instructions dynamically from schemas.

    Args:
        color (bool): Whether to enable ANSI color output.
        domain (str | None): Optional domain filter.

    Returns:
        str: Rendered help text.
    """
    from brain.presentation.commands.registry import COMMAND_MODULES

    command_schemas = [module.SCHEMA for module in COMMAND_MODULES]
    command_names = [command.name for command in command_schemas]
    domain_filter = domain.casefold().strip() if domain else None
    domain_commands: dict[str, list[str]] = {}
    parameter_docs: dict[str, str] = {}

    for command in command_schemas:
        command_domain = str(getattr(command, "domain", "general"))
        if domain_filter and command_domain.casefold() != domain_filter:
            continue
        domain_commands.setdefault(command_domain, []).append(f"  {get_syntax(command)} - {command.help}")
        collect_parameter_docs(command=command, parameter_docs=parameter_docs)

    if domain_filter and not domain_commands:
        raise BrainStoreError(f"Unknown help topic: {domain}. Run `help` to list commands.")

    if not domain_filter:
        parameter_docs["-c, --color"] = "Enable ANSI color output."

    if domain_filter:
        raw_text = render_domain_help_text(
            domain_name=next(iter(domain_commands.keys())),
            command_lines=sorted(next(iter(domain_commands.values()))),
            parameter_docs=parameter_docs,
        )
    else:
        raw_text = render_full_help_text(domain_commands=domain_commands, parameter_docs=parameter_docs)
    return render_help(raw_text, color, command_names)


def get_short_help_text(topic: str | None = None, color: bool = False) -> str:
    """
    Generate a compact domain and command index.

    Args:
        topic (str | None): Optional command or domain topic.
        color (bool): Whether to enable ANSI color output.

    Returns:
        str: Rendered short help text.
    """
    from brain.presentation.commands.registry import COMMAND_MODULES

    command_schemas = [module.SCHEMA for module in COMMAND_MODULES]
    command_names = [command.name for command in command_schemas]
    requested_topic = str(topic or "").strip().casefold()
    domain_commands: dict[str, list[str]] = {}
    for command in command_schemas:
        domain = str(getattr(command, "domain", "general")).casefold()
        if requested_topic and requested_topic not in (domain, command.name.casefold()):
            continue
        domain_commands.setdefault(domain, []).append(command.name)

    if requested_topic and not domain_commands:
        raise BrainStoreError(f"Unknown help topic: {topic}. Run `help` to list commands.")

    lines: list[str] = ["Environment Management System", "", "Domains:"]
    for domain in sorted(domain_commands):
        lines.append(f"  {domain}:")
        for command_name in sorted(domain_commands[domain]):
            lines.append(f"    - {command_name}")
    return render_help("\n".join(lines), color, command_names)


def get_command_help_text(topic: str, color: bool = False) -> str:
    """
    Generate focused help for one registered command or command domain.

    Args:
        topic (str): Command or domain topic.
        color (bool): Whether to enable ANSI color output.

    Returns:
        str: Rendered command or domain help text.
    """
    from brain.presentation.commands.registry import COMMAND_MODULES

    command_schemas = [module.SCHEMA for module in COMMAND_MODULES]
    command_names = [command.name for command in command_schemas]
    requested_topic = topic.strip()
    command = next((schema for schema in command_schemas if schema.name == requested_topic), None)
    if command is None:
        return get_help_text(color=color, domain=requested_topic)

    parameter_lines = build_command_parameter_lines(command=command)
    parameters = "\n".join(parameter_lines) if parameter_lines else "  None - This command has no parameters."
    raw_text = f"""Environment Management System

Command:
  {get_syntax(command)} - {command.help}

Domain:
  {command.domain} - Command group.

Parameters:
{parameters}"""
    return render_help(raw_text, color, command_names)


def collect_parameter_docs(command: CommandSchema, parameter_docs: dict[str, str]) -> None:
    """
    Collect option parameter documentation from one command.

    Args:
        command (CommandSchema): Command schema.
        parameter_docs (dict[str, str]): Mutable parameter documentation map.
    """
    for argument in command.arguments:
        if not any(flag.startswith("-") for flag in argument.flags):
            continue
        flag_doc = format_flag_documentation(
            argument.flags,
            has_value=argument.action != "store_true",
            long_only=False,
            cmd_domain=command.domain,
        )
        parameter_docs[flag_doc] = argument.help


def build_command_parameter_lines(command: CommandSchema) -> list[str]:
    """
    Build focused parameter documentation for one command.

    Args:
        command (CommandSchema): Command schema.

    Returns:
        list[str]: Printable parameter lines.
    """
    parameter_lines: list[str] = []
    for argument in command.arguments:
        is_flag = any(flag.startswith("-") for flag in argument.flags)
        if is_flag:
            flag_doc = format_flag_documentation(
                argument.flags,
                has_value=argument.action != "store_true",
                long_only=False,
                cmd_domain=command.domain,
            )
            parameter_lines.append(f"  {flag_doc} - {argument.help}")
        else:
            name = argument.flags[0].upper().replace("-", "_")
            parameter_lines.append(f"  <{name}> - {argument.help}")
    return parameter_lines


def render_full_help_text(domain_commands: dict[str, list[str]], parameter_docs: dict[str, str]) -> str:
    """
    Render the full help document body before ANSI coloring.

    Args:
        domain_commands (dict[str, list[str]]): Command lines grouped by domain.
        parameter_docs (dict[str, str]): Parameter documentation by flag.

    Returns:
        str: Raw help text.
    """
    command_sections: list[str] = []
    for domain in sorted(domain_commands):
        lines = sorted(domain_commands[domain])
        if not lines:
            continue
        command_sections.append(f"{domain.capitalize()}:")
        command_sections.extend(lines)
        command_sections.append("")

    parameters_section = "\n".join(f"  {flag_doc} - {help_text}" for flag_doc, help_text in sorted(parameter_docs.items()))
    return f"""Environment Management System

Commands list:
{"\n".join(command_sections).strip()}

Parameters:
{parameters_section}

Notation declaration:
  - Memory Domain (<MEMORY_DOMAIN>): Namespaces to categorize stored workspace memories.
  - Log Domain (<LOG_DOMAIN>): Identifiers to tag log entries representing affected subdomains.
  - Task Domain (<TASK_DOMAIN>): Checklist scopes for classifying backlog items.
  - Notation: Any *_DOMAIN value accepts both direct dot notation (e.g. a.b.c) and string notation (e.g. "a.b.c").
  - Shortcut: Specify domain and key together as domain.key (e.g. get-memory-entry domain.key).
  - Leaf values: Primitives are saved as keys inside domains.

Additional notes:
  - Stdin Fallback: set-memory-entry reads from stdin if no value is provided or if '-' is passed.
  - Confirmation: delete-memory-entry requires --confirm <MEMORY_DOMAIN> when deleting an entire memory domain.
  - JSON output: memory-structure, set-memory-entry, get-memory-entry, query, and check-workspace support --json for machine-readable output."""


def render_domain_help_text(
    domain_name: str,
    command_lines: list[str],
    parameter_docs: dict[str, str],
) -> str:
    """
    Render a domain-scoped help document body before ANSI coloring.

    Args:
        domain_name (str): Command domain.
        command_lines (list[str]): Command lines for the domain.
        parameter_docs (dict[str, str]): Parameter documentation by flag.

    Returns:
        str: Raw help text.
    """
    parameters_section = "\n".join(f"  {flag_doc} - {help_text}" for flag_doc, help_text in sorted(parameter_docs.items()))
    return f"""Environment Management System

Domain:
  {domain_name} - Command group.

Commands:
{"\n".join(command_lines)}

Parameters:
{parameters_section}"""
