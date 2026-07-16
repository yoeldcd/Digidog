# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Local HTTP server for the Brain Explorer static UI and JSON API."""

from __future__ import annotations

# Standard Libraries Imports
import json
import mimetypes
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Application Modules Imports
from brain.infrastructure.explorer.cli_facade import BrainCliFacade, CliCommandResult
from brain.infrastructure.explorer.contracts import ApiRouteError, BrainExplorerServerConfig
from brain.infrastructure.explorer.resources import find_documentation_dirs, resolve_static_file, resolve_workspace_picture
from brain.infrastructure.explorer.routes.api_routes import ApiRoutesMixin
from brain.infrastructure.explorer.routes.backlog_routes import BacklogRoutesMixin
from brain.infrastructure.explorer.routes.knowledge_routes import KnowledgeRoutesMixin
from brain.infrastructure.explorer.routes.log_routes import LogRoutesMixin
from brain.infrastructure.explorer.routes.memory_routes import MemoryRoutesMixin
from brain.infrastructure.explorer.routes.resource_routes import ResourceRoutesMixin
from brain.infrastructure.explorer.routes.system_routes import SystemRoutesMixin
from brain.infrastructure.explorer.routes.voice_routes import VoiceRoutesMixin
from brain.infrastructure.explorer.validation import (
    normalize_task_id,
    parse_prompt_command,
    parse_query,
    resolve_registered_workspace_root,
    require_query,
    require_value,
    safe_choice,
    safe_int,
    safe_scope,
    split_memory_path,
    split_memory_payload,
)
from brain.infrastructure.runtime.paths import get_brain_explorer_dist_dir, get_workspace_root


MAX_REQUEST_BYTES = 1_048_576
"""Maximum accepted JSON request body size."""

TEXT_CONTENT_TYPE = "text/plain; charset=utf-8"
"""Default static text content type."""

JSON_CONTENT_TYPE = "application/json; charset=utf-8"
"""Default JSON response content type."""

ALLOWED_PROMPTER_COMMANDS = {
    "check-workspace",
    "export-logs",
    "get-context",
    "get-memory-entry",
    "knowledge-deltas",
    "knowledge-export",
    "knowledge-query",
    "knowledge-show",
    "knowledge-status",
    "list-profiles",
    "log-index",
    "memory-structure",
    "query",
    "read-log",
    "read-profile",
    "show-backlog",
    "vectorstore-status",
    "local-vectorstore-status",
}
"""Read-only commands accepted by the Explorer CLI prompter."""


