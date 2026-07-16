# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Changelog type contract and CLI help regression tests."""

from brain.application.logs.entry_formatting import (
    VALID_LOG_TYPES,
    normalize_log_type,
    valid_log_types_text,
)
from brain.presentation.commands.general.command_complete_work import SCHEMA as COMPLETE_WORK_SCHEMA
from brain.presentation.commands.logs.command_append_log import SCHEMA as APPEND_LOG_SCHEMA
from brain.presentation.views.help.rendering import get_command_help_text


def test_maintenance_is_a_canonical_normalized_log_type() -> None:
    assert "maintenance" in VALID_LOG_TYPES
    assert normalize_log_type(" Maintenance ") == "maintenance"
    assert valid_log_types_text().endswith("documentation, maintenance")


def test_complete_work_and_append_log_helpers_list_every_log_type() -> None:
    expected = valid_log_types_text()
    complete_help = get_command_help_text(COMPLETE_WORK_SCHEMA.name, color=False)
    append_help = get_command_help_text(APPEND_LOG_SCHEMA.name, color=False)

    assert f"Accepted values: {expected}." in complete_help
    assert f"Accepted values: {expected}." in append_help


def test_invalid_log_type_error_uses_the_documented_contract() -> None:
    try:
        normalize_log_type("unknown")
    except ValueError as error:
        assert valid_log_types_text() in str(error)
    else:
        raise AssertionError("Unknown changelog type was unexpectedly accepted.")
