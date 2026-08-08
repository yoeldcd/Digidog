"""Execute the canonical ``show-records`` command and its parser alias."""

from __future__ import annotations

import argparse
import json

from brain.application.records.service import list_live_records
from brain.presentation.terminal import render_markdown, render_placeholders


def handle(args: argparse.Namespace) -> int:
    """Render every active always-on record in stable creation order.

    Args:
        args: Parsed command arguments. ``json`` selects an ID-indexed
            ``records`` dictionary; ``color`` controls terminal placeholders.

    Returns:
        Zero after rendering, including when the records store is empty.

    Notes:
        ``show-policies`` is a parser alias and reaches this same action. The
        output remains the canonical records contract for both spellings.
    """
    color_enabled = getattr(args, "color", False)
    records = list_live_records()
    if args.json:
        payload = {"ok": True, "records": {record.id: record.text for record in records}}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif not records:
        print(render_placeholders("__YELLOW__No active local records.__RESET__", color_enabled))
    else:
        content = "\n\n".join("# {}\n\n{}".format(record.id, record.text) for record in records)
        print(render_markdown(content, color_enabled))
    return 0
