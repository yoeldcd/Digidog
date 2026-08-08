"""Write-free regression coverage for the complete help JSON catalog."""

from __future__ import annotations

import argparse
import json
from contextlib import redirect_stdout
from io import StringIO

from brain.presentation.actions.general.command_show_help import handle


def test_help_catalog_is_json_serializable_with_named_types() -> None:
    """Every registered command schema must render without Python type objects."""
    args = argparse.Namespace(topic=None, short=False, color=False)
    with redirect_stdout(StringIO()):
        assert handle(args) == 0
    encoded = json.dumps(args.json_payload, ensure_ascii=False)
    assert '"type": "int"' in encoded
    assert args.json_payload["count"] > 0


def test_topic_help_keeps_alias_and_domain_filtering() -> None:
    """JSON conversion must preserve the existing topic-selection contract."""
    args = argparse.Namespace(topic="serve-explorer", short=False, color=False)
    with redirect_stdout(StringIO()):
        assert handle(args) == 0
    assert args.json_payload["count"] == 1
    assert args.json_payload["commands"][0]["name"] == "serve-explorer"
    json.dumps(args.json_payload)
