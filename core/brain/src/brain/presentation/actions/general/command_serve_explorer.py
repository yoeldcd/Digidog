"""Action module to serve the Brain Explorer local web UI."""

from __future__ import annotations

# Standard Libraries Imports
import argparse

# Application Modules Imports
from brain.infrastructure.explorer.server import serve_brain_explorer
from brain.presentation.terminal import render_placeholders


def handle(args: argparse.Namespace) -> int:
    """
    Start the local Brain Explorer HTTP server.

    Args:
        args (argparse.Namespace): Parsed CLI arguments containing host, port, and API timeout.

    Returns:
        int: Process exit code.
    """
    color_enabled: bool = getattr(args, "color", False)
    if getattr(args, "json", False):
        args.json_payload = {
            "ok": True,
            "command": "serve-explorer",
            "server": {
                "host": str(args.host),
                "port": int(args.port),
                "apiTimeoutSeconds": float(args.api_timeout),
                "url": f"http://{args.host}:{args.port}",
                "started": False,
                "reason": "JSON mode reports the foreground server configuration without blocking the caller.",
            },
        }
        return 0
    try:
        serve_brain_explorer(
            host=str(args.host),
            port=int(args.port),
            api_timeout=float(args.api_timeout),
        )
        return 0
    except KeyboardInterrupt:
        print(render_placeholders("__YELLOW__Brain Explorer server stopped.__RESET__", color_enabled))
        return 0
    except Exception as exc:
        print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1