class BrainExplorerRequestHandler(
    ApiRoutesMixin,
    BacklogRoutesMixin,
    KnowledgeRoutesMixin,
    LogRoutesMixin,
    MemoryRoutesMixin,
    ResourceRoutesMixin,
    SystemRoutesMixin,
    VoiceRoutesMixin,
    BaseHTTPRequestHandler,
):
    """Handle static Brain Explorer files and API requests."""

    server_version = "BrainExplorer/1.0"
    config: BrainExplorerServerConfig

    def do_GET(self) -> None:
        """Handle HTTP GET requests."""
        self._handle_request(method="GET")

    def do_POST(self) -> None:
        """Handle HTTP POST requests."""
        self._handle_request(method="POST")

    def do_DELETE(self) -> None:
        """Handle HTTP DELETE requests."""
        self._handle_request(method="DELETE")

    def do_OPTIONS(self) -> None:
        """Handle HTTP OPTIONS preflight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_common_headers()
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """
        Keep the explorer server quiet during normal local use.

        Args:
            format (str): Log message format.
            *args (Any): Message format values.
        """
        return

    def _handle_request(self, method: str) -> None:
        """
        Dispatch one HTTP request.

        Args:
            method (str): HTTP method name.
        """
        requested_root = self.headers.get("X-Workspace-Root") or self.config.facade.workspace_root
        try:
            workspace_root = resolve_registered_workspace_root(requested_root=requested_root)
        except ApiRouteError as exc:
            self._send_json(status=exc.status, payload={"ok": False, "error": exc.message})
            return
        with self.config.facade.workspace_context(workspace_root):
            self._handle_request_locked(method=method)

    def _handle_request_locked(self, method: str) -> None:
        """Dispatch one request while process-global workspace context is isolated."""
        parsed_url = urlparse(self.path)
        if parsed_url.path.startswith("/api/"):
            if parsed_url.path == "/api/voice/latest" or parsed_url.path.startswith("/api/voice/messages/"):
                self._handle_voice_audio(method=method, path=parsed_url.path)
                return
            if parsed_url.path == "/api/backlog/image":
                self._handle_backlog_image(method=method, query=parse_query(parsed_url.query))
                return
            if parsed_url.path == "/api/logs/image":
                self._handle_log_image(method=method, query=parse_query(parsed_url.query))
                return
            self._handle_api(method=method, path=parsed_url.path, query=parse_query(parsed_url.query))
            return
        if parsed_url.path.startswith("/wiki/"):
            self._handle_wiki(method=method, path=parsed_url.path)
            return
        if method != "GET":
            self._send_json(
                status=HTTPStatus.METHOD_NOT_ALLOWED,
                payload={"ok": False, "error": "Static files support GET only."},
            )
            return
        self._handle_static(path=parsed_url.path)



























    def _read_json_body(self) -> dict[str, Any]:
        """
        Read and parse a bounded JSON request body.

        Returns:
            dict[str, Any]: Parsed JSON object.
        """
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > MAX_REQUEST_BYTES:
            raise ApiRouteError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large.")
        if content_length <= 0:
            return {}
        body_bytes = self.rfile.read(content_length)
        try:
            parsed_body = json.loads(body_bytes.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, f"Invalid JSON body: {exc.msg}") from exc
        if not isinstance(parsed_body, dict):
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, "JSON body must be an object.")
        return parsed_body

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        """
        Send a JSON response.

        Args:
            status (HTTPStatus): HTTP response status.
            payload (dict[str, Any]): JSON-safe response payload.
        """
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Type", JSON_CONTENT_TYPE)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_common_headers(self) -> None:
        """Send headers shared by API and static responses."""
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Workspace-Root")


def serve_brain_explorer(host: str = "127.0.0.1", port: int = 8127, api_timeout: float = 30.0) -> None:
    """
    Serve the Brain Explorer static application and local API.

    Args:
        host (str): Host interface to bind.
        port (int): TCP port to bind.
        api_timeout (float): Maximum delegated CLI duration in seconds.
    """
    config = create_server_config(host=host, port=port, api_timeout=api_timeout)
    handler_class = create_request_handler(config=config)
    server = ThreadingHTTPServer((config.host, config.port), handler_class)
    print(f"Brain Explorer listening at http://{config.host}:{config.port}/")
    print(f"Serving static assets from {config.dist_dir.as_posix()}")
    server.serve_forever()


def create_server_config(host: str, port: int, api_timeout: float) -> BrainExplorerServerConfig:
    """
    Create the default Explorer server configuration.

    Args:
        host (str): Host interface to bind.
        port (int): TCP port to bind.
        api_timeout (float): Maximum delegated CLI duration in seconds.

    Returns:
        BrainExplorerServerConfig: Server configuration.
    """
    dist_dir = get_brain_explorer_dist_dir()
    facade = BrainCliFacade(timeout=api_timeout)
    return BrainExplorerServerConfig(
        host=host,
        port=port,
        dist_dir=dist_dir.resolve(),
        api_timeout=api_timeout,
        facade=facade,
    )


def create_request_handler(config: BrainExplorerServerConfig) -> type[BrainExplorerRequestHandler]:
    """
    Build a request handler class bound to one server configuration.

    Args:
        config (BrainExplorerServerConfig): Server configuration.

    Returns:
        type[BrainExplorerRequestHandler]: Configured request handler class.
    """

    class ConfiguredBrainExplorerRequestHandler(BrainExplorerRequestHandler):
        """Request handler with captured server configuration."""

        pass

    ConfiguredBrainExplorerRequestHandler.config = config
    return ConfiguredBrainExplorerRequestHandler
