# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Safe filesystem resolution for Brain Explorer resources."""

import os
import re
from pathlib import Path
from urllib.parse import unquote

PICTURE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.(?:png|jpe?g|gif|webp)$", re.IGNORECASE)


def resolve_static_file(dist_dir: Path, request_path: str) -> Path:
    """Resolve a URL path beneath the Explorer distribution root."""
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
    """Resolve a validated image filename beneath a pictures directory."""
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


def find_documentation_dirs(workspace_root: Path) -> list[Path]:
    """Find documentation roots while pruning generated and heavy folders."""
    skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".tmp", ".agents", "pictures", "database"}
    if not workspace_root.exists():
        return []
    documentation_dirs: list[Path] = []
    for root, dirs, _ in os.walk(workspace_root.resolve()):
        dirs[:] = [name for name in dirs if name not in skip_dirs]
        if "documentation" in dirs:
            documentation_dirs.append(Path(root) / "documentation")
    return documentation_dirs
