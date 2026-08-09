"""Command-line parsing, resource loading, and presentation helpers."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence


class CliCommand(str, Enum):
    """Represent supported command-line operations."""

    CREATE = "create-agent"
    UPDATE = "update-agent"


@dataclass(frozen=True)
class CliRequest:
    """Represent an immutable parsed command-line request.

    Attributes:
        command: Requested CLI operation.
        parent_path: Parent directory used by create requests.
        agent_name: Agent name used by create requests.
        user_name: User name used by create requests.
        target_path: Existing target used by update requests.
        json_mode: Whether output should use JSON formatting.
    """

    command: CliCommand
    parent_path: Path | None = None
    agent_name: str | None = None
    user_name: str | None = None
    target_path: Path | None = None
    json_mode: bool = False


class CliResourceLoader:
    """Load JSON label resources from a configured file path."""

    def __init__(self, resource_path: Path) -> None:
        """Initialize a loader for one resource file.

        Args:
            resource_path: Path to the UTF-8 JSON resource file.
        """

        self._resource_path = Path(resource_path)

    def load(self) -> Mapping[str, str]:
        """Read and return resource labels.

        Returns:
            Mapping[str, str]: Loaded labels copied into a new dictionary.
        """

        with self._resource_path.open("r", encoding="utf-8") as stream:
            labels = json.load(stream)

        if not isinstance(labels, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in labels.items()):
            raise ValueError("CLI resource labels must be a JSON object of string keys and values")

        return dict(labels)


class CliParser:
    """Parse named and legacy command-line argument formats."""

    def __init__(self, labels: Mapping[str, str] | None = None) -> None:
        """Initialize a parser with optional localized labels.

        Args:
            labels: Optional mapping used to customize validation messages.
        """

        required_keys = ("missing_command", "invalid_arguments", "create_required", "update_required", "legacy_required")
        provided_labels = dict(labels or {})
        missing_keys = [key for key in required_keys if key not in provided_labels]
        if missing_keys:
            raise ValueError(f"Missing CLI labels: {missing_keys}")
        self._labels = provided_labels

    def parse(self, argv: Sequence[str]) -> CliRequest:
        """Parse command-line tokens into an immutable request.

        Args:
            argv: Command-line tokens excluding the executable name.

        Returns:
            CliRequest: Parsed request preserving the selected command and mode.

        Raises:
            ValueError: If required arguments or a command are missing.
        """

        tokens = [token for token in argv if token != "--json"]
        json_mode = "--json" in argv

        if not tokens:
            raise ValueError(self._labels["missing_command"])

        aliases = {"create-agent": CliCommand.CREATE, "create_agent": CliCommand.CREATE,
                   "update-agent": CliCommand.UPDATE, "update_agent": CliCommand.UPDATE}
        command = aliases.get(tokens[0])
        if command is not None:
            values = self._named(command, tokens[1:])
        else:
            command = CliCommand.CREATE
            values = self._legacy(tokens)

        return CliRequest(command=command, json_mode=json_mode, **values)

    def _named(self, command: CliCommand, tokens: list[str]) -> dict[str, object]:
        """Parse named arguments for a supported command.

        Args:
            command: Command whose required fields should be validated.
            tokens: Remaining command-line tokens.

        Returns:
            dict[str, object]: Parsed request fields.

        Raises:
            ValueError: If unknown or required arguments are present or absent.
        """

        values = self._parse_form(tokens)
        path = values.pop("path", None)

        if path is None:
            raise ValueError(self._labels["invalid_arguments"])

        if command is CliCommand.CREATE:
            if not values.get("agent_name") or not values.get("user_name"):
                raise ValueError(self._labels["create_required"])
            return {"parent_path": Path(path), **values}

        if values:
            raise ValueError(self._labels["invalid_arguments"])

        return {"target_path": Path(path)}

    def _legacy(self, tokens: list[str]) -> dict[str, object]:
        """Parse the positional legacy create format.

        Args:
            tokens: Positional parent path, agent name, and user name.

        Returns:
            dict[str, object]: Parsed create request fields.

        Raises:
            ValueError: If the legacy argument count is incorrect.
        """

        values = self._parse_form(tokens)
        path = values.pop("path", None)

        if path is None or not values.get("agent_name") or not values.get("user_name"):
            raise ValueError(self._labels["legacy_required"])

        return {
            "parent_path": Path(path),
            "agent_name": values["agent_name"],
            "user_name": values["user_name"],
        }

    def _parse_form(self, tokens: list[str]) -> dict[str, str]:
        values: dict[str, str] = {}
        positional: list[str] = []
        aliases = {"--agent-name": "agent_name", "--agent_name": "agent_name", "--user-name": "user_name", "--user_name": "user_name"}
        index = 0
        while index < len(tokens):
            token = tokens[index]
            field = aliases.get(token)
            if field is None:
                if token.startswith("-"):
                    raise ValueError(self._labels["invalid_arguments"])
                positional.append(token)
                index += 1
                continue
            index += 1
            if index >= len(tokens) or tokens[index].startswith("-"):
                raise ValueError(self._labels["invalid_arguments"])
            values[field] = tokens[index]
            index += 1
        if len(positional) != 1:
            raise ValueError(self._labels["invalid_arguments"])
        values["path"] = positional[0]
        return values


class CliPresenter:
    """Serialize command results and errors for human or JSON output."""

    def __init__(self, labels: Mapping[str, str] | None = None) -> None:
        """Initialize a presenter with optional labels.

        Args:
            labels: Optional mapping retained for presenter configuration.
        """

        self._labels = dict(labels or {})

    def present(self, value: object, json_mode: bool = False) -> str:
        """Render a value in JSON or human-readable form.

        Args:
            value: Value to serialize.
            json_mode: Whether to return sorted, Unicode-preserving JSON.

        Returns:
            str: Formatted representation of the value.
        """

        payload = self._serialize(value)

        if json_mode:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)

        return str(payload)

    def present_error(self, error: Exception, json_mode: bool = False) -> tuple[str, int]:
        """Render an exception and its process exit code.

        Args:
            error: Exception to represent.
            json_mode: Whether to return a structured JSON error.

        Returns:
            tuple[str, int]: Formatted error text and exit code ``2``.
        """

        payload = {"error": {"type": type(error).__name__, "message": str(error)}}

        if json_mode:
            output = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        else:
            output = str(error)

        return output, 2

    def _serialize(self, value: object) -> object:
        """Convert supported values into JSON-compatible structures.

        Args:
            value: Value to convert recursively.

        Returns:
            object: Scalar or recursively converted representation.
        """

        if isinstance(value, Path):
            return str(value)

        if isinstance(value, Enum):
            return self._serialize(value.value)

        if is_dataclass(value):
            serialized_fields = asdict(value)
            return {key: self._serialize(item) for key, item in serialized_fields.items()}

        if isinstance(value, (tuple, list)):
            return [self._serialize(item) for item in value]

        if isinstance(value, Mapping):
            return {str(key): self._serialize(item) for key, item in value.items()}

        return value