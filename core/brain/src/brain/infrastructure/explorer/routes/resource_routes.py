# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Static, image, and wiki resource routes for Brain Explorer."""

import mimetypes
import re
from http import HTTPStatus
from pathlib import Path

from brain.infrastructure.explorer.resources import find_documentation_dirs, resolve_static_file, resolve_workspace_picture
from brain.infrastructure.runtime.paths import get_workspace_root

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
        """
        Serve documentation files statically from subproject documentation folders.
        Replicates the native serve behavior: the entire documentation/ directory
        is the static root, so wiki/index.html fetches .md files via relative paths.
        URL format: /wiki/<wiki_name>/<file_path>
        """
        if method != "GET":
            self._send_json(status=HTTPStatus.METHOD_NOT_ALLOWED, payload={"ok": False, "error": "Wikis support GET only."})
            return

        parts = [p for p in path.split("/") if p]
        if len(parts) < 2:
            self._send_json(status=HTTPStatus.BAD_REQUEST, payload={"ok": False, "error": "Invalid wiki path."})
            return

        wiki_name = parts[1]
        subpath = "/".join(parts[2:]) if len(parts) > 2 else "wiki/index.html"
        if not subpath:
            subpath = "wiki/index.html"

        workspace_root = get_workspace_root()
        doc_dirs = find_documentation_dirs(workspace_root)
        matched_dir = None
        for d in doc_dirs:
            if d.parent.name == wiki_name:
                matched_dir = d
                break

        if not matched_dir:
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": f"Wiki '{wiki_name}' not found."})
            return

        # Serve from documentation/ root, same as native serve
        try:
            file_path = (matched_dir / subpath).resolve()
            if not file_path.is_relative_to(matched_dir.resolve()):
                raise ValueError("Path traversal detected.")
        except Exception as exc:
            self._send_json(status=HTTPStatus.FORBIDDEN, payload={"ok": False, "error": str(exc)})
            return

        if not file_path.exists() or not file_path.is_file():
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"ok": False, "error": "File not found."})
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or TEXT_CONTENT_TYPE
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
