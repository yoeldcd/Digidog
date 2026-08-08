"""Execute the canonical ``delete-record`` command and its parser alias."""

from __future__ import annotations

import argparse
import json

from brain.application.records.service import delete_live_record
from brain.presentation.terminal import render_placeholders


def handle(args: argparse.Namespace) -> int:
    """Delete one explicit always-on record and render the result.

    Args:
        args: Parsed command arguments. The ID may arrive through positional
            ``record_id`` or option ``id``; ``json`` selects the output envelope.

    Returns:
        Zero after deletion; one when the ID is absent, invalid, unknown, or the
        persistence operation fails.

    Notes:
        ``deprecate-policie`` is normalized to this action. Deprecation does not
        introduce a second policy store or action layer.
    """
    color_enabled = getattr(args, "color", False)
    record_id = getattr(args, "id", None) or getattr(args, "record_id", None)
    try:
        if not record_id:
            raise ValueError("delete-record requires a rec## ID or --id rec##.")
        record = delete_live_record(record_id)
        payload = {"ok": True, "id": record.id, "result": "Record deleted."}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            message = "__GREEN__Deleted local record__RESET__ `{}`.".format(record.id)
            print(render_placeholders(message, color_enabled))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(render_placeholders("__RED__Error: {}__RESET__".format(exc), color_enabled))
        return 1
