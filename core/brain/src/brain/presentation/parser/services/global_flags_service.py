# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Global flag extraction for Brain CLI runtime options."""

from __future__ import annotations


def extract_global_flags(argv: list[str]) -> tuple[list[str], bool, bool]:
    """Separate global presentation flags from command-specific arguments.

    Args:
        argv (list[str]): Raw command-line tokens after the executable name.

    Returns:
        tuple[list[str], bool, bool]: Remaining tokens, whether color is enabled,
        and whether verbose activity logging is enabled.
    """
    color_enabled: bool = "--color" in argv or "-c" in argv
    verbose_log: bool = "--verbose-log" in argv or "-vl" in argv
    cleaned_argv: list[str] = [
        argument
        for argument in argv
        if argument not in ("--color", "-c", "--verbose-log", "-vl")
    ]

    return cleaned_argv, color_enabled, verbose_log
