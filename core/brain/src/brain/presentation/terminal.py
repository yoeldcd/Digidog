# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Presentation and terminal formatting utilities for colorized outputs."""

from __future__ import annotations

import re

ANSI_BOLD = "\033[1m"
ANSI_BLUE = "\033[34m"
ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_YELLOW = "\033[33m"
ANSI_MAGENTA = "\033[35m"
ANSI_DIM = "\033[90m"
ANSI_RESET = "\033[0m"


def get_color_codes(enabled: bool = False) -> tuple[str, str, str, str, str, str, str, str, str]:
    """Return ANSI color escapes if enabled is True, else empty strings."""
    if enabled:
        return (
            ANSI_BOLD,
            ANSI_BLUE,
            ANSI_CYAN,
            ANSI_GREEN,
            ANSI_RED,
            ANSI_YELLOW,
            ANSI_MAGENTA,
            ANSI_DIM,
            ANSI_RESET,
        )
    return ("", "", "", "", "", "", "", "", "")


def render_placeholders(text: str, color_enabled: bool = False) -> str:
    """Replace basic color placeholders (e.g. __GREEN__) with ANSI codes or strip them."""
    bold, blue, cyan, green, red, yellow, magenta, dim, reset = get_color_codes(color_enabled)
    placeholders = {
        "__BOLD__": bold,
        "__BLUE__": blue,
        "__CYAN__": cyan,
        "__GREEN__": green,
        "__RED__": red,
        "__YELLOW__": yellow,
        "__MAGENTA__": magenta,
        "__DIM__": dim,
        "__RESET__": reset,
    }
    for ph, esc in placeholders.items():
        text = text.replace(ph, esc)
    return text


def render_markdown(text: str, color_enabled: bool = False) -> str:
    """Highlight markdown syntax elements using ANSI colors and suppress meta tags."""
    if not color_enabled:
        return text

    bold, blue, cyan, green, red, yellow, magenta, dim, reset = get_color_codes(color_enabled)
    lines = []
    for line in text.splitlines():
        # Highlight Headers: keep '#+' and make yellow/bold
        line = re.sub(r'^(\s*)(#+)\s*(.*)$', rf'\1{bold}{yellow}\2 \3{reset}', line)

        # Highlight List Bullets: strip '-' or '*' and replace with colored bullet dot '•'
        line = re.sub(r'^(\s*)([-*+])\s+(.*)$', rf'\1{green}•{reset} \3', line)

        # Highlight Numbered lists: keep number but color it green
        line = re.sub(r'^(\s*)(\d+\.)\s+(.*)$', rf'\1{green}\2{reset} \3', line)

        # Highlight Bold text: strip '**' and make yellow/bold
        line = re.sub(r'\*\*([^*]+)\*\*', rf'{bold}{yellow}\1{reset}', line)

        # Highlight Inline Code: keep backticks and make magenta
        line = re.sub(r'`([^`]+)`', rf'{magenta}`\1`{reset}', line)

        # Highlight Links: strip brackets and URL, keep text cyan
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', rf'{cyan}\1{reset}', line)

        lines.append(line)
    return "\n".join(lines)


