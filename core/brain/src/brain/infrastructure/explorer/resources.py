# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Safe filesystem resolution for Brain Explorer resources."""

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

PICTURE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.(?:png|jpe?g|gif|webp)$", re.IGNORECASE)
WORKSPACE_IMAGE_SUFFIXES = frozenset({".gif", ".jpeg", ".jpg", ".png", ".webp"})
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:/")
LOCAL_FILE_URL_PREFIX = "file:///"


def resolve_static_file(dist_dir: Path, request_path: str) -> Path:
    """Resolve a URL path beneath the Explorer distribution root.

    Args:
        dist_dir (Path): Static distribution root.
        request_path (str): URL path requested by the client.

    Returns:
        Path: Validated static file path.

    Raises:
        ValueError: The path escapes the distribution root.
    """
    relative = unquote(request_path.split("?", 1)[0]).lstrip("/") or "index.html"
    if relative.endswith("/"):
        relative = f"{relative}index.html"
    safe_root = dist_dir.resolve()
    candidate = (safe_root / relative).resolve()
    try:
        candidate.relative_to(safe_root)
    except ValueError as exc:
        raise ValueError("Static path escapes the Explorer distribution directory.") from exc
    return candidate


def resolve_workspace_picture(pictures_dir: Path, picture_name: str) -> Path:
    """Resolve a validated image filename beneath a pictures directory.

    Args:
        pictures_dir (Path): Workspace picture root.
        picture_name (str): Requested relative picture name.

    Returns:
        Path: Validated picture path.

    Raises:
        ValueError: The name is invalid or escapes the picture root.
    """
    normalized = str(picture_name or "").strip()
    if not PICTURE_NAME_RE.fullmatch(normalized):
        raise ValueError("Invalid image name.")
    safe_root = pictures_dir.resolve()
    candidate = (safe_root / normalized).resolve()
    try:
        candidate.relative_to(safe_root)
    except ValueError as exc:
        raise ValueError("Image path escapes the workspace pictures directory.") from exc
    return candidate


def resolve_workspace_image(workspace_root: Path, image_path: str) -> Path:
    """Resolve a supported workspace-relative or absolute local image.

    Args:
        workspace_root (Path): Active, already-validated workspace root.
        image_path (str): ``$agent`` reference, local ``file:///`` URL, or
            absolute local image path supplied by the Explorer client.

    Returns:
        Path: Canonical validated image path. Absolute local references may
            reside outside the active workspace.

    Raises:
        ValueError: The reference is malformed, network-based, non-image, or
            violates the containment required for ``$agent`` references.
    """
    normalized = unquote(str(image_path or "").strip()).replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]

    safe_root = workspace_root.resolve()
    is_workspace_relative = False
    is_absolute_local_reference = False

    if normalized.startswith("$agent/"):
        candidate_path = safe_root / normalized
        is_workspace_relative = True
    elif normalized.casefold().startswith(LOCAL_FILE_URL_PREFIX):
        parsed_url = urlsplit(normalized)
        if parsed_url.netloc:
            raise ValueError("Network image paths are not supported.")

        file_path = unquote(parsed_url.path).replace("\\", "/")
        if WINDOWS_ABSOLUTE_PATH_RE.match(file_path.lstrip("/")):
            file_path = file_path[1:]
        if file_path.startswith("//"):
            raise ValueError("Network image paths are not supported.")

        candidate_path = Path(file_path)
        is_absolute_local_reference = True
    elif normalized.startswith("//"):
        raise ValueError("Network image paths are not supported.")
    elif Path(normalized).is_absolute() or WINDOWS_ABSOLUTE_PATH_RE.match(normalized):
        candidate_path = Path(normalized)
        is_absolute_local_reference = True
    else:
        raise ValueError("Images must use a $agent reference or an absolute local path.")

    try:
        candidate = candidate_path.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError("Local image path is invalid.") from exc

    if is_workspace_relative:
        try:
            candidate.relative_to(safe_root)
        except ValueError as exc:
            raise ValueError("Image path escapes the active workspace.") from exc

    if candidate.suffix.lower() not in WORKSPACE_IMAGE_SUFFIXES:
        raise ValueError("Unsupported local image type.")
    if is_absolute_local_reference and not candidate.is_file():
        raise ValueError("Local image is missing or is not a regular file.")

    return candidate


def find_wiki_markdown_files(documentation_dir: Path) -> list[Path]:
    """Return live Markdown sources beneath one documentation directory."""
    if not documentation_dir.is_dir():
        return []
    return sorted(
        (
            path
            for path in documentation_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".md", ".markdown"}
            and "wiki" not in path.relative_to(documentation_dir).parts
        ),
        key=lambda path: path.relative_to(documentation_dir).as_posix().lower(),
    )


def build_live_wiki_manifest(documentation_dir: Path) -> dict[str, object]:
    """Build the Wiki runtime manifest directly from current Markdown files."""
    presets = {
        "readme": ("Home", "\U0001F3E0"),
        "readme.es": ("Inicio", "\U0001F3E0"),
        "index": ("Home", "\U0001F3E0"),
        "architecture": ("Architecture Blueprint", "\U0001F3D7\uFE0F"),
        "design": ("Design & Theme", "\U0001F3A8"),
        "interface": ("UI Component Catalog", "\U0001F5A5\uFE0F"),
        "changelog": ("Changelog History", "\U0001F4DC"),
        "backlog": ("Project Backlog", "\U0001F4CB"),
        "api": ("API Specification", "\U0001F4D6"),
        "deployment": ("Deployment Guide", "\U0001F680"),
        "security": ("Security Model", "\U0001F512"),
    }
    pages: list[dict[str, str]] = []
    for markdown_path in find_wiki_markdown_files(documentation_dir):
        source = markdown_path.relative_to(documentation_dir).as_posix()
        page_id = re.sub(r"\.(?:md|markdown)$", "", source, flags=re.IGNORECASE).lower()
        basename = markdown_path.stem.lower()
        preset = presets.get(page_id) or presets.get(basename)
        content = markdown_path.read_text(encoding="utf-8")
        heading = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
        title = preset[0] if preset else (heading.group(1).strip() if heading else markdown_path.stem.replace("_", " ").replace("-", " ").title())
        icon = preset[1] if preset else "\U0001F4C4"
        pages.append({"id": page_id, "title": title, "icon": icon, "source": source, "sourceHref": f"../{source}"})
    return {
        "version": 2,
        "projectName": documentation_dir.parent.name,
        "pages": pages,
        "headings": [],
        "virtualPages": [],
    }


def find_documentation_dirs(workspace_root: Path) -> list[Path]:
    """Find documentation roots while pruning generated and heavy folders.

    Args:
        workspace_root (Path): Workspace to inspect.

    Returns:
        list[Path]: Stable documentation directories available to Explorer.
    """
    skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".tmp", ".agents", "pictures", "database"}
    if not workspace_root.exists():
        return []
    documentation_dirs: list[Path] = []
    for root, dirs, _ in os.walk(workspace_root.resolve()):
        dirs[:] = [name for name in dirs if name not in skip_dirs]
        if "documentation" in dirs:
            documentation_dirs.append(Path(root) / "documentation")
    return documentation_dirs
