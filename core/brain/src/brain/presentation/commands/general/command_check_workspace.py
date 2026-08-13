# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `check-workspace` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="check-workspace",
    domain="general",
    help="Validate workspace memory structure and nesting compliance.",
    arguments=[
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Print report as JSON."
        ),
    ],
    description="Validate workspace memory layout and nesting rules.",
    stdin=("No stdin is consumed; the current workspace is inspected.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} check-workspace --json",),
    output=("Validation findings and an overall pass/fail report.",),
    exit_codes=("0 when checks pass; nonzero when violations are found.",),
    safeguards=("Read-only validation; no files are rewritten.",),
    notes=("Use --json for automation-friendly findings.",),
)
