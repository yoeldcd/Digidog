# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to search or list available snippets."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import ast
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

# Application Modules Imports
from brain.infrastructure.runtime.paths import get_agent_home, get_workspace_root
from brain.presentation.terminal import log_step, render_placeholders


_SCRIPT_LANGUAGE_BY_SUFFIX: Final[Mapping[str, str]] = MappingProxyType({
    ".awk": "hash",
    ".bash": "hash",
    ".bat": "batch",
    ".cjs": "slash",
    ".cmd": "batch",
    ".fish": "hash",
    ".groovy": "slash",
    ".js": "slash",
    ".jsx": "slash",
    ".jl": "hash",
    ".lua": "dash",
    ".mjs": "slash",
    ".php": "php",
    ".pl": "hash",
    ".pm": "hash",
    ".ps1": "powershell",
    ".psd1": "powershell",
    ".psm1": "powershell",
    ".py": "python",
    ".pyw": "python",
    ".r": "hash",
    ".rb": "hash",
    ".sh": "hash",
    ".tcl": "hash",
    ".ts": "slash",
    ".tsx": "slash",
    ".zsh": "hash",
})
_COMMENT_PREFIXES_BY_LANGUAGE: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType({
    "batch": ("@rem ", "rem ", "::"),
    "dash": ("--",),
    "hash": ("#",),
    "php": ("//", "#", "/*", "*"),
    "powershell": ("#", "<#"),
    "python": ("#",),
    "slash": ("//", "/*", "*"),
})
_IGNORED_COMMENT_PREFIXES: Final[tuple[str, ...]] = (
    "author:",
    "coding:",
    "x:",
    "-*-",
)
_EXCLUDED_UTILITY_NAMES: Final[frozenset[str]] = frozenset({
    "__pycache__",
    "brain",
    "core.py",
})
_VALID_SCOPES: Final[frozenset[str]] = frozenset({
    "all",
    "global",
    "local",
})


@dataclass(frozen=True, slots=True)
class UtilityCandidate:
    """Represent one discovered utility and its source scope.

    Attributes:
        scope: Source scope containing the utility.
        path: Absolute filesystem path of the utility.
    """

    scope: str
    path: Path


def _script_language(path: Path, source_lines: list[str]) -> str | None:
    """Infer a supported scripting-language comment family.

    Args:
        path: Script path used for suffix-based detection.
        source_lines: Source lines used for shebang detection.

    Returns:
        The normalized comment-family name, or ``None`` when unsupported.
    """
    suffix_language = _SCRIPT_LANGUAGE_BY_SUFFIX.get(path.suffix.casefold())
    if suffix_language is not None:
        return suffix_language
    if not source_lines or not source_lines[0].startswith("#!"):
        return None

    interpreter = source_lines[0].casefold()
    if "python" in interpreter:
        return "python"
    if "pwsh" in interpreter or "powershell" in interpreter:
        return "powershell"
    if any(name in interpreter for name in ("bash", "fish", "/sh", "zsh")):
        return "hash"
    if any(name in interpreter for name in ("bun", "deno", "node")):
        return "slash"
    if "lua" in interpreter:
        return "dash"
    if "php" in interpreter:
        return "php"
    if any(name in interpreter for name in ("awk", "julia", "perl", "ruby", "rscript", "tcl")):
        return "hash"
    return None


def _script_description(path: Path) -> str:
    """Return the first human-readable specification from a script.

    Args:
        path: Script path to inspect.

    Returns:
        The first description line, or an empty string when unavailable.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""

    source_lines = source.splitlines()
    language = _script_language(path=path, source_lines=source_lines)
    if language is None:
        return ""
    if language == "python":
        try:
            module_description = ast.get_docstring(ast.parse(source), clean=True)
        except SyntaxError:
            module_description = None
        if module_description:
            return module_description.splitlines()[0].strip()

    comment_prefixes = _COMMENT_PREFIXES_BY_LANGUAGE[language]
    for raw_line in source_lines:
        stripped_line = raw_line.strip()
        folded_line = stripped_line.casefold()
        if not stripped_line or stripped_line.startswith("#!"):
            continue
        for comment_prefix in comment_prefixes:
            if not folded_line.startswith(comment_prefix):
                continue
            description = stripped_line[len(comment_prefix):].strip().removesuffix("*/").strip()
            if description and not description.casefold().startswith(_IGNORED_COMMENT_PREFIXES):
                return description

    return ""


def _markdown_description(path: Path) -> str:
    """Return the first prose paragraph that follows a Markdown header.

    Args:
        path: Markdown file to inspect.

    Returns:
        The first prose paragraph, or an empty string when unavailable.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return ""

    header_seen = False
    paragraph_lines: list[str] = []
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("#"):
            if paragraph_lines:
                break
            header_seen = True
            continue
        if not header_seen:
            continue
        if not stripped_line:
            if paragraph_lines:
                break
            continue
        if (
            stripped_line.startswith(("- ", "* ", "+ ", ">", "|", "```", "~~~"))
            or re.match(r"^\d+[.)]\s", stripped_line)
        ):
            if paragraph_lines:
                break
            continue
        paragraph_lines.append(stripped_line)

    return " ".join(paragraph_lines)


def _folder_description(path: Path) -> str:
    """Resolve a utility-folder description through canonical fallbacks.

    Args:
        path: Utility folder whose description should be resolved.

    Returns:
        The first available README or script description.
    """
    root_readme = path / "README.md"
    if root_readme.is_file():
        return _markdown_description(path=root_readme)

    documentation_readme = path / "documentation" / "README.md"
    if documentation_readme.is_file():
        return _markdown_description(path=documentation_readme)

    root_scripts = sorted(
        (child for child in path.iterdir() if child.is_file()),
        key=lambda child: child.name.casefold(),
    )
    for script_path in root_scripts:
        description = _script_description(path=script_path)
        if description:
            return description
    return ""


