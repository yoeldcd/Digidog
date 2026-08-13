# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `dream` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="dream",
    domain="knowledge",
    help="Use configured LLM stages to propose knowledge deltas, then confirm selected applications.",
    description=(
        "Run configured LLM stages over selected sources to propose knowledge deltas and refresh the graph when requested."
    ),
    stdin=(
        "No stdin is read; source selection, confidence, pruning, and output mode are command-line flags.",
    ),
    examples=("py {LOCAL_BRAIN_SCRIPT} dream --scope local --limit 10 --json",),
    output=(
        "Text reports scanned sources, generated proposals, and graph updates. --json emits stage results and counts.",
    ),
    exit_codes=(
        "0: dreaming completed, including no new proposals.",
        "2: invalid options, unavailable source, or stage failure.",
    ),
    safeguards=(
        "Without --force, current consumer timestamps can skip unchanged sources. --prune rebuilds the graph before processing.",
    ),
    notes=(
        "Scope defaults to all, domain to all, and limit is unset. Proposed deltas are reviewed separately with knowledge-deltas.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["--domain"],
            default="all",
            help="Source domain: all, memory, diary, profiles, logs, or messages.",
        ),
        ArgumentSchema(
            flags=["--scope"],
            default="all",
            help="Knowledge DB scope: all, global, or local. Defaults to all.",
        ),
        ArgumentSchema(
            flags=["-l", "--limit"],
            type="int",
            default=None,
            help="Limit number of sources to inspect.",
        ),
        ArgumentSchema(
            flags=["--source-path"],
            action="append",
            help="Restrict the pass to one source path. Repeat for multiple sources.",
        ),
        ArgumentSchema(
            flags=["--force"],
            action="store_true",
            help="Process selected sources even when their consumer timestamps are current.",
        ),
        ArgumentSchema(
            flags=["--min-confidence"],
            type="float",
            default=None,
            help="Override minimum confidence threshold.",
        ),
        ArgumentSchema(
            flags=["--prune"],
            action="store_true",
            help="Recreate the entire knowledge graph before running dream.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output results as JSON."
        ),
    ],
)
