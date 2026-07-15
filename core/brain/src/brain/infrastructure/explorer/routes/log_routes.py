"""LogRoutesMixin for Brain Explorer."""

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


class LogRoutesMixin:
    """Provide one cohesive group of Explorer routes."""

    def _logs(self, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute log export for visual inspection.

        Args:
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        arguments = ["export-logs", "--stdout"]
        for key, flag in {"domain": "--domain", "date": "--date", "time": "--time", "from": "--from", "to": "--to"}.items():
            value = query.get(key)
            if value:
                arguments.extend([flag, value])
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

    def _log_index(self, query: dict[str, str]) -> dict[str, Any]:
        """
        Execute `log-index` for domain tree navigation.

        Args:
            query (dict[str, str]): First-value query mapping.

        Returns:
            dict[str, Any]: CLI result payload.
        """
        arguments = ["log-index"]
        domain = query.get("domain")
        if domain:
            arguments.append(domain)
        arguments.append("--json")
        return self._run_cli(arguments, expect_json=True).to_payload()
