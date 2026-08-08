"""Execute the canonical ``add-record`` command and its parser alias."""

from __future__ import annotations

import argparse
import json

from brain.application.records.service import add_live_record
from brain.presentation.terminal import render_placeholders


def handle(args: argparse.Namespace) -> int:
    """Persist one always-on record and render its public CLI result.

    Args:
        args: Parsed command arguments. ``text`` supplies record content,
            ``json`` selects the machine-readable envelope, and ``color``
            controls terminal placeholders.

    Returns:
        Zero after the record is persisted and rendered; one when validation or
        persistence fails and the error has been rendered.

    Notes:
        ``registre-policie`` is normalized by the parser to this canonical
        action. The action therefore preserves one records execution layer.
    """
    color_enabled = getattr(args, "color", False)
    try:
        record = add_live_record(args.text)
        payload = {"ok": True, "id": record.id, "result": "Record added."}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            message = "__GREEN__Added local record__RESET__ `{}`.".format(record.id)
            print(render_placeholders(message, color_enabled))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(render_placeholders("__RED__Error: {}__RESET__".format(exc), color_enabled))
        return 1
