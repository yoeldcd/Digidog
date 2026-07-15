"""Thin command-line entrypoint for the Brain CLI."""

from __future__ import annotations

from brain.presentation.console import configure_utf8_console
from brain.presentation.router.services.cli_runtime_service import run_cli


def main(argv: list[str] | None = None) -> int:
    """Configure console runtime and delegate CLI execution."""
    configure_utf8_console()
    return run_cli(argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
