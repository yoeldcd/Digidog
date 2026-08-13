"""Command metadata for the `set-memory-entry` CLI command."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="set-memory-entry",
    domain="memory",
    help="Write content to a key inside a memory domain. (e.g. set-memory-entry profile.friend value 'presence info')",
    description="Write Markdown content to a memory entry, creating or replacing its file.",
    stdin=(
        "If content is omitted or set to -, the command reads the Markdown body from stdin.",
    ),
    examples=(
        'py {LOCAL_BRAIN_SCRIPT} set-memory-entry project.product.note "Updated value"',
    ),
    output=(
        "Text mode confirms the saved key; --json prints {ok, domain, key, path} or an error object.",
    ),
    exit_codes=("0: entry written.", "1: key is absent or writing fails."),
    safeguards=(
        "A key is required either as a second argument or dot notation; --value overrides positional content.",
    ),
    notes=(
        "A literal '-' value deliberately selects stdin, which supports piped Markdown.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["domain"],
            help="The memory domain or dot-separated subdomain (e.g. domain or domain.subdomain).",
        ),
        ArgumentSchema(
            flags=["key"],
            default=None,
            nargs="?",
            help="The name of the key to create/update (optional if domain.key notation is used).",
        ),
        ArgumentSchema(
            flags=["val"],
            default=None,
            nargs="?",
            help="The Markdown content to write. If omitted, reads from stdin.",
        ),
        ArgumentSchema(
            flags=["-v", "--value"],
            required=False,
            help="Alternative option to provide Markdown content.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output result as JSON."
        ),
    ],
)
