#!/usr/bin/env python
# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Propagate the canonical agent prompt to configured mirror files."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[2]
"""Core root discovered from the utility's own installed location."""

CORE_CONFIG_PATH = CORE_ROOT / "configs" / "brain_configs.json"
"""Canonical Brain configuration containing the global `agent_dir`."""

DEFAULT_SOURCE_PATH = CORE_ROOT / "AGENTS.md"
"""Canonical template shared by mirrors and localized Brain consumers."""

DEFAULT_MIRRORS_FILE = CORE_ROOT / "database" / "instruction_mirrors" / "agent_prompt_mirrors.txt"
"""Core-owned registry of canonical prompt mirror destinations."""

DEFAULT_CONSUMERS_FILE = CORE_ROOT / "configs" / "brain_mirrors.json"
"""Core-owned registry of direct Brain consumer repositories."""

TEMPLATE_VARIABLES = (
    "BRAIN_HOME",
    "WORKSPACE_ROOT",
    "AGENT_HOME",
    "BRAIN_SCRIPT_DIR",
    "LOCAL_BRAIN_SCRIPT",
)
"""Supported variables that must be fully resolved before propagation."""

RELATIVE_TEMPLATE_VALUES = {
    "BRAIN_HOME": "core",
    "WORKSPACE_ROOT": ".",
    "AGENT_HOME": ".",
    "BRAIN_SCRIPT_DIR": "$agent/scripts",
    "LOCAL_BRAIN_SCRIPT": "$agent/scripts/brain.py",
}
"""Portable paths interpreted from the active workspace by generic mirrors."""

POWERSHELL_PATH_EXPRESSIONS = {
    "{BRAIN_HOME}/core_cli.py": ("BRAIN_HOME", "core_cli.py"),
    "{LOCAL_BRAIN_SCRIPT}": ("LOCAL_BRAIN_SCRIPT", ""),
}
"""Executable template expressions that require PowerShell-safe quoting."""


@dataclass(slots=True)
class MirrorResult:
    """Result of one mirror propagation attempt.

    Attributes:
        destination (str): Target mirror path.
        status (str): Outcome category for the mirror operation.
        matches_source (bool): Whether the mirror bytes equal the source bytes.
        sha256 (str): Uppercase SHA-256 digest of the mirror when available.
        message (str): Human-readable operation detail.
    """

    destination: str
    status: str
    matches_source: bool
    sha256: str
    message: str


