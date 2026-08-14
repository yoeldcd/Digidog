# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Render authority-aware help documents for the brain CLI.

Translates registered command schemas into full, short, domain, and command views
while preserving their output order and making protected access explicit without
exposing a password or its configured digest.
The view is the presentation boundary for authority decisions: denied schemas stay
hidden, digest-backed requests are marked, and manual placeholders are materialized
through the shared profile resolver.
"""

from __future__ import annotations

# Presentation dependencies: authority, schema, profile, and terminal-formatting services.
from typing import Final

from brain.application.authority import AuthorityService
from brain.application.memory.paths import BrainStoreError
from brain.application.profiles.service import render_profile_template_variables
from brain.presentation.commands.models import CommandSchema, PayloadSchema
from brain.presentation.terminal import render_help
from brain.presentation.views.help.formatting import (
    format_flag_documentation,
    get_syntax,
)

_HELP_ACCESS_STATUSES: Final[frozenset[str]] = frozenset(
    {"execute", "request_password"}
)
_PASSWORD_STDIN_HELP: Final[str] = (
    "Read one password line from standard input for password-protected commands."
)


def _permission_status(decision: object) -> str:
    """Normalize one authority decision to the status consumed by help rendering.

    Accepts the typed decision returned by the permission service and the historical
    two-item tuple shape; malformed values resolve to ``deny`` so visibility fails closed.

    Args:
        decision: AuthorityDecision instance or historical two-value result.

    Returns:
        str: execute, request_password, or deny. Malformed values fail closed
        as deny.
    """
    decision_status = getattr(decision, "status", None)

    # Typed decision path: preserve the explicit service status for policy mapping.

    if isinstance(decision_status, str):
        return decision_status

    # Legacy result path: support only the historical two-item execute/deny convention.

    if isinstance(decision, tuple) and len(decision) == 2:
        return "execute" if bool(decision[0]) else "deny"

    return "deny"


def _has_nonempty_password_digest(decision: object) -> bool:
    """Check whether a protected help entry has configured approval material.

    Help may label a request-password command only when a nonblank digest exists;
    this avoids advertising an approval path that runtime cannot safely complete and
    never renders the digest itself.

    Args:
        decision: Authority decision containing an optional password digest.

    Returns:
        bool: True only when the decision exposes non-whitespace digest text.
    """
    password_digest = getattr(decision, "password_digest", "")

    return isinstance(password_digest, str) and bool(password_digest.strip())


def _get_authorized_schema_entries(
    authority: str | None,
) -> tuple[tuple[CommandSchema, str], ...]:
    """Build the ordered command catalog visible to one authority.

    Evaluates each registered schema at the authority boundary and keeps only
    executable or digest-backed request entries, preserving registry order while
    failing closed for missing identity or unconfigured protected access.

    Args:
        authority: Declared caller authority. Missing or blank authority fails
            closed and returns no schemas.

    Returns:
        tuple[tuple[CommandSchema, str], ...]: Immutable schema/status entries
        for executable or password-requested commands. Denied commands are
        omitted.
    """
    from brain.presentation.commands.registry import COMMAND_MODULES

    # Authority boundary: absent or blank identity cannot enumerate command schemas.

    if not isinstance(authority, str) or not authority.strip():
        return ()

    auth_service = AuthorityService()
    entries: list[tuple[CommandSchema, str]] = []

    # Registry traversal: evaluate every schema while retaining registration order.

    for module in COMMAND_MODULES:
        schema = module.SCHEMA

        decision = auth_service.evaluate_command_permission(
            schema.name, authority
        )
        access_status = _permission_status(decision)

        # Secret-safety gate: hide approval requests with no configured digest.

        if access_status == "request_password" and not _has_nonempty_password_digest(
            decision
        ):
            continue

        # Visibility policy: expose only executable or digest-backed request entries.

        if access_status in _HELP_ACCESS_STATUSES:
            entries.append((schema, access_status))

    return tuple(entries)


def _filter_schemas_for_authority(
    authority: str | None = None,
) -> list[CommandSchema]:
    """Return visible command schemas without their per-command access labels.

    Delegates to the ordered catalog helper so callers share deny-by-default
    filtering and the rule that hides password requests lacking approval material.

    Args:
        authority: Declared caller authority. Missing or blank authority fails
            closed and returns no schemas.

    Returns:
        list[CommandSchema]: Schemas visible for execution or password request.
    """

    # Projection: strip access labels only after ordered visibility filtering.

    return [
        schema
        for schema, _access_status in _get_authorized_schema_entries(authority)
    ]


def _access_suffix(access_status: str) -> str:
    """Format the non-secret access marker used beside protected help commands.

    Distinguishes approval-required entries for operators without copying password
    material into terminal text or the JSON command catalog.

    Args:
        access_status: Resolved authority status for one command schema.

    Returns:
        str: Password marker for request-password entries, otherwise empty text.
    """

    # Presentation guard: identify approval-required commands without exposing secrets.

    if access_status == "request_password":
        return " [password required]"

    return ""


def get_help_text(
    color: bool = False,
    domain: str | None = None,
    authority: str | None = None,
) -> str:
    """Render the complete or domain-scoped help document for one authority.

    Collects visible schemas before building sections, keeping denied commands
    absent, protected commands marked, and full/domain output in canonical order
    for terminal and JSON consumers.

    Args:
        color: Whether to enable ANSI color output.
        domain: Optional domain filter.
        authority: Declared authority string for filtering commands. Missing or
            blank authority fails closed and exposes no command schemas.

    Returns:
        str: Rendered help text.

    Raises:
        BrainStoreError: If ``domain`` does not match a visible command domain.
    """
    command_entries = _get_authorized_schema_entries(authority=authority)

    # Name projection: retain visible names for renderer highlighting and parity.

    command_names = [
        schema.name
        for schema, _access_status in command_entries
    ]
    domain_filter = domain.casefold().strip() if domain else None
    domain_commands: dict[str, list[str]] = {}
    parameter_docs: dict[str, str] = {}

    # Collection pass: group only authority-visible commands by their registered domain.

    for command, access_status in command_entries:
        command_domain = str(getattr(command, "domain", "general"))

        # Domain filter: exclude commands outside the requested topic before aggregation.

        if domain_filter and command_domain.casefold() != domain_filter:
            continue

        domain_commands.setdefault(command_domain, []).append(
            f"  {get_syntax(command)} - {command.help}"
            f"{_access_suffix(access_status)}"
        )
        collect_parameter_docs(command=command, parameter_docs=parameter_docs)

    # Topic validation: preserve fail-closed errors for unknown or hidden domains.

    if domain_filter and not domain_commands:
        raise BrainStoreError(
            f"Unknown help topic: {domain}. Run `help` to list commands."
        )

    parameter_docs["--password-stdin"] = _PASSWORD_STDIN_HELP

    # Global option policy: add color documentation only to the full-help view.

    if not domain_filter:
        parameter_docs["-c, --color"] = "Enable ANSI color output."

    # Layout selection: render the filtered domain body or complete help body.

    if domain_filter:
        raw_text = render_domain_help_text(
            domain_name=next(iter(domain_commands.keys())),
            command_lines=sorted(next(iter(domain_commands.values()))),
            parameter_docs=parameter_docs,
        )

    # Full-layout branch: retain all domains and the established global sections.

    else:
        raw_text = render_full_help_text(
            domain_commands=domain_commands, parameter_docs=parameter_docs
        )

    return render_help(raw_text, color, command_names)


def get_short_help_text(
    topic: str | None = None,
    color: bool = False,
    authority: str | None = None,
) -> str:
    """Render a compact authority-aware index of domains and command names.

    Applies the same visibility policy as full help, marks digest-backed password
    requests, and sorts both hierarchy levels for stable operator-facing output.

    Args:
        topic: Optional command or domain topic.
        color: Whether to enable ANSI color output.
        authority: Declared authority string for filtering commands. Missing or
            blank authority fails closed and exposes no command schemas.

    Returns:
        str: Rendered short help text.

    Raises:
        BrainStoreError: If ``topic`` does not match a visible command or domain.
    """
    command_entries = _get_authorized_schema_entries(authority=authority)

    # Name projection: retain visible names for renderer highlighting and parity.

    command_names = [
        schema.name
        for schema, _access_status in command_entries
    ]
    requested_topic = str(topic or "").strip().casefold()
    domain_commands: dict[str, list[str]] = {}

    # Collection pass: group visible command names under their normalized domains.

    for command, access_status in command_entries:
        domain = str(getattr(command, "domain", "general")).casefold()

        # Topic filter: keep only the requested command or its containing domain.

        if requested_topic and requested_topic not in (domain, command.name.casefold()):
            continue

        command_label = f"{command.name}{_access_suffix(access_status)}"
        domain_commands.setdefault(domain, []).append(command_label)

    # Topic validation: reject unknown or authority-hidden topics before rendering.

    if requested_topic and not domain_commands:
        raise BrainStoreError(
            f"Unknown help topic: {topic}. Run `help` to list commands."
        )

    lines: list[str] = ["Environment Management System", "", "Domains:"]

    # Domain ordering: sort normalized domains for stable compact-help output.

    for domain in sorted(domain_commands):
        lines.append(f"  {domain}:")

        # Command ordering: sort names while retaining the protected-access marker.

        for command_name in sorted(domain_commands[domain]):
            lines.append(f"    - {command_name}")

    return render_help("\n".join(lines), color, command_names)


def get_command_help_text(
    topic: str,
    color: bool = False,
    authority: str | None = None,
) -> str:
    """Render detailed help for one visible command or its visible domain.

    Resolves topics inside the authority-filtered catalog, adds only non-secret
    password-input guidance for protected commands, and preserves manual order.

    Args:
        topic: Command or domain topic.
        color: Whether to enable ANSI color output.
        authority: Declared authority string for filtering commands. Missing or
            blank authority fails closed and exposes no command schemas.

    Returns:
        str: Rendered command or domain help text.

    Raises:
        BrainStoreError: If ``topic`` is neither a visible command nor a visible domain.
    """
    command_entries = _get_authorized_schema_entries(authority=authority)

    # Name projection: retain visible names for renderer highlighting and parity.

    command_names = [
        schema.name
        for schema, _access_status in command_entries
    ]
    requested_topic = topic.strip()

    # Topic resolution: search only visible schemas so hidden commands cannot be described.

    command_entry = next(
        (
            (schema, access_status)
            for schema, access_status in command_entries
            if schema.name == requested_topic
        ),
        None,
    )

    # Domain fallback: preserve domain rendering and fail closed for unknown topics.

    if command_entry is None:
        return get_help_text(color=color, domain=requested_topic, authority=authority)

    command, access_status = command_entry
    parameter_lines = build_command_parameter_lines(command=command)

    # Approval guidance: expose only the supported input channel, never secret material.

    if access_status == "request_password":
        parameter_lines.append(f"  --password-stdin - {_PASSWORD_STDIN_HELP}")

    # Parameter fallback: keep focused help explicit when a schema declares no arguments.

    if parameter_lines:
        parameters = "\n".join(parameter_lines)

    # Empty-argument branch: emit the stable no-parameters notice.

    else:
        parameters = "  None - This command has no parameters."

    access_section = ""

    # Access disclosure: state the approval requirement without copying configuration secrets.

    if access_status == "request_password":
        access_section = "\n\nAccess:\n  Password required for execution."

    raw_text = f"""Environment Management System

