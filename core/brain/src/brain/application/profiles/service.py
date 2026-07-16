# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Profile-specific helpers built on top of the Markdown memory store."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Application Modules Imports
from brain.application.memory.paths import BrainStoreError, validate_part_name
from brain.infrastructure.runtime.paths import get_agent_home


def get_profiles_dir() -> Path:
    """Return the memory directory that stores agent profiles."""
    return get_agent_home() / "memory" / "profiles"


def discover_profile_names(profiles_dir: Path | None = None) -> list[str]:
    """Return profile names for both legacy files and modular profile folders."""
    root = profiles_dir or get_profiles_dir()
    if not root.exists():
        return []

    names: set[str] = set()
    for child in root.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_file() and child.suffix.lower() == ".md":
            names.add(child.stem)
        elif child.is_dir() and any(entry.is_file() and entry.suffix.lower() == ".md" for entry in child.rglob("*.md")):
            names.add(child.name)

    return sorted(names, key=str.lower)


def build_dir_tree(dir_path: Path, prefix: str = "") -> list[str]:
    """Build a connector-based tree for nested profile directories."""
    lines = []
    if not dir_path.exists():
        return lines

    try:
        children = sorted(
            [child for child in dir_path.iterdir() if not child.name.startswith(".")],
            key=lambda item: (not item.is_dir(), item.name.lower()),
        )
    except OSError:
        return lines

    for index, child in enumerate(children):
        is_last = index == len(children) - 1
        connector = "`-- " if is_last else "+-- "
        child_prefix = prefix + connector
        if child.is_dir():
            lines.append(f"{child_prefix}{child.name}/")
            next_prefix = prefix + ("    " if is_last else "|   ")
            lines.extend(build_dir_tree(child, next_prefix))
        else:
            lines.append(f"{child_prefix}{child.name}")
    return lines


def read_profile_entries(name: str) -> list[tuple[str, str]]:
    """Read all Markdown entries for one profile as ordered key/content pairs."""
    profile_name = validate_part_name(name)
    root = get_profiles_dir()
    profile_dir = root / profile_name
    legacy_file = root / f"{profile_name}.md"

    if profile_dir.is_dir():
        entries = []
        files = []
        subdirs = []

        for child in profile_dir.iterdir():
            if child.name.startswith("."):
                continue
            if child.is_file() and child.suffix.lower() == ".md":
                files.append(child)
            elif child.is_dir():
                subdirs.append(child)

        for path in sorted(files, key=lambda item: item.name.lower()):
            rel_key = path.stem
            entries.append((rel_key, path.read_text(encoding="utf-8")))

        if subdirs:
            help_lines = [
                "Remaining domain directories:",
                "",
            ]
            ordered_subdirs = sorted(subdirs, key=lambda item: item.name.lower())
            for index, subdir in enumerate(ordered_subdirs):
                is_last = index == len(ordered_subdirs) - 1
                connector = "`-- " if is_last else "+-- "
                help_lines.append(f"{connector}{subdir.name}/")
                next_prefix = "    " if is_last else "|   "
                help_lines.extend(build_dir_tree(subdir, next_prefix))
            help_lines.append("")
            help_lines.append("Help: To read these directories, run:")
            help_lines.append(f"`get-memory-entry profiles.{profile_name}.<directory>`")

            entries.append(("Directivas Adicionales", "\n".join(help_lines)))

        if entries:
            return entries

    if legacy_file.is_file():
        return [(profile_name, legacy_file.read_text(encoding="utf-8"))]

    raise BrainStoreError(f"Profile '{profile_name}' does not exist.")


def render_profile(name: str, entries: list[tuple[str, str]]) -> str:
    """Render a complete profile readout from ordered Markdown entries."""
    profile_name = validate_part_name(name)
    lines = [f"# Profile: {profile_name}", ""]

    for key, content in entries:
        lines.append(f"## {key}")
        lines.append("")
        lines.append(content.rstrip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
