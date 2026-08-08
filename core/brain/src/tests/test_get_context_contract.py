"""Regression tests for the compact get-context transport contract."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from brain.application.profiles.service import get_profiles_dir, profile_summaries
from brain.presentation.actions.general.command_get_context import (
    _diary_header_items,
    _memory_section,
    _parse_log_index_items,
    _policies_section,
)


def test_log_context_items_are_compact_domain_records() -> None:
    """Keep log hydration free from duplicated routing and timestamp fields."""
    items = _parse_log_index_items([
        "## wiki",
        "",
        "* generator : (documentation) last entry `read-log -d 02-07-2026 --time 03:36` "
        "| title: Bind wiki logs by explicit superdomain",
        "* viewer : (feature) last entry `read-log -d 03-07-2026 --time 04:37` | title: Add wiki viewer",
    ])

    assert items == [
        {
            "id": 1,
            "domain": "wiki.generator",
            "last_change": {
                "title": "Bind wiki logs by explicit superdomain",
                "type": "documentation",
                "retrieve_command": "read-log -d 02-07-2026 --time 03:36",
            },
        },
        {
            "id": 2,
            "domain": "wiki.viewer",
            "last_change": {
                "title": "Add wiki viewer",
                "type": "feature",
                "retrieve_command": "read-log -d 03-07-2026 --time 04:37",
            },
        },
    ]


def test_policy_context_section_uses_the_public_policies_contract() -> None:
    """Always-on imperative records are exposed as policies in hydrated context."""
    with patch(
        "brain.application.records.service.list_live_records",
        return_value=[SimpleNamespace(id="rec01", text="Use explicit types.")],
    ):
        section = _policies_section()

    assert section == {
        "kind": "policies",
        "title": "Workspace Local Policies",
        "status": "ok",
        "summary": "1 always-on local policy.",
        "policies": {"rec01": "Use explicit types."},
    }


def test_diary_context_items_only_expose_retrieval_fields() -> None:
    """Derive a focused read command without route metadata or filesystem writes."""
    items = _diary_header_items(
        Path("21-07-2026.md"),
        "## 21-07-2026 10:46:14 - A compact morning\n",
    )

    assert items == [{
        "title": "A compact morning",
        "retrieve_command": "read-diary -d 21-07-2026 --time 10:46",
    }]


def test_profile_context_items_include_root_usage_guidance() -> None:
    """Expose compact profile metadata sourced from each root usage file."""
    profiles = profile_summaries(get_profiles_dir())

    assert profiles
    assert all(set(profile) == {"id", "name", "retrieve_command", "use_when"} for profile in profiles)
    assert all(isinstance(profile["id"], int) for profile in profiles)
    assert all(str(profile["use_when"]).startswith("Use ") for profile in profiles)


def test_memory_context_section_exposes_only_operational_guidance() -> None:
    """Keep memory hydration concise while exposing canonical discovery and mutation routes."""
    section = _memory_section()

    assert section == {
        "kind": "memory",
        "use_when": "Use when durable context, preferences, relationships, notes, or reusable knowledge must be read or updated.",
        "get_structure_command": "memory-structure",
        "read_entry_template": "get-memory-entry <DOMAIN> [KEY]",
        "write_item_template": "set-memory-entry <DOMAIN> <KEY> <CONTENT>",
    }