def _normalize_scope(raw_scope: object) -> str:
    """Normalize and validate one requested utility scope.

    Args:
        raw_scope: Raw parser value supplied by the command boundary.

    Returns:
        Normalized scope name.

    Raises:
        ValueError: The requested scope is not `local`, `global`, or `all`.
    """
    scope = str(raw_scope).casefold()

    if scope not in _VALID_SCOPES:
        raise ValueError("--scope must be local, global, or all.")

    return scope


def _collect_candidates(scope: str, query: str | None) -> tuple[UtilityCandidate, ...]:
    """Collect ordered utilities from the selected source scopes.

    Args:
        scope: Validated source scope to inspect.
        query: Optional case-insensitive utility-name filter.

    Returns:
        Immutable candidates ordered by local scope, global scope, kind, and name.
    """
    utility_sources: tuple[tuple[str, Path], ...] = (
        ("local", get_workspace_root() / "$agent" / "scripts"),
        ("global", get_agent_home() / "snippets"),
    )
    normalized_query = query.casefold() if query else None
    candidates: list[UtilityCandidate] = []

    for source_scope, utility_directory in utility_sources:
        if scope not in ("all", source_scope):
            continue

        if not utility_directory.is_dir():
            continue

        paths = sorted(
            utility_directory.iterdir(),
            key=lambda path: (not path.is_dir(), path.name.casefold()),
        )

        for utility_path in paths:
            if utility_path.name in _EXCLUDED_UTILITY_NAMES:
                continue

            if normalized_query and normalized_query not in utility_path.name.casefold():
                continue

            candidate = UtilityCandidate(
                scope=source_scope,
                path=utility_path,
            )
            candidates.append(candidate)

    return tuple(candidates)


def _describe_utility(path: Path) -> str:
    """Resolve the human-readable description for one utility path.

    Args:
        path: File or folder representing one utility.

    Returns:
        Resolved description, or an empty string when unavailable.
    """
    if path.is_dir():
        return _folder_description(path=path)

    return _script_description(path=path)


def _render_catalog(
    candidates: tuple[UtilityCandidate, ...],
) -> tuple[str, list[dict[str, str]]]:
    """Render human output and serialize utility entries.

    Args:
        candidates: Ordered immutable utility candidates.

    Returns:
        Human-readable catalog text and JSON-compatible utility entries.
    """
    output_lines: list[str] = ["# Available Utilities"]
    serialized_entries: list[dict[str, str]] = []
    rendered_scope: str | None = None

    for candidate in candidates:
        utility_path = candidate.path

        if candidate.scope != rendered_scope:
            scope_title = (
                "Local Utilities"
                if candidate.scope == "local"
                else "Shared Snippets"
            )
            output_lines.extend(("", f"## {scope_title}", ""))
            rendered_scope = candidate.scope

        kind_label = "Folder" if utility_path.is_dir() else "File"
        description = _describe_utility(path=utility_path)
        description_suffix = f" - {description}" if description else ""
        output_line = f"- **{utility_path.name}** ({kind_label}){description_suffix}"
        serialized_entry = {
            "description": description,
            "path": utility_path.as_posix(),
        }

        output_lines.append(output_line)
        serialized_entries.append(serialized_entry)

    rendered_output = "\n".join(output_lines)

    return rendered_output, serialized_entries


def _build_payload(
    scope: str,
    query: str | None,
    serialized_entries: list[dict[str, str]],
) -> dict[str, object]:
    """Build the command payload without mutating the parser namespace.

    Args:
        scope: Validated scope requested for the catalog.
        query: Optional utility-name filter.
        serialized_entries: JSON-compatible utility entries.

    Returns:
        Complete command payload for the presentation boundary.
    """
    return {
        "ok": True,
        "command": "list-snippets",
        "scope": scope,
        "filter": query,
        "count": len(serialized_entries),
        "snippets": serialized_entries,
    }


def _empty_result_message(query: str | None) -> str:
    """Return the user-facing message for an empty catalog.

    Args:
        query: Optional utility-name filter.

    Returns:
        Empty-result message matching the active filter state.
    """
    if query:
        return f"No snippets found matching filter '{query}'."

    return "No snippets available."


def handle(args: argparse.Namespace) -> int:
    """List reusable utilities, optionally filtered by scope and name.

    Args:
        args: Parsed command options containing query, scope, color, and output settings.

    Returns:
        Zero when the catalog is rendered; otherwise one after reporting an error.
    """
    color_enabled = bool(getattr(args, "color", False))

    try:
        log_step(args, "Scanning available snippets...")

        query = getattr(args, "filter", None) or getattr(args, "query", None)
        scope = _normalize_scope(raw_scope=getattr(args, "scope", "all"))
        candidates = _collect_candidates(
            scope=scope,
            query=query,
        )

        if not candidates:
            empty_message = _empty_result_message(query=query)
            serialized_entries: list[dict[str, str]] = []
            payload = _build_payload(
                scope=scope,
                query=query,
                serialized_entries=serialized_entries,
            )

            print(empty_message)
            args.json_payload = payload

            return 0

        rendered_output, serialized_entries = _render_catalog(candidates=candidates)
        payload = _build_payload(
            scope=scope,
            query=query,
            serialized_entries=serialized_entries,
        )

        print(rendered_output)
        args.json_payload = payload

        return 0
    except Exception as exc:
        error_message = f"__RED__Error: {exc}__RESET__"
        rendered_error = render_placeholders(error_message, color_enabled)

        print(rendered_error)

        return 1
