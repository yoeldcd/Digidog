# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Contracts for compact and legacy ``complete-work`` metadata resolution."""

from argparse import Namespace

import pytest

from brain.application.backlog.models import BacklogTask
from brain.presentation.actions.general.command_complete_work import _resolve_completion_metadata
from brain.presentation.commands.general import command_complete_work
from brain.presentation.parser.services.argument_parser_service import build_argument_parser


def _task() -> BacklogTask:
    """Return a stable task fixture without touching the workspace database."""
    return BacklogTask(
        task_id="t42",
        domain="core.brain.cli",
        title="Canonical task title",
        description="Canonical task reason",
        priority="HIGH",
        status="WORKING",
    )


def test_parser_accepts_compact_and_legacy_completion_forms() -> None:
    """Both supported positional contracts must reach the action unchanged."""
    parser = build_argument_parser([command_complete_work])

    compact = parser.parse_args(["complete-work", "t42", "fix", "Summary", "--stage", "a.py"])
    legacy = parser.parse_args(
        [
            "complete-work",
            "t42",
            "old.domain",
            "Old title",
            "feature",
            "Old reason",
            "Old description",
            "Old impact",
            "--stage",
            "a.py",
        ],
    )

    assert compact.details == ["fix", "Summary"]
    assert legacy.details == [
        "old.domain",
        "Old title",
        "feature",
        "Old reason",
        "Old description",
        "Old impact",
    ]


def test_compact_metadata_inherits_task_context() -> None:
    """The compact form must derive redundant semantic fields from the task."""
    metadata = _resolve_completion_metadata(
        task=_task(),
        args=Namespace(details=["fix", "Implemented the contract"], domain=None, title=None, why=None, impact=None),
    )

    assert metadata.domain == "core.brain.cli"
    assert metadata.title == "Canonical task title"
    assert metadata.why == "Canonical task reason"
    assert metadata.description == "Implemented the contract"
    assert metadata.impact == "Implemented the contract"


def test_explicit_options_override_task_defaults() -> None:
    """Named overrides must remain available for exceptional completion logs."""
    metadata = _resolve_completion_metadata(
        task=_task(),
        args=Namespace(
            details=["improvement", "Implemented"],
            domain="override.domain",
            title="Override title",
            why="Override reason",
            impact="Override impact",
        ),
    )

    assert metadata.domain == "override.domain"
    assert metadata.title == "Override title"
    assert metadata.why == "Override reason"
    assert metadata.impact == "Override impact"


def test_invalid_positional_arity_is_rejected() -> None:
    """Ambiguous invocations must fail instead of producing malformed logs."""
    with pytest.raises(ValueError, match="expects CHANGE_TYPE SUMMARY"):
        _resolve_completion_metadata(
            task=_task(),
            args=Namespace(details=["fix"], domain=None, title=None, why=None, impact=None),
        )
