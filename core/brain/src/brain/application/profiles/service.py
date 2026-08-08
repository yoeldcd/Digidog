# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Profile-specific helpers built on top of the Markdown memory store."""

from __future__ import annotations

# Standard Libraries Imports
import re
from pathlib import Path

# Application Modules Imports
from brain.application.memory.paths import BrainStoreError, validate_part_name
from brain.infrastructure.runtime.paths import get_agent_home, get_workspace_root


PROFILE_TEMPLATE_VARIABLES = (
    "BRAIN_HOME",
    "WORKSPACE_ROOT",
    "AGENT_HOME",
    "BRAIN_SCRIPT_DIR",
    "LOCAL_BRAIN_SCRIPT",
)
"""Runtime path variables supported in persisted profile and memory content."""

PROFILE_SCRIPT_PATH_PATTERN = re.compile(r"\{BRAIN_SCRIPT_DIR\}(?P<suffix>/[A-Za-z0-9_./-]+)")
"""Composite script paths that require quoting after localization."""


def get_profiles_dir() -> Path:
    """Return the memory directory that stores agent profiles.

    Returns:
        Path: Agent-owned profile directory.
    """
    return get_agent_home() / "memory" / "profiles"


def discover_profile_names(profiles_dir: Path | None = None) -> list[str]:
    """Discover names from legacy profile files and modular profile folders.

    Args:
        profiles_dir (Path | None): Optional profile root override.

    Returns:
        list[str]: Case-insensitively sorted profile names.
    """
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


def profile_summaries(profiles_dir: Path | None = None) -> list[dict[str, object]]:
    """Build compact profile records with root usage guidance.

    Args:
        profiles_dir (Path | None): Optional profile root override.

    Returns:
        list[dict[str, object]]: Ordered profile summaries and retrieval commands.
    """
    root = profiles_dir or get_profiles_dir()
    summaries: list[dict[str, object]] = []
    for index, name in enumerate(discover_profile_names(root), start=1):
        usage_path = root / name / "usage.md"
        use_when = usage_path.read_text(encoding="utf-8").strip() if usage_path.is_file() else ""
        summaries.append({
            "id": index,
            "name": name,
            "retrieve_command": f"read-profile {name}",
            "use_when": use_when,
        })
    return summaries


def build_dir_tree(dir_path: Path, prefix: str = "") -> list[str]:
    """Build a connector-based tree for nested profile directories.

    Args:
        dir_path (Path): Directory whose visible children are rendered.
        prefix (str): Connector prefix inherited from ancestor levels.

    Returns:
        list[str]: Display lines for the directory subtree.
    """
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
    """Read all Markdown entries for one profile as ordered key-content pairs.

    Args:
        name (str): Profile name to validate and resolve.

    Returns:
        list[tuple[str, str]]: Ordered entry names and Markdown bodies.

    Raises:
        BrainStoreError: The profile name is invalid or no profile exists.
    """
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


def render_profile_template_variables(content: str, workspace_root: Path | None = None) -> str:
    """Localize supported runtime paths in persisted profile and memory content.

    Args:
        content (str): Raw Markdown content containing optional template variables.
        workspace_root (Path | None): Optional consumer workspace override. Defaults to the
            active workspace resolved by the Brain runtime.

    Returns:
        str: Content with PowerShell-safe, consumer-localized paths.
    """
    root = get_workspace_root(workspace_root=workspace_root)
    agent_home = get_agent_home()
    brain_script_dir = agent_home / "scripts"
    local_brain_script = (brain_script_dir / "brain.py").as_posix().replace("'", "''")
    brain_home = agent_home / "core"

    values = {
        "WORKSPACE_ROOT": root.as_posix(),
        "AGENT_HOME": agent_home.as_posix(),
        "BRAIN_HOME": brain_home.as_posix(),
        "BRAIN_SCRIPT_DIR": brain_script_dir.as_posix(),
        "LOCAL_BRAIN_SCRIPT": f"'{local_brain_script}'",
    }
    rendered = content
    matches = list(PROFILE_SCRIPT_PATH_PATTERN.finditer(rendered))
    for match in reversed(matches):
        script_path = f"{values['BRAIN_SCRIPT_DIR']}{match.group('suffix')}".replace("'", "''")
        rendered = f"{rendered[:match.start()]}'{script_path}'{rendered[match.end():]}"
    for variable in PROFILE_TEMPLATE_VARIABLES:
        rendered = rendered.replace(f"{{{variable}}}", values[variable])
    return rendered


def render_profile(name: str, entries: list[tuple[str, str]]) -> str:
    """Render a complete profile readout from ordered Markdown entries.

    Args:
        name (str): Profile name shown in the top-level heading.
        entries (list[tuple[str, str]]): Ordered entry names and Markdown bodies.

    Returns:
        str: Complete profile document with stable trailing newline.
    """
    profile_name = validate_part_name(name)
    lines = [f"# Profile: {profile_name}", ""]

    for key, content in entries:
        lines.append(f"## {key}")
        lines.append("")
        lines.append(content.rstrip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