def render_help(text: str, color_enabled: bool = False, subcommands: list[str] | None = None) -> str:
    """Highlight the specific structure of the Memory CLI help command."""
    if not color_enabled:
        return text

    lines = []
    if subcommands is None:
        subcommands = []

    for line in text.splitlines():
        stripped = line.strip()

        # 1. Section Header: ends with ':'
        if stripped.endswith(":") and not stripped.startswith("-"):
            lines.append(f"__BOLD____YELLOW__{line}__RESET__")
            continue

        # 2. Main Title: starts with 'Memory CLI'
        if "Memory CLI" in line:
            lines.append(f"__BOLD____CYAN__{line}__RESET__")
            continue

        # 3. Command & Parameter Lines starting with two spaces
        if line.startswith("  ") and not line.startswith("   ") and " - " in line:
            left_part, right_part = line.split(" - ", 1)
            left_part = left_part.strip()

            hl_left = left_part
            for sub in subcommands:
                hl_left = re.sub(rf'\b{sub}\b', f"__BOLD____GREEN__{sub}__RESET__", hl_left)
            hl_left = re.sub(r'(<[^>]+>)', f"__CYAN__\\1__RESET__", hl_left)
            hl_left = re.sub(r'(\[|\])', f"__BRACKET_DIM__\\1__RESET__", hl_left)
            hl_left = re.sub(r'(--\w+)', f"__BOLD____MAGENTA__\\1__RESET__", hl_left)
            hl_left = re.sub(r'("[^"]*")', f"__YELLOW__\\1__RESET__", hl_left)
            hl_left = re.sub(r'\b(\w+\.\w+(?:\.\w+)?)\b', f"__CYAN__\\1__RESET__", hl_left)

            lines.append(f"  {hl_left} - __DIM__{right_part}__RESET__")
            continue

        # 4. Standard shortcuts or code snippets
        if stripped.startswith(tuple(subcommands)) or any(stripped.startswith(f"python memory.py {sub}") for sub in subcommands):
            line_hl = line
            for sub in subcommands:
                line_hl = re.sub(rf'\b{sub}\b', f"__BOLD____GREEN__{sub}__RESET__", line_hl)
            line_hl = re.sub(r'(<[^>]+>)', f"__CYAN__\\1__RESET__", line_hl)
            line_hl = re.sub(r'(\[|\])', f"__BRACKET_DIM__\\1__RESET__", line_hl)
            line_hl = re.sub(r'(--\w+)', f"__BOLD____MAGENTA__\\1__RESET__", line_hl)
            line_hl = re.sub(r'("[^"]*")', f"__YELLOW__\\1__RESET__", line_hl)
            line_hl = re.sub(r'\b(\w+\.\w+(?:\.\w+)?)\b', f"__CYAN__\\1__RESET__", line_hl)

            lines.append(line_hl)
            continue

        lines.append(line)

    result_text = "\n".join(lines)
    # Resolve the placeholders to escape sequences
    bold, blue, cyan, green, red, yellow, magenta, dim, reset = get_color_codes(True)
    placeholders = {
        "__BOLD__": bold,
        "__BLUE__": blue,
        "__CYAN__": cyan,
        "__GREEN__": green,
        "__RED__": red,
        "__YELLOW__": yellow,
        "__MAGENTA__": magenta,
        "__DIM__": dim,
        "__RESET__": reset,
        "__BRACKET_DIM__": dim, # Separate to avoid matching [ and ] in ANSI escapes
    }
    for ph, esc in placeholders.items():
        result_text = result_text.replace(ph, esc)
    return result_text


def log_step(args, msg: str, task: str | None = None) -> None:
    """Print a high-level step-progress message only with --verbose-log.

    Usage inside command handlers:
        log_step(args, "[1/3] Parsing inputs...")
        log_step(args, "[1/7] Migrating stores...", task="initialization")
    """
    if getattr(args, "verbose_log", False):
        color_enabled = getattr(args, "color", False)
        task_name = (task or getattr(args, "verbose_log_task", "") or "").strip()
        step_text = f"{task_name} steep {msg}" if task_name and msg.lstrip().startswith("[") else msg
        print(render_placeholders(f"__DIM__{step_text}__RESET__", color_enabled), flush=True)


def log_verbose(args, msg: str) -> None:
    """Print a verbose detail message. Only visible with --verbose-log.

    Usage inside command handlers:
        log_verbose(args, "  Reading file: /path/to/file.md")
    """
    if getattr(args, "verbose_log", False):
        color_enabled = getattr(args, "color", False)
        print(render_placeholders(f"__DIM__{msg}__RESET__", color_enabled), flush=True)