@dataclass(frozen=True, slots=True)
class PromptDestination:
    """Describe one rendered prompt destination.

    Attributes:
        path (Path): Instruction file receiving rendered template content.
        consumer_root (Path | None): Direct consumer root used for absolute
            localization, or `None` for a generic relative-path mirror.
    """

    path: Path
    consumer_root: Path | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse prompt-propagation command-line options.

    Args:
        argv (list[str] | None): Explicit arguments, or None to use process
            arguments.

    Returns:
        argparse.Namespace: Parsed source, mirrors, dry-run, and JSON options.
    """
    parser = argparse.ArgumentParser(description="Copy AGENTS.md into configured prompt mirrors and Brain consumers.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE_PATH), help="Canonical core/AGENTS.md template path.")
    parser.add_argument(
        "--mirrors-file",
        default=str(DEFAULT_MIRRORS_FILE),
        help="Text file containing mirror destination paths.",
    )
    parser.add_argument(
        "--consumers-file",
        default=str(DEFAULT_CONSUMERS_FILE),
        help="JSON registry containing direct Brain consumer repository roots.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate destinations without writing files.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    return parser.parse_args(argv)


def resolve_agent_home() -> Path:
    """Resolve the global agent directory exclusively from the core config.

    Returns:
        Path: Resolved configured agent directory.

    Raises:
        FileNotFoundError: If the canonical Brain configuration is absent.
        ValueError: If the configuration lacks a valid ``agent_dir`` value.
    """
    if not CORE_CONFIG_PATH.is_file():
        raise FileNotFoundError(f"Brain config does not exist: {CORE_CONFIG_PATH}")
    raw_config = json.loads(CORE_CONFIG_PATH.read_text(encoding="utf-8"))
    agent_dir = raw_config.get("agent_dir") if isinstance(raw_config, dict) else None
    if not isinstance(agent_dir, str) or not agent_dir.strip():
        raise ValueError(f"Brain config requires a non-empty agent_dir: {CORE_CONFIG_PATH}")
    return Path(agent_dir).expanduser().resolve()


def read_mirror_paths(mirrors_file: Path) -> list[Path]:
    """Read active destination paths from a mirror-list file.

    Args:
        mirrors_file (Path): Text file containing one mirror path per line.

    Returns:
        list[Path]: Non-comment, non-empty mirror destination paths.

    Raises:
        FileNotFoundError: If the mirror-list file does not exist.
    """
    if not mirrors_file.is_file():
        raise FileNotFoundError(f"Mirror list does not exist: {mirrors_file}")

    destinations: list[Path] = []
    for raw_line in mirrors_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        destinations.append(Path(line))
    return destinations


def read_consumer_roots(consumers_file: Path) -> list[Path]:
    """Read direct Brain consumer roots from the canonical JSON registry.

    Args:
        consumers_file (Path): JSON list whose records contain a non-empty
            ``path`` field.

    Returns:
        list[Path]: Resolved consumer repository roots in registry order.

    Raises:
        FileNotFoundError: If the consumer registry does not exist.
        ValueError: If the registry root is not a JSON list.
    """
    if not consumers_file.is_file():
        raise FileNotFoundError(f"Consumer registry does not exist: {consumers_file}")
    raw_consumers = json.loads(consumers_file.read_text(encoding="utf-8"))
    if not isinstance(raw_consumers, list):
        raise ValueError(f"Consumer registry must contain a JSON list: {consumers_file}")

    roots: list[Path] = []
    for record in raw_consumers:
        raw_path = record.get("path") if isinstance(record, dict) else None
        if isinstance(raw_path, str) and raw_path.strip():
            roots.append(Path(raw_path).expanduser().resolve())
    return roots


def collect_destinations(
    source: Path,
    mirrors: list[Path],
    consumer_roots: list[Path],
) -> list[PromptDestination]:
    """Combine explicit mirrors with consumer-root ``AGENTS.md`` targets.

    Args:
        source (Path): Canonical instruction file, excluded from destinations.
        mirrors (list[Path]): Explicit mirror file paths.
        consumer_roots (list[Path]): Direct Brain consumer repository roots.

    Returns:
        list[PromptDestination]: Stable destinations carrying their rendering
            context and preserving first use.
    """
    source_key = str(source.expanduser().resolve()).casefold()
    destinations: list[PromptDestination] = []
    seen: set[str] = {source_key}
    consumer_targets = {
        str((root.expanduser().resolve() / "AGENTS.md")).casefold(): root.expanduser().resolve()
        for root in consumer_roots
    }
    candidates = [*mirrors, *(root / "AGENTS.md" for root in consumer_roots)]
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        key = str(resolved).casefold()
        if key not in seen:
            seen.add(key)
            destinations.append(
                PromptDestination(
                    path=resolved,
                    consumer_root=consumer_targets.get(key),
                )
            )
    return destinations


def template_values(destination: PromptDestination, agent_home: Path) -> dict[str, str]:
    """Build relative mirror values or absolute consumer-localized values.

    Args:
        destination (PromptDestination): Target and optional consumer context.
        agent_home (Path): Canonical shared agent directory.

    Returns:
        dict[str, str]: Complete values for every supported template variable.
    """
    if destination.consumer_root is None:
        return dict(RELATIVE_TEMPLATE_VALUES)

    workspace_root = destination.consumer_root.expanduser().resolve()
    return {
        "BRAIN_HOME": CORE_ROOT.resolve().as_posix(),
        "WORKSPACE_ROOT": workspace_root.as_posix(),
        "AGENT_HOME": agent_home.expanduser().resolve().as_posix(),
        "BRAIN_SCRIPT_DIR": (workspace_root / "$agent" / "scripts").as_posix(),
        "LOCAL_BRAIN_SCRIPT": (workspace_root / "$agent" / "scripts" / "brain.py").as_posix(),
    }


def quote_powershell_literal(value: str) -> str:
    """Quote one path as a PowerShell single-quoted literal.

    Args:
        value (str): Unquoted path expression to protect from interpolation.

    Returns:
        str: Single-quoted literal with embedded apostrophes escaped by doubling.
    """
    return f"'{value.replace(chr(39), chr(39) * 2)}'"


def render_prompt_template(template: str, values: dict[str, str]) -> str:
    """Render and validate one canonical prompt template.

    Args:
        template (str): UTF-8 instruction template content.
        values (dict[str, str]): Values keyed by supported variable name.

    Returns:
        str: Fully localized instruction content.

    Raises:
        ValueError: If a supported variable has no value or remains unresolved.
    """
    rendered = template
    for expression, (variable, child_name) in POWERSHELL_PATH_EXPRESSIONS.items():
        base_path = values.get(variable)
        if not isinstance(base_path, str) or not base_path:
            raise ValueError(f"Template variable requires a non-empty value: {variable}")
        executable_path = f"{base_path.rstrip('/')}/{child_name}" if child_name else base_path
        quoted_path = quote_powershell_literal(value=executable_path)
        rendered = rendered.replace(expression, quoted_path)
    for variable in TEMPLATE_VARIABLES:
        value = values.get(variable)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Template variable requires a non-empty value: {variable}")
        rendered = rendered.replace(f"{{{variable}}}", value)
    unresolved = [variable for variable in TEMPLATE_VARIABLES if f"{{{variable}}}" in rendered]
    if unresolved:
        raise ValueError(f"Unresolved prompt template variables: {', '.join(unresolved)}")
    return rendered


def sha256_file(path: Path) -> str:
    """Calculate the uppercase SHA-256 digest for a file.

    Args:
        path (Path): File whose bytes are hashed in fixed-size chunks.

    Returns:
        str: Uppercase hexadecimal SHA-256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def propagate_prompt(
    source: Path,
    destinations: list[PromptDestination],
    agent_home: Path,
    dry_run: bool,
) -> list[MirrorResult]:
    """Copy a canonical prompt to mirrors and verify resulting hashes.

    Args:
        source (Path): Canonical prompt file to propagate.
        destinations (list[PromptDestination]): Configured targets and their
            localization context.
        agent_home (Path): Canonical shared agent directory.
        dry_run (bool): Whether to inspect targets without writing them.

    Returns:
        list[MirrorResult]: One detailed propagation result per destination.

    Raises:
        FileNotFoundError: If the canonical source prompt does not exist.
    """
    if not source.is_file():
        raise FileNotFoundError(f"Source prompt does not exist: {source}")

    template = source.read_bytes().decode("utf-8")
    results: list[MirrorResult] = []

    for target in destinations:
        destination = target.path
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

        rendered_content = render_prompt_template(
            template=template,
            values=template_values(destination=target, agent_home=agent_home),
        )
        rendered_bytes = rendered_content.encode("utf-8")
        expected_hash = hashlib.sha256(rendered_bytes).hexdigest().upper()

        if dry_run:
            existing_hash = sha256_file(destination) if destination.is_file() else ""
            matches_source = existing_hash == expected_hash
            results.append(
                MirrorResult(
                    destination=str(destination),
                    status="dry-run" if matches_source else "would-update",
                    matches_source=matches_source,
                    sha256=existing_hash,
                    message=(
                        "Destination already matches rendered template."
                        if matches_source
                        else "Destination differs; propagation would update it."
                    ),
                )
            )
            continue

        destination.write_bytes(rendered_bytes)
        destination_hash = sha256_file(destination)
        results.append(
            MirrorResult(
                destination=str(destination),
                status="updated" if destination_hash == expected_hash else "error",
                matches_source=destination_hash == expected_hash,
                sha256=destination_hash,
                message="Destination matches rendered template."
                if destination_hash == expected_hash
                else "Destination hash differs from rendered template.",
            )
        )

    return results


