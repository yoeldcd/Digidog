"""Command metadata for the Core code-quality evaluator adapter."""

from __future__ import annotations

from brain.presentation.commands.models import (
    ArgumentSchema,
    CommandSchema,
    PayloadSchema,
    SchemaField,
)

SCHEMA = CommandSchema(
    name="code-quality",
    aliases=("eval-quality","check-quality"),
    domain="utilities",
    help="Run the policy-driven six-language in-memory code-quality evaluator.",
    arguments=[
        ArgumentSchema(
            flags=["paths"],
            nargs="*",
            help="Workspace-relative files to evaluate.",
        ),
        ArgumentSchema(
            flags=["--mode"],
            default="check",
            help="Operation mode: check, evaluate, format, or schema.",
        ),
        ArgumentSchema(
            flags=["--language"],
            required=False,
            default="",
            help="Optional language override for every supplied file.",
        ),
        ArgumentSchema(
            flags=["--evaluator"],
            required=False,
            default="",
            help="Optional evaluator profile identifier.",
        ),
        ArgumentSchema(
            flags=["--schema"],
            default="request",
            help="Generated schema: request, result, format, error, config, or model.",
        ),
    ],
    description=(
        "Run the configured six-language evaluator for workspace-relative files. "
        "The facade synthesizes the typed request; it does not read request JSON from stdin."
    ),
    stdin=(
        "Does not read request JSON from standard input; provide workspace-relative paths as positional arguments.",
    ),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} code-quality src/app.py --mode check --json",
        "py {LOCAL_BRAIN_SCRIPT} code-quality src/app.ts --mode evaluate --json",
        "py {LOCAL_BRAIN_SCRIPT} code-quality src/app.js --mode format --json",
        "py {LOCAL_BRAIN_SCRIPT} code-quality --mode schema --schema request --json",
        "py {LOCAL_BRAIN_SCRIPT} code-quality --mode schema --schema format --json",
        "py {LOCAL_BRAIN_SCRIPT} code-quality --mode schema --schema error --json",
    ),
    output=(
        (
            "One JSON result: status plus failed gates/commands for check or evaluate, "
            "formatter candidates for format, or a generated schema."
        ),
    ),
    exit_codes=(
        "0: pass; deterministic and required semantic layers completed successfully.",
        "1: fail or disagree; one or more required gates or semantic criteria failed.",
        "2: blocked, error, invalid input, invalid configuration, or unavailable formatter/provider.",
    ),
    safeguards=(
        "Only explicitly supplied workspace-relative files are evaluated.",
        "Supported suffixes: .py, .js/.mjs/.cjs, .ts/.tsx, .json, .md, .ps1/.psm1.",
        "No temporary files, cache discovery, or source persistence is performed.",
    ),
    notes=(
        "Modes check, evaluate, format, and schema have distinct output behavior.",
        "check disables semantic transmission; evaluate uses only the configured provider boundary.",
        "All deterministic gates run and all configured evidence occurrences are bounded by policy.",
        (
            "Shared gates: REQ-01-DIGEST, REQ-01-CONTENT, REQ-01-PATH, REQ-01-LINE-LENGTH, "
            "REQ-01-REQUIRED, REQ-01-FORBIDDEN."
        ),
        (
            "Language gates: PY-SYNTAX, PY-ANNOTATIONS, PY-DOCSTRINGS, PY-IMPORTS, PY-NO-ANY, "
            "PY-VERTICAL-LAYOUT, PY-COMPACTNESS."
        ),
        (
            "Language gates: JS-SYNTAX, JS-DOCUMENTATION, JS-VERTICAL-LAYOUT, JS-COMPACTNESS; "
            "TS-SYNTAX, TS-DOCUMENTATION, TS-VERTICAL-LAYOUT, TS-COMPACTNESS."
        ),
        (
            "Language gates: JSON-SYNTAX, JSON-STRUCTURE; MD-SYNTAX, MD-STRUCTURE; "
            "PS-SYNTAX, PS-DOCUMENTATION, PS-VERTICAL-LAYOUT, PS-COMPACTNESS."
        ),
    ),
    input_schemas=(
        PayloadSchema(
            name="request",
            media_type="application/json",
            description=(
                "Canonical evaluator request synthesized from direct path arguments; "
                "this command does not read stdin."
            ),
            fields=(
                SchemaField(
                    "files",
                    "array<file>",
                    True,
                    "Non-empty source files with safe relative path, supported language, and content. "
                    "CLI callers provide paths, not stdin JSON.",
                ),
                SchemaField(
                    "requirements",
                    "array<requirement>",
                    False,
                    "Requirement objects: id, description, category, and required_gate_ids[].",
                ),
                SchemaField(
                    "commands",
                    "array<command>",
                    False,
                    "Command objects: id, argv[] (non-empty), expected_exit_code, timeout (0<seconds<=86400), retry.",
                ),
                SchemaField(
                    "artifact_checks",
                    "array<artifact-check>",
                    False,
                    "Gate objects: id, description, optional command.",
                ),
                SchemaField(
                    "formatter_checks",
                    "array<formatter>",
                    False,
                    "Formatter objects: id, language, command.",
                ),
                SchemaField(
                    "evaluator_id",
                    "string|null",
                    False,
                    "Optional stable evaluator profile ID.",
                ),
                SchemaField(
                    "baseline_paths",
                    "array<string>",
                    False,
                    "Safe relative baseline paths; length must match baseline_digests.",
                ),
                SchemaField(
                    "baseline_digests",
                    "array<string>",
                    False,
                    "Baseline digest strings paired one-to-one with baseline_paths.",
                ),
            ),
            example=(
                '{"files":[{"path":"src/example.py","language":"python","content":"..."}]}',
            ),
        ),
        PayloadSchema(
            name="config",
            media_type="application/json",
            description="Evaluator configuration selected by the resolved profile.",
            fields=(
                SchemaField(
                    "default_evaluator_id",
                    "string",
                    True,
                    "Stable profile ID selected when evaluator_id is omitted.",
                ),
                SchemaField(
                    "evaluators",
                    "array<evaluator>",
                    True,
                    "Non-empty unique evaluator profiles with language policies, formatters, "
                    "semantic requirements, thresholds, retries, and timeouts.",
                ),
            ),
        ),
    ),
    output_schemas=(
        PayloadSchema(
            name="result",
            media_type="application/json",
            description="Normal check/evaluate envelope emitted as one JSON object.",
            fields=(
                SchemaField("mode", "string", True, "check or evaluate."),
                SchemaField(
                    "status", "string", True, "pass, fail, disagree, blocked, or error."
                ),
                SchemaField(
                    "files",
                    "array<file-result>",
                    True,
                    "Per-file path, language, status, and non-passing gates/findings[].",
                ),
                SchemaField(
                    "commands",
                    "array<command-result>",
                    False,
                    "Non-passing command results with command_id, status, exit_code, and message.",
                ),
                SchemaField(
                    "semantic",
                    "semantic-result|null",
                    False,
                    "Semantic result with status, evaluator_id, blocks_aggregate, and non-passing criteria[].",
                ),
                SchemaField("summary", "string", True, "Bounded aggregate status summary."),
            ),
        ),
        PayloadSchema(
            name="request-schema",
            media_type="application/json",
            description="Generated request DTO schema projection.",
            fields=(
                SchemaField("title", "string", True),
                SchemaField("type", "string", True),
                SchemaField("properties", "object", True),
                SchemaField("required", "array<string>", False),
            ),
        ),
        PayloadSchema(
            name="result-schema",
            media_type="application/json",
            description="Generated result DTO schema projection.",
            fields=(
                SchemaField("title", "string", True),
                SchemaField("type", "string", True),
                SchemaField("properties", "object", True),
            ),
        ),
        PayloadSchema(
            name="config-schema",
            media_type="application/json",
            description="Generated CodeEvaluatorConfig schema projection.",
            fields=(
                SchemaField("title", "string", True),
                SchemaField("type", "string", True),
                SchemaField("properties", "object", True),
            ),
        ),
        PayloadSchema(
            name="model-schema",
            media_type="application/json",
            description=(
                "Generated ModelSpec schema projection: model, base_url, api_key, "
                "temperature, max_tokens, and enabled."
            ),
            fields=(
                SchemaField("title", "string", True),
                SchemaField("type", "string", True),
                SchemaField("properties", "object", True),
                SchemaField("required", "array<string>", False),
            ),
        ),
        PayloadSchema(
            name="format-result",
            media_type="application/json",
            description="Formatter envelope emitted for format mode.",
            fields=(
                SchemaField("mode", "string", True, "Always format."),
                SchemaField("status", "string", True, "pass, fail, blocked, or error."),
                SchemaField("summary", "string", True, "Bounded formatter summary."),
                SchemaField(
                    "files",
                    "array<object>",
                    True,
                    "Per-file path, language, status, message, and optional content candidate.",
                ),
            ),
        ),
        PayloadSchema(
            name="error-result",
            media_type="application/json",
            description="Source-redacted failure envelope emitted before a normal result exists.",
            fields=(
                SchemaField("mode", "string", True, "Requested operation."),
                SchemaField("status", "string", True, "blocked or error."),
                SchemaField("summary", "string", True, "Bounded failure explanation."),
            ),
        ),
        PayloadSchema(
            name="format-schema",
            media_type="application/json",
            description="Generated FormatReport DTO schema projection.",
            fields=(
                SchemaField("title", "string", True),
                SchemaField("type", "string", True),
                SchemaField("properties", "object", True),
            ),
        ),
        PayloadSchema(
            name="error-schema",
            media_type="application/json",
            description="Generated ErrorReport DTO schema projection.",
            fields=(
                SchemaField("title", "string", True),
                SchemaField("type", "string", True),
                SchemaField("properties", "object", True),
            ),
        ),
    ),
)
