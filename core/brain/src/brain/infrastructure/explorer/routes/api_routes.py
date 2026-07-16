# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""ApiRoutesMixin for Brain Explorer."""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any

from brain.infrastructure.explorer.cli_facade import CliCommandResult
from brain.infrastructure.explorer.contracts import ApiRouteError
from brain.infrastructure.explorer.resources import find_documentation_dirs
from brain.infrastructure.explorer.validation import (
    normalize_task_id, parse_prompt_command, require_query, require_value,
    safe_choice, safe_int, safe_scope, split_memory_path, split_memory_payload,
)
from brain.infrastructure.runtime.paths import get_agent_home, get_workspace_root


class ApiRoutesMixin:
    """Provide one cohesive group of Explorer routes."""

    def _handle_api(self, method: str, path: str, query: dict[str, str]) -> None:
        """
        Dispatch one API request.

        Args:
            method (str): HTTP method name.
            path (str): Parsed request path.
            query (dict[str, str]): First-value query mapping.
        """
        try:
            payload = self._route_api(method=method, path=path, query=query)
            self._send_json(status=HTTPStatus.OK, payload=payload)
        except ApiRouteError as exc:
            self._send_json(status=exc.status, payload={"ok": False, "error": exc.message})
        except Exception as exc:
            self._send_json(status=HTTPStatus.INTERNAL_SERVER_ERROR, payload={"ok": False, "error": str(exc)})

    def _route_api(self, method: str, path: str, query: dict[str, str]) -> dict[str, Any]:
        """
        Resolve and execute an API route.

        Args:
            method (str): HTTP method name.
            path (str): Parsed request path.
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: JSON response payload.
        """
        if method == "GET" and path == "/api/health":
            return self._health_payload()
        if method == "GET" and path == "/api/projects":
            return self._projects_list()
        if method == "GET" and path == "/api/wikis":
            return self._wikis_list()
        if method == "GET" and path == "/api/voice/messages":
            return self._voice_messages()
        if method == "POST" and path == "/api/voice/replay":
            return self._voice_replay()
        if method == "POST" and path == "/api/voice/pause":
            return self._voice_pause()
        if method == "GET" and path == "/api/context":
            return self._run_cli(["get-context", "--json"]).to_payload()
        if method == "POST" and path == "/api/cli":
            return self._cli_prompt().to_payload()
        if path == "/api/memory/tree" and method == "GET":
            return self._run_cli(["memory-structure", "--json"]).to_payload()
        if path == "/api/memory/entry":
            return self._memory_entry(method=method, query=query)
        if path == "/api/memory/domain":
            return self._memory_domain(method=method, query=query)
        if path == "/api/knowledge/status" and method == "GET":
            return self._knowledge_status(query=query)
        if path == "/api/knowledge/show" and method == "GET":
            return self._knowledge_show(query=query)
        if path == "/api/knowledge/query" and method == "GET":
            return self._knowledge_query(query=query)
        if path == "/api/knowledge/export" and method == "GET":
            return self._knowledge_export(query=query)
        if path == "/api/knowledge/deltas":
            return self._knowledge_deltas(method=method, query=query)
        if path == "/api/query" and method == "GET":
            return self._global_query(query=query)
        if path == "/api/profiles" and method == "GET":
            return self._run_cli(["list-profiles", "--json"]).to_payload()
        if path == "/api/profiles/read" and method == "GET":
            return self._profile_read(query=query)
        if path == "/api/logs/index" and method == "GET":
            return self._log_index(query=query)
        if path == "/api/logs" and method == "GET":
            return self._logs(query=query)
        if path == "/api/backlog" and method == "GET":
            return self._backlog(query=query)
        if path == "/api/backlog/task" and method == "POST":
            return self._backlog_task()
        raise ApiRouteError(HTTPStatus.NOT_FOUND, f"Unknown API route `{path}`.")

    def _run_cli(
        self,
        arguments: list[str],
        stdin_text: str | None = None,
        expect_json: bool = True,
    ) -> CliCommandResult:
        """
        Execute one delegated CLI command.

        Args:
            arguments (list[str]): Safe command arguments.
            stdin_text (str | None): Optional stdin payload.
            expect_json (bool): Whether to parse stdout as JSON.

        Returns:
            CliCommandResult: Captured CLI result.
        """
        return self.config.facade.run(
            arguments=arguments,
            stdin_text=stdin_text,
            expect_json=expect_json,
            workspace_root=getattr(self, "request_workspace_root", None),
        )