Command:
  {get_syntax(command)} - {command.help}{_access_suffix(access_status)}

Domain:
  {command.domain} - Command group.

Parameters:
{parameters}{access_section}{render_manual_sections(command)}"""

    return render_help(raw_text, color, command_names)


def render_manual_sections(command: CommandSchema) -> str:
    """Render rich manual sections in the canonical order shared with argparse.

    Materializes runtime placeholders and omits empty optional sections so focused
    help and parser-generated help expose the same documented contract.

    Args:
        command: Command schema containing manual description sections.

    Returns:
        str: Rendered manual sections text.
    """
    sections = [("Description", command.description)]

    # Section selection: retain canonical order while omitting empty optional blocks.

    sections.extend(
        (title, values)
        for title, values in (
            ("Stdin", command.stdin),
            ("Examples", command.examples),
            ("Output", command.output),
            ("Exit codes", command.exit_codes),
            ("Safeguards", command.safeguards),
            ("Notes", command.notes),
        )
        if values
    )

    sections.extend(_render_schema_sections(command))
    rendered: list[str] = []

    # Section traversal: format entries in the canonical argparse-compatible order.

    for title, values in sections:

        # Value-shape branch: materialize scalars or preserve sequence order as bullets.

        if isinstance(values, str):
            body = _materialize(values)

        # Sequence branch: materialize each declared item without reordering it.

        else:
            body = "\n".join(f"  - {_materialize(item)}" for item in values)

        # Empty-content guard: do not emit headings with no rendered documentation.

        if body:
            rendered.append(f"\n\n{title}:\n{body}")

    return "".join(rendered)


def _materialize(value: str) -> str:
    """Resolve runtime placeholders in one command-manual value.

    The shared resolver keeps examples tied to the active workspace while avoiding
    environment-specific paths in stored command schemas.

    Args:
        value: Raw template string with placeholders.

    Returns:
        str: Materialized string with resolved runtime variables.
    """

    return render_profile_template_variables(value)


def _render_schema_sections(command: CommandSchema) -> list[tuple[str, str]]:
    """Render input and output payload schemas as ordered manual sections.

    Preserves the input-then-output grouping and declared field order, omitting
    empty groups so the detailed manual mirrors the public schema contract.

    Args:
        command: Command schema holding input and output payload schemas.

    Returns:
        list[tuple[str, str]]: Title and formatted payload schema text tuples.
    """
    sections: list[tuple[str, str]] = []
    schema_groups = (
        ("Input schemas", command.input_schemas),
        ("Output schemas", command.output_schemas),
    )

    # Schema traversal: keep input groups before output groups as the public contract requires.

    for title, schemas in schema_groups:

        # Empty-group guard: omit absent payload variants from the manual.

        if schemas:
            # Payload traversal: format each schema in its declared group order.

            rendered_schemas = "\n\n".join(
                _render_payload_schema(schema) for schema in schemas
            )

            sections.append((title, rendered_schemas))

    return sections


def _render_payload_schema(schema: PayloadSchema) -> str:
    """Render one payload schema with constraints, fields, and examples.

    Preserves descriptions and declaration order, materializes each example line,
    and keeps required/optional labels visible for structured command contracts.

    Args:
        schema: Payload schema instance to render.

    Returns:
        str: Formatted payload schema text with fields and examples.
    """
    lines = [f"  {schema.name} ({schema.media_type})"]

    # Description branch: include the schema-level explanation when it is defined.

    if schema.description:
        lines.append(f"    {schema.description}")

    # Field branch: expose the declared shape and requiredness of structured payloads.

    if schema.fields:
        lines.append("    Fields:")

        # Field traversal: preserve schema declaration order for reliable manuals.

        for field in schema.fields:
            requirement = "required" if field.required else "optional"
            detail = f" - {field.description}" if field.description else ""

            lines.append(f"      - {field.name} ({field.type}, {requirement}){detail}")

    # Example branch: include runnable materialized examples when supplied.

    if schema.example:
        lines.append("    Example:")

        # Example traversal: preserve each example line and its original order.

        for example in schema.example:
            example_lines = _materialize(example).splitlines() or [""]

            # Example line projection: preserve materialized line order in the display.

            lines.extend(f"      {line}" for line in example_lines)

    return "\n".join(lines)


def collect_parameter_docs(
    command: CommandSchema, parameter_docs: dict[str, str]
) -> None:
    """Collect option documentation for the aggregate full-help parameter section.

    Ignores positional arguments and uses shared flag formatting, mutating only the
    caller-owned mapping so repeated schema traversal remains deterministic.

    Args:
        command: Command schema to inspect.
        parameter_docs: Mutable dictionary collecting parameter documentation.

    Returns:
        None.
    """

    # Argument traversal: inspect each declaration before aggregating global options.

    for argument in command.arguments:

        # Positional exclusion: aggregate only flags that can be invoked as options.

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
    """Build focused parameter lines in the schema declaration order.

    Uses shared formatting for options and explicit placeholders for positionals,
    keeping help presentation aligned with parser argument semantics.

    Args:
        command: Command schema containing argument specifications.

    Returns:
        list[str]: Printable parameter documentation lines.
    """
    parameter_lines: list[str] = []

    # Argument traversal: preserve declaration order in focused help output.

    for argument in command.arguments:
        is_flag = any(flag.startswith("-") for flag in argument.flags)

        # Option branch: use the shared formatter so focused and aggregate help agree.

        if is_flag:
            flag_doc = format_flag_documentation(
                argument.flags,
                has_value=argument.action != "store_true",
                long_only=False,
                cmd_domain=command.domain,
            )

            parameter_lines.append(f"  {flag_doc} - {argument.help}")

        # Positional branch: show the parser's positional name as an explicit placeholder.

        else:
            name = argument.flags[0].upper().replace("-", "_")

            parameter_lines.append(f"  <{name}> - {argument.help}")

    return parameter_lines


def _render_parameter_docs(parameter_docs: dict[str, str]) -> str:
    """Render aggregate parameter documentation in stable lexical order.

    Sorting formatted keys makes full and domain help deterministic without altering
    the schemas or their declared descriptions.

    Args:
        parameter_docs: Parameter documentation keyed by formatted option text.

    Returns:
        str: Newline-separated parameter documentation lines.
    """

    # Ordering invariant: sort formatted keys for reproducible terminal help.

    return "\n".join(
        f"  {flag_doc} - {help_text}"
        for flag_doc, help_text in sorted(parameter_docs.items())
    )


def render_full_help_text(
    domain_commands: dict[str, list[str]], parameter_docs: dict[str, str]
) -> str:
    """Assemble the complete raw help body before terminal coloring.

    Groups nonempty commands by domain, appends sorted global parameters, and
    preserves the established notation and additional-note sections for help parity.

    Args:
        domain_commands: Command lines grouped by domain name.
        parameter_docs: Parameter documentation map keyed by flag string.

    Returns:
        str: Raw full help text string.
    """
    command_sections: list[str] = []

    # Domain traversal: build one ordered command section for each registered domain.

    for domain in sorted(domain_commands):
        lines = sorted(domain_commands[domain])

        # Empty-domain guard: omit headings that have no visible command lines.

        if not lines:
            continue

        command_sections.append(f"{domain.capitalize()}:")
        command_sections.extend(lines)
        command_sections.append("")

    parameters_section = _render_parameter_docs(parameter_docs)

    formatted_commands = "\n".join(command_sections).strip()

    return f"""Environment Management System

Commands list:
{formatted_commands}

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
  - JSON output: memory-structure, set-memory-entry, get-memory-entry,
    query, and check-workspace support --json for machine-readable output."""


def render_domain_help_text(
    domain_name: str,
    command_lines: list[str],
    parameter_docs: dict[str, str],
) -> str:
    """Assemble a raw help body for one already-selected command domain.

    Preserves caller-provided command lines and shared parameter formatting so the
    public domain filter controls selection without re-evaluating authority.

    Args:
        domain_name: Name of the command domain.
        command_lines: List of formatted command syntax lines for the domain.
        parameter_docs: Parameter documentation map keyed by flag string.

    Returns:
        str: Raw domain help text string.
    """
    parameters_section = _render_parameter_docs(parameter_docs)

    formatted_lines = "\n".join(command_lines)

    return f"""Environment Management System

Domain:
  {domain_name} - Command group.

Commands:
{formatted_lines}

Parameters:
{parameters_section}"""
