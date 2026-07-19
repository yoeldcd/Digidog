# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""KnowledgeRoutesMixin for Brain Explorer."""

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


class KnowledgeRoutesMixin:
    """Provide one cohesive group of Explorer routes."""

    def _knowledge_status(self, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute `knowledge-status`.

        Args:
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        scope = safe_scope(query.get("scope", "all"))
        return self._run_cli(["knowledge-status", "--scope", scope, "--json"]).to_payload()

    def _knowledge_show(self, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute `knowledge-show`.

        Args:
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        scope = safe_scope(query.get("scope", "all"))
        arguments = ["knowledge-show", "--scope", scope, "--json"]
        entity = query.get("entity")
        mode = query.get("mode")
        filter_value = query.get("filter")
        if entity:
            arguments.insert(1, entity)
        if mode == "all":
            arguments.extend(["--entities", "--relations", "--classes"])
        elif mode in {"entities", "classes"}:
            arguments.extend([f"--{mode}", "--relations"])
        elif mode == "relations":
            arguments.append(f"--{mode}")
        if filter_value:
            arguments.extend(["--filter", filter_value])
        return self._run_cli(arguments).to_payload()

    def _knowledge_query(self, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute `knowledge-query`.

        Args:
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        text = require_query(query=query, key="q")
        scope = safe_scope(query.get("scope", "all"))
        limit = safe_int(query.get("limit"), default=10, minimum=1, maximum=100)
        arguments = ["knowledge-query", text, "--scope", scope, "--limit", str(limit), "--json"]
        if query.get("hybrid") == "true":
            arguments.append("--hybrid")
        if query.get("explain") == "true":
            arguments.append("--explain")
        return self._run_cli(arguments).to_payload()

    def _knowledge_export(self, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute `knowledge-export`.

        Args:
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        scope = safe_scope(query.get("scope", "all"))
        return self._run_cli(["knowledge-export", "--scope", scope, "--json"]).to_payload()

    def _knowledge_deltas(self, method: str, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute knowledge delta review or application.

        Args:
            method (str): HTTP method name.
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        scope = safe_scope(query.get("scope", "global"), allow_all=False)
        limit = safe_int(query.get("limit"), default=10, minimum=1, maximum=100)
        status = query.get("status", "pending")
        arguments = ["knowledge-deltas", "--scope", scope, "--limit", str(limit), "--status", status, "--json"]
        if query.get("id"):
            arguments.extend(["--id", str(safe_int(query.get("id"), default=0, minimum=1, maximum=10_000_000))])
        if method == "POST":
            body = self._read_json_body()
            if body.get("apply") is True:
                arguments.append("--yes")
        if method not in {"GET", "POST"}:
            raise ApiRouteError(HTTPStatus.METHOD_NOT_ALLOWED, "Knowledge deltas supports GET and POST.")
        return self._run_cli(arguments).to_payload()

    def _global_query(self, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute the global `query` command.

        Args:
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        text = require_query(query=query, key="q")
        domain = query.get("domain")
        source = safe_choice(query.get("source", "all"), {"all", "memory", "knowledge", "messages"}, "source")
        mechanism = safe_choice(query.get("mechanism", "all"), {"all", "graph", "vector", "text"}, "mechanism")
        knowledge_scope = safe_scope(query.get("knowledgeScope", "all"))
        limit = safe_int(query.get("limit"), default=5, minimum=1, maximum=100)
        arguments = ["query"]
        if domain:
            arguments.extend([domain, text])
        else:
            arguments.append(text)
        arguments.extend(
            [
                "--source",
                source,
                "--mechanism",
                mechanism,
                "--knowledge-scope",
                knowledge_scope,
                "--limit",
                str(limit),
                "--json",
            ],
        )
        if query.get("deep") == "true":
            arguments.append("--deep")
        if query.get("explain") == "true":
            arguments.append("--explain")
        return self._run_cli(arguments).to_payload()
