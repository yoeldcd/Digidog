# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""BacklogRoutesMixin for Brain Explorer."""

from __future__ import annotations

import re
from http import HTTPStatus
from pathlib import Path
from typing import Any

from brain.application.backlog.enrichment import TaskEnrichmentError, enrich_backlog_draft, enrich_backlog_task
from brain.application.backlog.models import BacklogTask
from brain.infrastructure.explorer.cli_facade import CliCommandResult
from brain.infrastructure.explorer.contracts import ApiRouteError
from brain.infrastructure.explorer.resources import find_documentation_dirs
from brain.infrastructure.explorer.validation import (
    normalize_task_id, parse_prompt_command, require_query, require_value,
    safe_choice, safe_int, safe_scope, split_memory_path, split_memory_payload,
)
from brain.infrastructure.runtime.paths import get_agent_home, get_workspace_root


class BacklogRoutesMixin:
    """Provide one cohesive group of Explorer routes."""

    def _backlog(self, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute `show-backlog` for domain tree navigation.

        Args:
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        arguments = ["show-backlog", "--all"]
        domain = query.get("domain")
        if domain:
            arguments.append(domain)
        arguments.append("--json")
        payload = self._run_cli(arguments, expect_json=True).to_payload()

        has_images = []
        import re
        pictures_dir = get_workspace_root() / "$agent" / "pictures"
        if pictures_dir.exists():
            for f in pictures_dir.iterdir():
                if f.is_file() and f.name.startswith("backlog-pic-"):
                    match = re.match(r"^backlog-pic-(t\d+)\.", f.name)
                    if match:
                        has_images.append(match.group(1))
        payload["hasImages"] = has_images
        return payload

    def _backlog_task(self) -> dict[str, Any]:
        """
        Execute a bounded backlog mutation through explicit actions.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        body = self._read_json_body()
        action = safe_choice(
            str(body.get("action", "")),
            {"add", "delete", "finish", "working", "done", "todo", "edit", "enrich", "enrich-draft"},
            "action",
        )
        if action == "enrich-draft":
            raw_task_id = str(body.get("taskId", "")).strip()
            task_id = normalize_task_id(raw_task_id) if raw_task_id else "draft"
            priority = safe_choice(str(body.get("priority", "HIGH")), {"high", "medium", "low"}, "priority").upper()
            draft = BacklogTask(
                task_id=task_id,
                domain=require_value(body=body, key="domain"),
                title=require_value(body=body, key="title"),
                description=require_value(body=body, key="description"),
                priority=priority,
                status="DRAFT",
            )
            image_data = body.get("image") if isinstance(body.get("image"), str) else None
            try:
                enrichment = enrich_backlog_draft(
                    task=draft,
                    image_data_url=image_data,
                    image_path=None if image_data or task_id == "draft" else self._find_backlog_image(task_id=task_id),
                )
            except (TaskEnrichmentError, ValueError) as exc:
                raise ApiRouteError(HTTPStatus.BAD_GATEWAY, str(exc)) from exc
            return {
                "ok": True,
                "command": "enrich-task-draft",
                "data": {
                    "description": enrichment.description,
                    "enrichment": {
                        "profile": enrichment.profile,
                        "guidelineCount": enrichment.guideline_count,
                        "usedImage": enrichment.used_image,
                        "model": enrichment.model,
                    },
                },
            }
        if action == "enrich":
            task_id = normalize_task_id(require_value(body=body, key="taskId"))
            try:
                enrichment = enrich_backlog_task(
                    workspace_root=get_workspace_root(),
                    task_id=task_id,
                    image_path=self._find_backlog_image(task_id=task_id),
                )
            except (TaskEnrichmentError, ValueError) as exc:
                raise ApiRouteError(HTTPStatus.BAD_GATEWAY, str(exc)) from exc
            return {
                "ok": True,
                "command": "enrich-task",
                "data": {
                    "task": enrichment.task.as_mapping(),
                    "enrichment": {
                        "profile": enrichment.profile,
                        "guidelineCount": enrichment.guideline_count,
                        "usedImage": enrichment.used_image,
                        "model": enrichment.model,
                    },
                },
            }
        if action in {"finish", "done", "working", "todo"}:
            task_id = normalize_task_id(require_value(body=body, key="taskId"))
            status = "WORKING" if action == "working" else ("TODO" if action == "todo" else "DONE")
            return self._run_cli(["set-task-status", task_id, status, "--json"], expect_json=True).to_payload()
        if action == "delete":
            task_id = normalize_task_id(require_value(body=body, key="taskId"))
            arguments = ["delete-task", task_id]
            if body.get("force") is True:
                arguments.append("--force")
            arguments.append("--json")
            return self._run_cli(arguments, expect_json=True).to_payload()
        if action == "edit":
            task_id = normalize_task_id(require_value(body=body, key="taskId"))
            title = body.get("title")
            description = body.get("description")
            priority = body.get("priority")
            image_data = body.get("image")
            arguments = ["edit-task", task_id]
            if title is not None:
                arguments.extend(["--title", str(title)])
            if description is not None:
                arguments.extend(["--description", str(description)])
            if priority is not None:
                normalized_priority = safe_choice(str(priority), {"high", "medium", "low"}, "priority").upper()
                arguments.extend(["--priority", normalized_priority])
            arguments.append("--json")
            result = self._run_cli(arguments, expect_json=True).to_payload()
            if result.get("ok") and image_data:
                self._save_backlog_image(image_data=image_data, task_id=task_id)

            return result

        domain = require_value(body=body, key="domain")
        title = require_value(body=body, key="title")
        description = str(body.get("description", "")).strip() or title
        priority = safe_choice(str(body.get("priority", "LOW")), {"high", "medium", "low"}, "priority").upper()
        image_data = body.get("image")

        arguments = ["add-task", domain, title, "-d", description, "-p", priority]
        arguments.append("--json")
        result = self._run_cli(arguments, expect_json=True).to_payload()

        if result.get("ok") and image_data:
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            task = data.get("task") if isinstance(data.get("task"), dict) else {}
            task_id = str(task.get("id", ""))
            if re.fullmatch(r"t\d+", task_id):
                self._save_backlog_image(image_data=image_data, task_id=task_id)


        return result

    def _rename_backlog_domain(self) -> dict[str, Any]:
        """
        Rename one backlog-domain subtree through the canonical CLI contract.

        Returns:
            dict[str, Any]: Structured CLI mutation payload.
        """
        body = self._read_json_body()
        arguments = [
            "rename-task-domain",
            require_value(body=body, key="source"),
            require_value(body=body, key="target"),
        ]
        if body.get("exact") is True:
            arguments.append("--exact")
        arguments.append("--json")
        return self._run_cli(arguments, expect_json=True).to_payload()

    def _save_backlog_image(self, image_data: object, task_id: str) -> str | None:
        """Persist an optional user-supplied backlog image without affecting task mutations.

        Args:
            image_data: Browser-provided image data URL or raw Base64 payload.
            task_id: Normalized persistent task identifier used in the filename.

        Returns:
            The persisted file extension, or ``None`` when validation or writing fails.
        """
        import base64

        if not isinstance(image_data, str):
            return None
        try:
            if "," in image_data:
                header, base64_str = image_data.split(",", 1)
            else:
                base64_str = image_data
                header = ""
            image_bytes = base64.b64decode(base64_str, validate=True)
            extension = "png"
            if "image/jpeg" in header:
                extension = "jpg"
            elif "image/gif" in header:
                extension = "gif"
            elif "image/webp" in header:
                extension = "webp"
            pictures_dir = get_workspace_root() / "$agent" / "pictures"
            pictures_dir.mkdir(parents=True, exist_ok=True)
            (pictures_dir / f"backlog-pic-{task_id}.{extension}").write_bytes(image_bytes)
            return extension
        except (ValueError, OSError):
            # Attachments are optional and must never roll back a task mutation.
            return None

    def _find_backlog_image(self, task_id: str) -> Path | None:
        """Resolve one validated task attachment from the workspace picture store.

        Args:
            task_id: Normalized persistent task identifier.

        Returns:
            Existing image path, or ``None`` when the task has no attachment.
        """
        pictures_dir = get_workspace_root() / "$agent" / "pictures"
        for extension in ("png", "jpg", "jpeg", "gif", "webp"):
            candidate = pictures_dir / f"backlog-pic-{task_id}.{extension}"
            if candidate.is_file():
                return candidate
        return None
