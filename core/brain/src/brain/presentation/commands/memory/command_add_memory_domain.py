"""Command metadata for the `add-memory-domain` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="add-memory-domain",
    domain="memory",
    help="Create a memory domain or subdomain (e.g. domain or domain.subdomain). (e.g. add-memory-domain profile.friend)",
    description="Create the requested memory domain directory and report its path.",
    stdin=("No stdin is read; provide the domain as the positional argument.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} add-memory-domain project.product",),
    output=(
        "Text mode prints a creation message; --json prints {ok, domain, path} or {ok:false, error}.",
    ),
    exit_codes=("0: domain created.", "1: domain creation or validation failed."),
    safeguards=(
        "The action strips the domain name and catches service errors before returning a failure status; it does not delete existing data.",
    ),
    notes=("Nested names use dot notation, such as project.product.",),
    arguments=[
        ArgumentSchema(
            flags=["domain"],
            help="Name of the memory domain or dot-separated subdomain.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output result as JSON."
        ),
    ],
)
