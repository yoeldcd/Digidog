"""Input parsing and validation for Brain Explorer routes."""

from http import HTTPStatus
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from brain.infrastructure.explorer.contracts import ApiRouteError
from brain.infrastructure.runtime.paths import get_brain_mirrors_path

ALLOWED_SCOPE_VALUES = {"all", "global", "local"}


def load_registered_projects() -> list[dict[str, str]]:
    """Load valid agent-owned consumer records from the core mirror registry."""
    mirrors_file = get_brain_mirrors_path()
    if not mirrors_file.is_file():
        return []
    try:
        raw_data = json.loads(mirrors_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw_data, list):
        return []
    projects: list[dict[str, str]] = []
    for raw_project in raw_data:
        if not isinstance(raw_project, dict):
            continue
        name = raw_project.get("name")
        path = raw_project.get("path")
        if isinstance(name, str) and name.strip() and isinstance(path, str) and path.strip():
            projects.append({"name": name.strip(), "path": Path(path).expanduser().resolve().as_posix()})
    return projects


def resolve_registered_workspace_root(
    requested_root: Path | str,
) -> Path:
    """Resolve one Explorer workspace only when it belongs to this agent."""
    candidate = Path(requested_root).expanduser().resolve()
    registered_projects = load_registered_projects()
    if not registered_projects:
        raise ApiRouteError(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "The agent core has no valid registered consumers.",
        )
    allowed_roots = {
        os.path.normcase(str(Path(project["path"]).resolve()))
        for project in registered_projects
    }
    if os.path.normcase(str(candidate)) not in allowed_roots:
        raise ApiRouteError(
            HTTPStatus.FORBIDDEN,
            "The requested workspace is not a registered consumer of this agent core.",
        )
    return candidate


def parse_query(raw_query: str) -> dict[str, str]:
    """Parse a query string into a first-value mapping."""
    return {key: values[0] for key, values in parse_qs(raw_query, keep_blank_values=True).items()}


def parse_prompt_command(command_text: str) -> list[str]:
    """Parse a small command string without invoking a shell."""
    arguments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for char in command_text.strip():
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
            else:
                current.append(char)
        elif char in {"'", '"'}:
            quote = char
        elif char.isspace():
            if current:
                arguments.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        arguments.append("".join(current))
    if arguments and arguments[0].casefold() in {"brain.py", "py", "python", "python.exe"}:
        arguments = arguments[1:]
    if arguments and arguments[0].endswith("brain.py"):
        arguments = arguments[1:]
    return arguments


def split_memory_path(query: dict[str, str]) -> tuple[str, str | None]:
    """Resolve a memory domain and optional key from query fields."""
    if query.get("path"):
        return split_dot_path(query["path"])
    return require_query(query, "domain"), query.get("key") or None


def split_memory_payload(body: dict[str, Any]) -> tuple[str, str]:
    """Resolve a memory domain and required key from a JSON body."""
    if body.get("path"):
        domain, key = split_dot_path(str(body["path"]))
        if key is None:
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, "`path` must include an entry key.")
        return domain, key
    return require_value(body, "domain"), require_value(body, "key")


def split_dot_path(path_value: str) -> tuple[str, str | None]:
    """Split domain.key notation at its final separator."""
    normalized = path_value.strip()
    if "." not in normalized:
        return normalized, None
    return tuple(normalized.rsplit(".", 1))


def require_query(query: dict[str, str], key: str) -> str:
    """Return a required non-empty query value."""
    value = query.get(key, "").strip()
    if not value:
        raise ApiRouteError(HTTPStatus.BAD_REQUEST, f"Missing required query parameter `{key}`.")
    return value


def require_value(body: dict[str, Any], key: str) -> str:
    """Return a required non-empty JSON string value."""
    value = str(body.get(key, "")).strip()
    if not value:
        raise ApiRouteError(HTTPStatus.BAD_REQUEST, f"Missing required JSON field `{key}`.")
    return value


def normalize_task_id(task_id: str) -> str:
    """Normalize a rendered backlog task identifier."""
    return task_id.strip().lstrip("#")


def safe_scope(value: str | None, allow_all: bool = True) -> str:
    """Validate a knowledge scope selector."""
    allowed = ALLOWED_SCOPE_VALUES if allow_all else {"global", "local"}
    return safe_choice((value or "all").casefold().strip(), allowed, "scope")


def safe_choice(value: str, allowed_values: set[str], label: str) -> str:
    """Validate and normalize an enum-like string."""
    normalized = value.casefold().strip()
    if normalized not in allowed_values:
        expected = ", ".join(sorted(allowed_values))
        raise ApiRouteError(HTTPStatus.BAD_REQUEST, f"Invalid `{label}`. Expected one of: {expected}.")
    return normalized


def safe_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    """Parse and bounds-check an optional integer."""
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ApiRouteError(HTTPStatus.BAD_REQUEST, "Expected an integer value.") from exc
    if parsed < minimum or parsed > maximum:
        raise ApiRouteError(HTTPStatus.BAD_REQUEST, f"Integer must be between {minimum} and {maximum}.")
    return parsed
