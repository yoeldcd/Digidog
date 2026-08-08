# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Canonical compact and ANSI-colored JSON rendering for CLI output."""

from __future__ import annotations

# Standard Libraries Imports
import json
import re
from typing import Any

# Application Modules Imports
from brain.presentation.terminal import (
    ANSI_BOLD,
    ANSI_CYAN,
    ANSI_DIM,
    ANSI_GREEN,
    ANSI_MAGENTA,
    ANSI_RESET,
    ANSI_YELLOW,
)


_JSON_TOKEN_PATTERN = re.compile(
    r'(?P<key>"(?:\\.|[^"\\])*")(?=\s*:)|'
    r'(?P<string>"(?:\\.|[^"\\])*")|'
    r'(?P<number>-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)|'
    r'(?P<boolean>\b(?:true|false)\b)|'
    r'(?P<null>\bnull\b)',
)


def render_json(payload: Any, color_enabled: bool = False) -> str:
    """
    Serialize one JSON payload according to the CLI presentation mode.

    Args:
        payload (Any): JSON-compatible value emitted by a command.
        color_enabled (bool): Whether to indent and apply semantic ANSI colors.

    Returns:
        str: Compact machine JSON, or indented syntax-colored JSON.
    """
    if not color_enabled:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    return _JSON_TOKEN_PATTERN.sub(_color_json_token, rendered)


def _color_json_token(match: re.Match[str]) -> str:
    """
    Apply the canonical ANSI color assigned to one serialized JSON token.

    Args:
        match (re.Match[str]): Named token match produced by `_JSON_TOKEN_PATTERN`.

    Returns:
        str: Token wrapped in its semantic ANSI color.
    """
    token = match.group(0)
    if match.lastgroup == "key":
        return f"{ANSI_BOLD}{ANSI_CYAN}{token}{ANSI_RESET}"
    if match.lastgroup == "string":
        return f"{ANSI_GREEN}{token}{ANSI_RESET}"
    if match.lastgroup == "number":
        return f"{ANSI_YELLOW}{token}{ANSI_RESET}"
    if match.lastgroup == "boolean":
        return f"{ANSI_MAGENTA}{token}{ANSI_RESET}"
    return f"{ANSI_DIM}{token}{ANSI_RESET}"
