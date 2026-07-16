# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Syntax formatting helpers for CLI help views."""

from __future__ import annotations

# Application Modules Imports
from brain.presentation.commands.models import ArgumentSchema, CommandSchema


def format_flags(flags: list[str], long_only: bool = False) -> list[str]:
    """
    Return option flags preferring short form before long form.

    Args:
        flags (list[str]): Raw parser flags.
        long_only (bool): Whether to prefer long flags only.

    Returns:
        list[str]: Ordered flags.
    """
    short_flags = [flag for flag in flags if flag.startswith("-") and not flag.startswith("--")]
    long_flags = [flag for flag in flags if flag.startswith("--")]
    if long_only:
        return long_flags or short_flags
    return short_flags + long_flags


def format_flag_documentation(
    flags: list[str],
    has_value: bool = True,
    long_only: bool = False,
    cmd_domain: str = "",
) -> str:
    """
    Build a human-friendly flag representation.

    Args:
        flags (list[str]): Raw parser flags.
        has_value (bool): Whether the flag expects a value.
        long_only (bool): Whether to prefer long flags only.
        cmd_domain (str): Command domain for domain-specific value labels.

    Returns:
        str: Printable flag documentation.
    """
    option_flags = [flag for flag in flags if flag.startswith("-")]
    if not option_flags:
        return ""

    displayed_flags_list = format_flags(option_flags, long_only=long_only)
    displayed_flags = ", ".join(displayed_flags_list)
    raw_label = displayed_flags_list[-1].lstrip("-").upper().replace("-", "_")
    value_label = domain_value_label(raw_label=raw_label, cmd_domain=cmd_domain)
    if has_value:
        return f"{displayed_flags} <{value_label}>"
    return displayed_flags


def get_fallback_name(arg_flags: list[str], cmd_args: list[ArgumentSchema]) -> str | None:
    """
    Find the positional fallback argument name if it exists.

    Args:
        arg_flags (list[str]): Flags declared by one command argument.
        cmd_args (list[ArgumentSchema]): Complete command argument set.

    Returns:
        str | None: Fallback display name.
    """
    flag_names = [flag.lstrip("-").replace("-", "_") for flag in arg_flags]
    for other in cmd_args:
        if other.flags[0].startswith("-"):
            continue
        pos_name = other.flags[0]
        if pos_name == "body" and any(flag_name in ("text", "desc", "append", "replace") for flag_name in flag_names):
            return "BODY"
        if pos_name == "domain" and any(flag_name in ("domain", "log_domain") for flag_name in flag_names):
            return "DOMAIN"
        if pos_name == "timestamp" and any(flag_name in ("datetime", "timestamp") for flag_name in flag_names):
            return "TIMESTAMP"
        if any(pos_name == f"{flag_name}_pos" or pos_name == f"compact_{flag_name}" for flag_name in flag_names):
            return pos_name.upper()
    return None


def get_syntax(cmd: CommandSchema) -> str:
    """
    Generate syntax representation for a command dynamically from its schema.

    Args:
        cmd (CommandSchema): Command schema.

    Returns:
        str: Printable command syntax.
    """
    parts = [cmd.name]
    used_fallbacks = set()

    for arg in cmd.arguments:
        if not arg.flags[0].startswith("-"):
            continue
        fallback_name = get_fallback_name(arg.flags, cmd.arguments)
        if not fallback_name:
            continue
        for other in cmd.arguments:
            if not other.flags[0].startswith("-") and other.flags[0].upper() == fallback_name:
                used_fallbacks.add(other.flags[0])

    for arg in cmd.arguments:
        is_flag = any(flag.startswith("-") for flag in arg.flags)
        if is_flag:
            parts.append(format_flag_syntax(command=cmd, argument=arg))
            continue
        positional_text = format_positional_syntax(command=cmd, argument=arg, used_fallbacks=used_fallbacks)
        if positional_text:
            parts.append(positional_text)
    return " ".join(parts)


def format_flag_syntax(command: CommandSchema, argument: ArgumentSchema) -> str:
    """
    Return one option syntax fragment.

    Args:
        command (CommandSchema): Owning command schema.
        argument (ArgumentSchema): Option argument schema.

    Returns:
        str: Printable option syntax fragment.
    """
    has_value = argument.action != "store_true"
    long_flags = [flag for flag in argument.flags if flag.startswith("--")]
    principal_flag = long_flags[-1] if long_flags else argument.flags[0]
    flag_names = [flag.lstrip("-").replace("-", "_") for flag in argument.flags]
    fallback_name = get_fallback_name(argument.flags, command.arguments)
    is_required = is_conceptually_required(command=command, argument=argument, flag_names=flag_names)

    if fallback_name:
        value_label = fallback_name.replace("COMPACT_", "").replace("_POS", "").replace("-", "_")
        value_label = domain_value_label(raw_label=value_label, cmd_domain=command.domain)
        if is_required:
            return f"[{principal_flag}] <{value_label}>"
        return f"[[{principal_flag}] <{value_label}>]"

    if has_value:
        value_label = domain_value_label(
            raw_label=principal_flag.lstrip("-").upper().replace("-", "_"),
            cmd_domain=command.domain,
        )
        flag_doc = f"{principal_flag} <{value_label}>"
    else:
        flag_doc = principal_flag

    if argument.action == "store_true":
        return f"[{flag_doc}]"
    if argument.required or is_required:
        return flag_doc
    return f"[{flag_doc}]"


def format_positional_syntax(command: CommandSchema, argument: ArgumentSchema, used_fallbacks: set[str]) -> str:
    """
    Return one positional syntax fragment.

    Args:
        command (CommandSchema): Owning command schema.
        argument (ArgumentSchema): Positional argument schema.
        used_fallbacks (set[str]): Positional names already represented by options.

    Returns:
        str: Printable positional syntax fragment.
    """
    primary_flag = argument.flags[0]
    if primary_flag in used_fallbacks:
        return ""
    primary_flag_upper = domain_value_label(
        raw_label=primary_flag.upper().replace("-", "_"),
        cmd_domain=command.domain,
    )
    if argument.nargs == "?":
        return f"[<{primary_flag_upper}>]"
    if argument.nargs == "*":
        return f"[<{primary_flag_upper}>...]"
    return f"<{primary_flag_upper}>"


def is_conceptually_required(command: CommandSchema, argument: ArgumentSchema, flag_names: list[str]) -> bool:
    """
    Return whether a flag is required by command semantics even with positional fallback.

    Args:
        command (CommandSchema): Owning command schema.
        argument (ArgumentSchema): Option argument schema.
        flag_names (list[str]): Normalized option names.

    Returns:
        bool: True when the value is required.
    """
    return (
        argument.required
        or (command.name == "append-log" and any(name in ("domain", "log_domain", "title", "type") for name in flag_names))
        or (command.name == "edit-log" and any(name in ("datetime", "timestamp") for name in flag_names))
        or (command.name == "edit-diary" and any(name in ("datetime", "timestamp") for name in flag_names))
        or (command.name == "add-task" and "title" in flag_names)
    )


def domain_value_label(raw_label: str, cmd_domain: str) -> str:
    """
    Return a domain-specific placeholder label.

    Args:
        raw_label (str): Raw uppercase placeholder label.
        cmd_domain (str): Command domain.

    Returns:
        str: Display placeholder label.
    """
    if raw_label != "DOMAIN":
        return raw_label
    if cmd_domain == "memory":
        return "MEMORY_DOMAIN"
    if cmd_domain == "logs":
        return "LOG_DOMAIN"
    return "DOMAIN"
