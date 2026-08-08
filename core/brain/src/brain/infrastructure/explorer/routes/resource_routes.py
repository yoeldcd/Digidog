# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Static, image, and wiki resource routes for Brain Explorer."""

import json
import mimetypes
import re
from http import HTTPStatus
from urllib.parse import unquote
from pathlib import Path

from brain.infrastructure.explorer.validation import resolve_registered_workspace_root
from brain.infrastructure.explorer.resources import (
    build_live_wiki_manifest,
    find_documentation_dirs,
    find_wiki_markdown_files,
    resolve_static_file,
    resolve_workspace_image,
    resolve_workspace_picture,
)
from brain.infrastructure.runtime.paths import get_core_root, get_workspace_root
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.runtime.paths import resolve_picture_path

TEXT_CONTENT_TYPE = "text/plain; charset=utf-8"


class ResourceRoutesMixin:
    """Serve validated local resources over HTTP."""

    def _handle_backlog_image(self, method: str, query: dict[str, str]) -> None:
        """Serve a saved backlog image file by task ID."""
        if method != "GET":
            self._send_json(
                status=HTTPStatus.METHOD_NOT_ALLOWED,
                payload={"ok": False, "error": "GET only."},
            )
            return

        task_id = query.get("taskId", "").strip()
        if not task_id:
            self._send_json(status=HTTPStatus.BAD_REQUEST, payload={"ok": False, "error": "Missing taskId."})
            return

        if not re.match(r"^t\d+$", task_id):
            self._send_json(status=HTTPStatus.BAD_REQUEST, payload={"ok": False, "error": "Invalid taskId format."})
            return

        pictures_dir = get_workspace_root() / "$agent" / "pictures"
        found_file = None
        if pictures_dir.exists():
            for f in pictures_dir.iterdir():
                if f.is_file() and f.name.startswith(f"backlog-pic-{task_id}."):
                    found_file = f
                    break

        if not found_file or not found_file.exists():
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": "Image not found."})
            return

        self._send_picture_file(found_file)

    def _handle_workspace_image(self, method: str, query: dict[str, str]) -> None:
        """Serve one validated ``$agent``-relative Markdown image."""
        if method != "GET":
            self._send_json(status=HTTPStatus.METHOD_NOT_ALLOWED, payload={"ok": False, "error": "GET only."})
            return
        try:
            picture_file = resolve_workspace_image(
                workspace_root=get_workspace_root(),
                image_path=query.get("path", ""),
            )
        except ValueError as exc:
            self._send_json(status=HTTPStatus.BAD_REQUEST, payload={"ok": False, "error": str(exc)})
            return
        if not picture_file.is_file():
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": "Image not found."})
            return
        self._send_picture_file(picture_file)

    def _handle_log_image(self, method: str, query: dict[str, str]) -> None:
        """Serve one log attachment from the workspace pictures directory."""
        if method != "GET":
            self._send_json(
                status=HTTPStatus.METHOD_NOT_ALLOWED,
                payload={"ok": False, "error": "GET only."},
            )
            return
        try:
            picture_file = resolve_workspace_picture(
                pictures_dir=get_workspace_root() / "$agent" / "pictures",
                picture_name=query.get("name", ""),
            )
        except ValueError as exc:
            self._send_json(status=HTTPStatus.BAD_REQUEST, payload={"ok": False, "error": str(exc)})
            return
        if not picture_file.is_file():
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": "Image not found."})
            return
        self._send_picture_file(picture_file)

    def _handle_picture_file(self, method: str, query: dict[str, str]) -> None:
        """Serve one active registry image by opaque picture identifier."""
        if method != "GET":
            self._send_json(status=HTTPStatus.METHOD_NOT_ALLOWED, payload={"ok": False, "error": "GET only."})
            return
        picture_id = query.get("id", "").strip()
        record = PictureRepository().get(picture_id=picture_id)
        if record is None or not record.active:
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": "Image not found."})
            return
        try:
            picture_file = resolve_picture_path(
                scope=str(getattr(record, "scope", "local") or "local"),
                relative_path=record.relative_path,
            )
        except ValueError:
            self._send_json(status=HTTPStatus.FORBIDDEN, payload={"ok": False, "error": "Image path is unsafe."})
            return
        if not picture_file.is_file():
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": "Image file is missing."})
            return
        self._send_picture_file(picture_file)

    def _send_picture_file(self, picture_file: Path) -> None:
        """Send an already validated workspace picture file."""
        content_type = mimetypes.guess_type(picture_file.name)[0] or "image/png"
        data = picture_file.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_static(self, path: str) -> None:
        """
        Serve one static file from the configured distribution directory.

        Args:
            path (str): URL path.
        """
        try:
            file_path = resolve_static_file(dist_dir=self.config.dist_dir, request_path=path)
        except ValueError as exc:
            self._send_json(status=HTTPStatus.FORBIDDEN, payload={"ok": False, "error": str(exc)})
            return

        if not file_path.exists() or not file_path.is_file():
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": "Static file not found."})
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or TEXT_CONTENT_TYPE
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_wiki(self, method: str, path: str) -> None:
        """Serve a live project Wiki directly from its Markdown sources."""
        if method != "GET":
            self._send_json(status=HTTPStatus.METHOD_NOT_ALLOWED, payload={"ok": False, "error": "Wikis support GET only."})
            return

        parts = [part for part in path.split("/") if part]
        if len(parts) < 2:
            self._send_json(status=HTTPStatus.BAD_REQUEST, payload={"ok": False, "error": "Invalid wiki path."})
            return

        if len(parts) >= 4 and parts[1] == "workspace":
            try:
                workspace_root = resolve_registered_workspace_root(unquote(parts[2]))
            except ApiRouteError as exc:
                self._send_json(status=exc.status, payload={"ok": False, "error": exc.message})
                return
            wiki_name = unquote(parts[3])
            subpath = "/".join(parts[4:]) if len(parts) > 4 else "wiki/index.html"
        else:
            workspace_root = get_workspace_root()
            wiki_name = unquote(parts[1])
            subpath = "/".join(parts[2:]) if len(parts) > 2 else "wiki/index.html"
        matched_dir = next(
            (directory for directory in find_documentation_dirs(workspace_root) if directory.parent.name == wiki_name),
            None,
        )
        if matched_dir is None or not find_wiki_markdown_files(matched_dir):
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": f"Wiki '{wiki_name}' not found."})
            return

        try:
            data, content_type = self._resolve_live_wiki_resource(matched_dir=matched_dir, subpath=subpath)
        except ValueError as exc:
            self._send_json(status=HTTPStatus.FORBIDDEN, payload={"ok": False, "error": str(exc)})
            return
        except FileNotFoundError:
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": "File not found."})
            return

        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    @staticmethod
    def _resolve_live_wiki_resource(matched_dir: Path, subpath: str) -> tuple[bytes, str]:
        """Resolve one generated-in-memory shell, manifest, runtime asset, or Markdown source."""
        utilities_root = get_core_root() / "utilities" / "documentation_utils"
        if subpath in {"", "wiki", "wiki/", "wiki/index.html"}:
            template = (utilities_root / "wiki.template.html").read_text(encoding="utf-8")
            replacements = {
                "{{TITLE}}": f"Wiki - {matched_dir.parent.name}",
                "{{PAGE_KIND}}": "reader",
                "{{MARKDOWN_SOURCE}}": "",
                "{{MARKED_PATH}}": "scripts/marked.min.js",
                "{{MERMAID_PATH}}": "scripts/mermaid.min.js",
                "{{SVG_PAN_ZOOM_PATH}}": "scripts/svg-pan-zoom.min.js",
                "{{PRISM_CSS_PATH}}": "styles/prism-tomorrow.min.css",
                "{{PRISM_JS_PATH}}": "scripts/prism.min.js",
                "{{PRISM_JS_JS_PATH}}": "scripts/prism-javascript.min.js",
                "{{PRISM_CSS_JS_PATH}}": "scripts/prism-css.min.js",
                "{{PRISM_JSON_JS_PATH}}": "scripts/prism-json.min.js",
                "{{PRISM_PYTHON_JS_PATH}}": "scripts/prism-python.min.js",
                "{{WIKI_CORE_CSS_PATH}}": "styles/wiki-core.css",
                "{{WIKI_CORE_JS_PATH}}": "scripts/wiki-core.js",
            }
            for marker, value in replacements.items():
                template = template.replace(marker, value)
            return template.encode("utf-8"), "text/html; charset=utf-8"

        if subpath == "wiki/data/index.json":
            manifest = build_live_wiki_manifest(matched_dir)
            return json.dumps(manifest, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"

        if subpath.startswith("wiki/scripts/") or subpath.startswith("wiki/styles/"):
            asset_relative = subpath.removeprefix("wiki/scripts/") if subpath.startswith("wiki/scripts/") else subpath.removeprefix("wiki/styles/")
            asset_path = (utilities_root / "lib" / asset_relative).resolve()
            library_root = (utilities_root / "lib").resolve()
            if not asset_path.is_relative_to(library_root):
                raise ValueError("Path traversal detected.")
            if not asset_path.is_file():
                raise FileNotFoundError(asset_path)
            return asset_path.read_bytes(), mimetypes.guess_type(asset_path.name)[0] or TEXT_CONTENT_TYPE

        file_path = (matched_dir / subpath).resolve()
        if not file_path.is_relative_to(matched_dir.resolve()):
            raise ValueError("Path traversal detected.")
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        return file_path.read_bytes(), mimetypes.guess_type(file_path.name)[0] or TEXT_CONTENT_TYPE
