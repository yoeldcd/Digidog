# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Global flag extraction for Brain CLI runtime options.

Provides utility functions to parse presentation and authority flags from argv.
Separates global configuration options from command-specific arguments.
"""

from __future__ import annotations


def extract_global_flags(
    argv: list[str],
) -> tuple[list[str], bool, bool, str, bool, bool]:
    """Separate global presentation flags from command-specific arguments.

    Parses raw command-line tokens to identify global flags such as --color,
    --verbose-log, --authority, and --password-stdin. Returns cleaned argument
    tokens and settings.

    Args:
        argv: Raw command-line tokens after the executable name.

    Returns:
        tuple[list[str], bool, bool, str, bool, bool]: Remaining tokens, color
        enabled, verbose logging enabled, authority string, authority_provided
        flag, and password_stdin flag.

        An omitted authority returns "orchestrator" with
        authority_provided set to False. An empty explicit value returns ""
        with authority_provided set to True. The password_stdin flag is true
        only when the global --password-stdin switch was supplied.
    """
    color_enabled: bool = "--color" in argv or "-c" in argv
    verbose_log: bool = "--verbose-log" in argv or "-vl" in argv
    password_stdin: bool = False

    authority: str = "orchestrator"
    authority_provided: bool = False
    cleaned_argv: list[str] = []
    index = 0

    # Iteration: scan raw command-line argument tokens

    while index < len(argv):
        argument = argv[index]

        if argument in ("--color", "-c", "--verbose-log", "-vl"):
            index += 1
            continue

        if argument == "--password-stdin":
            password_stdin = True
            index += 1
            continue

        if argument == "--authority":
            authority_provided = True
            value_index = index + 1

            if value_index < len(argv) and not argv[value_index].startswith("-"):
                authority = argv[value_index]
                index += 2

            else:
                authority = ""
                index += 1

            continue

        if argument.startswith("--authority="):
            authority = argument.partition("=")[2]
            authority_provided = True
            index += 1
            continue

        cleaned_argv.append(argument)
        index += 1

    return (
        cleaned_argv,
        color_enabled,
        verbose_log,
        authority,
        authority_provided,
        password_stdin,
    )
