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
        match (method, path):
            case ("GET", "/api/health"):
                return self._health_payload()
            case ("GET", "/api/projects"):
                return self._projects_list()
            case ("GET", "/api/wikis"):
                return self._wikis_list()
            case ("GET", "/api/voice/messages"):
                return self._voice_messages(query=query)
            case ("POST", "/api/voice/session/name"):
                return self._voice_session_name()
            case ("GET", "/api/voice/status"):
                return self._voice_status()
            case ("POST", "/api/voice/replay"):
                return self._voice_replay()
            case ("POST", "/api/voice/pause"):
                return self._voice_pause()
            case ("POST", "/api/voice/synthesize"):
                return self._voice_synthesize()
            case ("GET", "/api/context"):
                return self._run_cli(["get-context", "--json"]).to_payload()
            case ("POST", "/api/cli"):
                return self._cli_prompt().to_payload()
            case ("GET", "/api/memory/tree"):
                return self._run_cli(["memory-structure", "--json"]).to_payload()
            case (_, "/api/memory/entry"):
                return self._memory_entry(method=method, query=query)
            case (_, "/api/memory/domain"):
                return self._memory_domain(method=method, query=query)
            case ("GET", "/api/knowledge/status"):
                return self._knowledge_status(query=query)
            case ("GET", "/api/knowledge/show"):
                return self._knowledge_show(query=query)
            case ("GET", "/api/knowledge/query"):
                return self._knowledge_query(query=query)
            case ("GET", "/api/knowledge/export"):
                return self._knowledge_export(query=query)
            case (_, "/api/knowledge/deltas"):
                return self._knowledge_deltas(method=method, query=query)
            case ("POST", "/api/knowledge/dream"):
                return self._knowledge_dream()
            case ("GET", "/api/query"):
                return self._global_query(query=query)
            case ("GET", "/api/pictures"):
                return self._pictures(query=query)
            case ("POST", "/api/pictures/description"):
                return self._describe_picture()
            case ("POST", "/api/pictures/import"):
                return self._import_picture(query=query)
            case ("GET", "/api/profiles"):
                return self._run_cli(["list-profiles", "--json"]).to_payload()
            case ("GET", "/api/profiles/read"):
                return self._profile_read(query=query)
            case ("GET", "/api/logs/index"):
                return self._log_index(query=query)
            case ("GET", "/api/logs"):
                return self._logs(query=query)
            case ("POST", "/api/logs/domain"):
                return self._rename_log_domain()
            case ("GET", "/api/backlog"):
                return self._backlog(query=query)
            case ("POST", "/api/backlog/task"):
                return self._backlog_task()
            case ("POST", "/api/backlog/domain"):
                return self._rename_backlog_domain()
            case _:
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
