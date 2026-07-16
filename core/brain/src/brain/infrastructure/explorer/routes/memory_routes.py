# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""MemoryRoutesMixin for Brain Explorer."""

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

ALLOWED_PROMPTER_COMMANDS = {
    "check-workspace", "export-logs", "get-context", "get-memory-entry",
    "knowledge-deltas", "knowledge-export", "knowledge-query", "knowledge-show",
    "knowledge-status", "list-profiles", "log-index", "memory-structure",
    "query", "read-log", "read-profile", "show-backlog", "vectorstore-status",
    "local-vectorstore-status",
}


class MemoryRoutesMixin:
    """Provide one cohesive group of Explorer routes."""

    def _profile_read(self, query: dict[str, str]) -> dict[str, Any]:
        """
        Read one profile through the CLI facade.

        Args:
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        name = require_query(query=query, key="name")
        return self._run_cli(["read-profile", name, "--json"]).to_payload()

    def _cli_prompt(self) -> CliCommandResult:
        """
        Execute one read-only command submitted by the Explorer prompter.

        Returns:
            CliCommandResult: Captured CLI result.
        """
        body = self._read_json_body()
        command_text = require_value(body=body, key="command")
        arguments = parse_prompt_command(command_text)
        if not arguments:
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, "Command cannot be empty.")
        command_name = arguments[0]
        if command_name not in ALLOWED_PROMPTER_COMMANDS:
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, f"Command `{command_name}` is not enabled in Explorer.")
        expect_json = "--json" in arguments
        return self._run_cli(arguments, expect_json=expect_json)

    def _memory_entry(self, method: str, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute memory entry read, write, or delete.

        Args:
            method (str): HTTP method name.
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        if method == "GET":
            domain, key = split_memory_path(query=query)
            arguments = ["get-memory-entry", domain, "--json"]
            if key:
                arguments.insert(2, key)
            return self._run_cli(arguments).to_payload()

        if method == "POST":
            body = self._read_json_body()
            domain, key = split_memory_payload(body=body)
            content = str(body.get("content", ""))
            return self._run_cli(["set-memory-entry", domain, key, "-", "--json"], stdin_text=content).to_payload()

        if method == "DELETE":
            domain, key = split_memory_path(query=query)
            if not key:
                raise ApiRouteError(HTTPStatus.BAD_REQUEST, "Deleting an entry requires `key` or `path`.")
            return self._run_cli(["delete-memory-entry", domain, key, "--json"]).to_payload()

        raise ApiRouteError(HTTPStatus.METHOD_NOT_ALLOWED, "Memory entry supports GET, POST, and DELETE.")

    def _memory_domain(self, method: str, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute memory domain creation or deletion.

        Args:
            method (str): HTTP method name.
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        if method == "POST":
            body = self._read_json_body()
            domain = require_value(body=body, key="domain")
            return self._run_cli(["add-memory-domain", domain, "--json"]).to_payload()
        if method == "DELETE":
            domain = require_query(query=query, key="domain")
            confirmation = query.get("confirm", domain)
            return self._run_cli(["delete-memory-entry", domain, "--confirm", confirmation, "--json"]).to_payload()
        raise ApiRouteError(HTTPStatus.METHOD_NOT_ALLOWED, "Memory domain supports POST and DELETE.")