def print_results(results: list[MirrorResult], as_json: bool) -> None:
    """Render prompt-propagation results for humans or machines.

    Args:
        results (list[MirrorResult]): Completed mirror operation results.
        as_json (bool): Whether to emit a machine-readable JSON payload.
    """
    if as_json:
        payload = {
            "ok": all(item.status != "error" for item in results),
            "mirrors": [asdict(item) for item in results],
        }
        print(json.dumps(payload, indent=2))
        return

    for result in results:
        marker = "ERR" if result.status == "error" else "OK"
        print(f"[{marker}] {result.destination} - {result.status} - {result.message}")


def main(argv: list[str] | None = None) -> int:
    """Run canonical prompt propagation from parsed command-line arguments.

    Args:
        argv (list[str] | None): Explicit arguments, or None to use process
            arguments.

    Returns:
        int: Zero when every mirror succeeds; otherwise one.
    """
    args = parse_args(argv)
    source = Path(args.source)
    mirrors_file = Path(args.mirrors_file)
    consumers_file = Path(args.consumers_file)

    try:
        agent_home = resolve_agent_home()
        destinations = collect_destinations(
            source=source,
            mirrors=read_mirror_paths(mirrors_file),
            consumer_roots=read_consumer_roots(consumers_file),
        )
        results = propagate_prompt(
            source=source,
            destinations=destinations,
            agent_home=agent_home,
            dry_run=args.dry_run,
        )
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
