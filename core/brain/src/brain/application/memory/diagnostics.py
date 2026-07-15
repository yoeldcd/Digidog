"""Memory store ignore-list and structural diagnostics."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path
from typing import Any

# Application Modules Imports
from brain.application.memory import paths


def load_ignore_list() -> set[str]:
    """Load paths to ignore from memory/.ignore file."""
    ignored = {".ignore", "index.md", ".gitkeep"}
    ignore_file = paths.MEMORY_ROOT / ".ignore"
    if ignore_file.exists():
        try:
            for line in ignore_file.read_text(encoding="utf-8").splitlines():
                line_clean = line.strip()
                if line_clean and not line_clean.startswith("#"):
                    ignored.add(line_clean.strip("/"))
        except Exception:
            pass
    return ignored


def doctor_report() -> dict[str, Any]:
    """Scan MEMORY_ROOT and check for structural compliance, supporting infinite nesting depth."""
    paths.ensure_memory_root()
    errors: list[str] = []
    warnings: list[str] = []
    ignored = load_ignore_list()

    def _check_dir(current_dir: Path, rel_parts: list[str]) -> None:
        try:
            for child in current_dir.iterdir():
                if child.name in ignored or child.name.startswith("."):
                    continue
                new_parts = rel_parts + [child.name]
                if child.is_dir():
                    _check_dir(child, new_parts)
                else:
                    if child.suffix.lower() != ".md":
                        errors.append(
                            f"Invalid file extension: {Path(*new_parts).as_posix()} (only .md files are allowed)",
                        )
        except Exception as exc:
            errors.append(f"Error reading directory {Path(*rel_parts).as_posix() or '.'}: {exc}")

    for child in paths.MEMORY_ROOT.iterdir():
        if child.name in ignored or child.name.startswith("."):
            continue
        if not child.is_dir():
            errors.append(f"Root file found: {child.name} (memory/ should contain only category folders)")
            continue
        _check_dir(child, [child.name])

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }
