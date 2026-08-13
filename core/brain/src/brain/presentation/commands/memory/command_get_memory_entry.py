"""Command metadata for the `get-memory-entry` CLI command."""

from brain.presentation.commands.models import (
    ArgumentSchema,
    CommandSchema,
    PayloadSchema,
    SchemaField,
)

SCHEMA = CommandSchema(
    name="get-memory-entry",
    domain="memory",
    help="Read Markdown content from a memory domain key. (e.g. get-memory-entry profile.friend value)",
    description="Read one Markdown entry or list/render the contents of a memory domain.",
    stdin=("No stdin is read; domain, key, and rendering flags come from arguments.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} get-memory-entry project.product.note --json",),
    output=(
        (
            "Normal mode renders Markdown or a navigable tree. For an entry, --json "
            "prints <RAW DOCUMENT> followed by raw Markdown; --json-envelope prints a JSON object."
        ),
    ),
    exit_codes=(
        "0: content or domain listing rendered.",
        "1: domain, key, or read operation failed.",
    ),
    safeguards=(
        "Reads are read-only; missing domains return an error payload in JSON mode and a terminal error otherwise.",
    ),
    notes=(
        "Use --full-text for every Markdown file in a domain; --limit truncates lines or tree items before raw/envelope rendering.",
    ),
    input_schemas=(),
    output_schemas=(
        PayloadSchema(
            name="entry-raw",
            media_type="text/markdown",
            description=(
                "Terminal entry output in --json mode: a literal <RAW DOCUMENT> preamble "
                "followed by localized raw Markdown; not a JSON document."
            ),
            fields=(
                SchemaField(
                    "preamble", "string", True, "Literal <RAW DOCUMENT> marker."
                ),
                SchemaField(
                    "markdown", "string", True, "Raw localized Markdown content."
                ),
            ),
            example=("<RAW DOCUMENT>\n# Entry\n...",),
        ),
        PayloadSchema(
            name="entry-envelope",
            media_type="application/json",
            description="Server-compatible --json-envelope entry result.",
            fields=(
                SchemaField("ok", "boolean", True),
                SchemaField("domain", "string", True),
                SchemaField("key", "string", True),
                SchemaField("content", "string", True, "Localized Markdown."),
            ),
        ),
        PayloadSchema(
            name="error",
            media_type="application/json",
            description="JSON error envelope returned for missing or unreadable domains/keys.",
            fields=(
                SchemaField("ok", "boolean", True, "Always false."),
                SchemaField("error", "string", True, "Human-readable failure message."),
            ),
        ),
        PayloadSchema(
            name="directory",
            media_type="application/json",
            description="Directory JSON result: index keys or full-text entries.",
            fields=(
                SchemaField("ok", "boolean", True),
                SchemaField("domain", "string", True),
                SchemaField("keys", "array<string>", False),
                SchemaField("entries", "object", False),
            ),
        ),
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
            help="The name of the key to read (optional if domain.key notation is used).",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help=(
                "Output directory indexes as JSON; terminal entries remain raw Markdown "
                "after <RAW DOCUMENT>."
            ),
        ),
        ArgumentSchema(
            flags=["--json-envelope"],
            action="store_true",
            help="Keep terminal entries in a JSON envelope for internal API consumers.",
        ),
        ArgumentSchema(
            flags=["-ft", "--full-text"],
            action="store_true",
            help="Print the entire content of all files in the domain instead of a navigable tree.",
        ),
        ArgumentSchema(
            flags=["-uo", "--uptime-order"],
            action="store_true",
            help="Sort the tree by modification date (newest first).",
        ),
        ArgumentSchema(
            flags=["-l", "--limit"],
            type="int",
            default=None,
            help="Limit the number of tree items per level or lines printed.",
        ),
    ],
)
