# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""KnowledgeRoutesMixin for Brain Explorer."""

from __future__ import annotations

import json
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
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
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
        scope = safe_scope(query.get("scope", "global"))
        limit = safe_int(query.get("limit"), default=10, minimum=1, maximum=100)
        status = query.get("status", "pending")
        if scope == "all":
            if method != "GET":
                raise ApiRouteError(
                    HTTPStatus.BAD_REQUEST,
                    "Applying knowledge deltas requires an explicit global or local scope.",
                )
            return self._knowledge_deltas_all_scopes(limit=limit, status=status)
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

    def _knowledge_dream(self) -> dict[str, Any]:
        """Generate selected container deltas and optionally prune their prior graph assertions."""
        body = self._read_json_body()
        action = safe_choice(str(body.get("action") or "consolidate"), {"consolidate", "recompose"}, "action")
        scope = safe_scope(str(body.get("scope") or "global"), allow_all=False)
        domain = safe_choice(
            str(body.get("domain") or "all"),
            {"all", "memory", "diary", "profiles", "logs", "messages"},
            "domain",
        )
        raw_source_paths = body.get("sourcePaths")
        source_paths = [
            str(path).replace("\\", "/").strip()
            for path in raw_source_paths
            if isinstance(path, str) and path.strip()
        ] if isinstance(raw_source_paths, list) else []
        limit = safe_int(str(body.get("limit") or "") or None, default=max(len(source_paths), 20), minimum=1, maximum=200)
        arguments = ["dream", "--scope", scope, "--domain", domain, "--limit", str(limit), "--force", "--json"]
        for source_path in sorted(set(source_paths)):
            arguments.extend(["--source-path", source_path])
        result = self._run_cli(arguments).to_payload()
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        dream = data.get("dream") if isinstance(data.get("dream"), dict) else {}
        proposed_count = int(dream.get("deltas_proposed") or 0)
        recompose_paths = source_paths or [
            str(row.get("source_path") or "")
            for row in data.get("pending_deltas", [])
            if isinstance(row, dict) and row.get("source_path")
        ]
        if action == "recompose" and bool(result.get("ok")) and bool(data.get("ok")) and proposed_count > 0:
            data["recompose"] = KnowledgeRepository(scope=scope).recompose_source_paths(recompose_paths)
            data["recompose"]["status"] = "pruned_after_generation"
        else:
            data["recompose"] = {"status": "not_requested" if action == "consolidate" else "generation_not_ready"}
        data["action"] = action
        data["selected_source_paths"] = sorted(set(source_paths))
        result["data"] = data
        return result

    def _knowledge_deltas_all_scopes(self, limit: int, status: str) -> dict[str, Any]:
        """Review global and local delta buffers through one Explorer request."""
        scope_payloads: dict[str, dict[str, Any]] = {}
        review_rows: list[dict[str, Any]] = []
        candidate_ids: list[int] = []
        blocked_ids: list[int] = []
        duration_ms = 0
        queue_ms = 0
        execution_ms = 0
        successful = True
        for physical_scope in ("global", "local"):
            result = self._run_cli(
                [
                    "knowledge-deltas", "--scope", physical_scope,
                    "--limit", str(limit), "--status", status, "--json",
                ],
            ).to_payload()
            scope_payloads[physical_scope] = result
            successful = successful and bool(result.get("ok"))
            duration_ms += int(result.get("durationMs") or 0)
            queue_ms += int(result.get("queueMs") or 0)
            execution_ms += int(result.get("executionMs") or 0)
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            for row in data.get("review_rows", []):
                if isinstance(row, dict):
                    review_rows.append({**row, "scope": physical_scope})
            candidate_ids.extend(int(value) for value in data.get("candidate_ids", []) if str(value).isdigit())
            blocked_ids.extend(int(value) for value in data.get("blocked_ids", []) if str(value).isdigit())

        data = {
            "ok": successful,
            "scope": "all",
            "review_rows": review_rows,
            "candidate_ids": candidate_ids,
            "blocked_ids": blocked_ids,
            "scopes": {scope: payload.get("data", {}) for scope, payload in scope_payloads.items()},
        }
        return {
            "ok": successful,
            "command": ["knowledge-deltas", "--scope", "all", "--limit", str(limit), "--status", status, "--json"],
            "code": 0 if successful else 1,
            "stdout": json.dumps(data, ensure_ascii=False),
            "stderr": "\n".join(
                str(payload.get("stderr") or "")
                for payload in scope_payloads.values()
                if payload.get("stderr")
            ),
            "durationMs": duration_ms,
            "queueMs": queue_ms,
            "executionMs": execution_ms,
            "data": data,
        }

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
        source = safe_choice(query.get("source", "all"), {"all", "memory", "knowledge", "messages", "pictures", "diary", "logs", "policies"}, "source")
        mechanism = safe_choice(query.get("mechanism", "all"), {"all", "graph", "vector", "text"}, "mechanism")
        knowledge_scope = safe_scope(query.get("knowledgeScope", "all"))
        page = safe_int(query.get("page"), default=1, minimum=1, maximum=1_000_000)
        page_size = safe_int(query.get("pageSize"), default=25, minimum=0, maximum=100)
        if page_size not in {0, 10, 25, 50, 100}:
            raise ValueError("pageSize must be one of: 0, 10, 25, 50, 100")

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
                "--page",
                str(page),
                "--page-size",
                str(page_size),
                "--json",
                "--verbose-schema",
            ],
        )
        if query.get("deep") == "true":
            arguments.append("--deep")
        if query.get("explain") == "true":
            arguments.append("--explain")
        return self._run_cli(arguments).to_payload()
