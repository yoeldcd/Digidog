"""Action module to backup (export) memory domains."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from brain.application.memory.paths import MEMORY_ROOT, resolve_category_dir
from brain.presentation.terminal import get_color_codes, log_step



def handle(args: argparse.Namespace) -> int:
    """Export memory domain directories to a target path."""
    bold, cyan, green, red, yellow, magenta, dim, reset = get_color_codes(getattr(args, "color", False))
    try:
        log_step(args, '[1/2] Resolving domain...')
        domain = args.domain
        out_value = args.out if args.out is not None else args.out_dir
        if out_value is None:
            print(f"{red}Error: Destination directory must be provided via --out or compact positional form.{reset}")
            return 1
        out_dir = Path(out_value).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        log_step(args, '[2/2] Exporting...')
        if domain.lower() == "all":
            # Export all directories
            for item in MEMORY_ROOT.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    shutil.copytree(str(item), str(out_dir / item.name), dirs_exist_ok=True)
            print(f"{green}Successfully exported entire memory store to {cyan}{out_dir}{reset}")
            exported = [item.name for item in MEMORY_ROOT.iterdir() if item.is_dir() and not item.name.startswith(".")]
        else:
            cat_dir = resolve_category_dir(domain)
            if not cat_dir.exists():
                raise FileNotFoundError(f"Memory domain '{domain}' does not exist.")
            shutil.copytree(str(cat_dir), str(out_dir / domain), dirs_exist_ok=True)
            print(f"{green}Successfully exported memory domain {magenta}{domain}{green} to {cyan}{out_dir / domain}{reset}")
            exported = [domain]
        args.json_payload = {
            "ok": True,
            "command": "export",
            "requestedDomain": domain,
            "destination": out_dir.as_posix(),
            "count": len(exported),
            "domains": exported,
        }
        return 0
    except Exception as exc:
        print(f"{red}Error: {exc}{reset}")
        return 1
