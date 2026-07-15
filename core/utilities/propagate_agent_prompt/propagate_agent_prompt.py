#!/usr/bin/env python
"""Propagate the canonical agent prompt to configured mirror files."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[2]
"""Core root discovered from the utility's own installed location."""

CORE_CONFIG_PATH = CORE_ROOT / "configs" / "brain_configs.json"
"""Canonical Brain configuration containing the global `agent_dir`."""

DEFAULT_MIRRORS_FILE = CORE_ROOT / "database" / "instruction_mirrors" / "agent_prompt_mirrors.txt"
"""Core-owned registry of canonical prompt mirror destinations."""


@dataclass(slots=True)
class MirrorResult:
    """Result of one mirror propagation attempt."""

    destination: str
    status: str
    matches_source: bool
    sha256: str
    message: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    agent_home = resolve_agent_home()
    parser = argparse.ArgumentParser(description="Copy AGENT.md into configured prompt mirrors.")
    parser.add_argument("--source", default=str(agent_home / "AGENT.md"), help="Canonical AGENT.md source path.")
    parser.add_argument(
        "--mirrors-file",
        default=str(DEFAULT_MIRRORS_FILE),
        help="Text file containing mirror destination paths.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate destinations without writing files.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    return parser.parse_args(argv)


def resolve_agent_home() -> Path:
    """Resolve the global agent directory exclusively from the core config."""
    if not CORE_CONFIG_PATH.is_file():
        raise FileNotFoundError(f"Brain config does not exist: {CORE_CONFIG_PATH}")
    raw_config = json.loads(CORE_CONFIG_PATH.read_text(encoding="utf-8"))
    agent_dir = raw_config.get("agent_dir") if isinstance(raw_config, dict) else None
    if not isinstance(agent_dir, str) or not agent_dir.strip():
        raise ValueError(f"Brain config requires a non-empty agent_dir: {CORE_CONFIG_PATH}")
    return Path(agent_dir).expanduser().resolve()


def read_mirror_paths(mirrors_file: Path) -> list[Path]:
    """Read destination paths from a mirror list file."""
    if not mirrors_file.is_file():
        raise FileNotFoundError(f"Mirror list does not exist: {mirrors_file}")

    destinations: list[Path] = []
    for raw_line in mirrors_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        destinations.append(Path(line))
    return destinations


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def propagate_prompt(source: Path, destinations: list[Path], dry_run: bool) -> list[MirrorResult]:
    """Copy source prompt to destinations and verify hashes."""
    if not source.is_file():
        raise FileNotFoundError(f"Source prompt does not exist: {source}")

    source_hash = sha256_file(source)
    results: list[MirrorResult] = []

    for destination in destinations:
        parent = destination.parent
        if not parent.is_dir():
            results.append(
                MirrorResult(
                    destination=str(destination),
                    status="error",
                    matches_source=False,
                    sha256="",
                    message=f"Parent directory does not exist: {parent}",
                )
            )
            continue

        if dry_run:
            existing_hash = sha256_file(destination) if destination.is_file() else ""
            matches_source = existing_hash == source_hash
            results.append(
                MirrorResult(
                    destination=str(destination),
                    status="dry-run" if matches_source else "would-update",
                    matches_source=matches_source,
                    sha256=existing_hash,
                    message="Destination already matches source." if matches_source else "Destination differs; propagation would update it.",
                )
            )
            continue

        shutil.copyfile(source, destination)
        destination_hash = sha256_file(destination)
        results.append(
            MirrorResult(
                destination=str(destination),
                status="updated" if destination_hash == source_hash else "error",
                matches_source=destination_hash == source_hash,
                sha256=destination_hash,
                message="Mirror matches source." if destination_hash == source_hash else "Mirror hash differs from source.",
            )
        )

    return results


def print_results(results: list[MirrorResult], as_json: bool) -> None:
    """Print propagation results for humans or machines."""
    if as_json:
        print(json.dumps({"ok": all(item.status != "error" for item in results), "mirrors": [asdict(item) for item in results]}, indent=2))
        return

    for result in results:
        marker = "ERR" if result.status == "error" else "OK"
        print(f"[{marker}] {result.destination} - {result.status} - {result.message}")


def main(argv: list[str] | None = None) -> int:
    """Run prompt propagation."""
    args = parse_args(argv)
    source = Path(args.source)
    mirrors_file = Path(args.mirrors_file)

    try:
        destinations = read_mirror_paths(mirrors_file)
        results = propagate_prompt(source, destinations, dry_run=args.dry_run)
        print_results(results, as_json=args.json)
        return 0 if all(item.status != "error" for item in results) else 1
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
