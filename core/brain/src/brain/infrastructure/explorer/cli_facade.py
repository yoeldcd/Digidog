# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""In-process CLI facade for Brain Explorer API routes."""

from __future__ import annotations

# Standard Libraries Imports
import json
import io
import os
import sys
import threading
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

# Application Modules Imports
from brain.infrastructure.runtime.paths import get_local_database_dir, get_workspace_root
from brain.presentation.router.services.cli_runtime_service import run_cli


@dataclass(slots=True)
class CliCommandResult:
    """
    JSON-safe result returned by one delegated Brain CLI call.

    Attributes:
        ok: Whether the command exited successfully and produced parseable output when JSON was expected.
        command: Safe argv list represented by the in-process execution.
        code: CLI handler exit code or synthetic server-side failure code.
        stdout: Captured standard output.
        stderr: Captured standard error.
        duration_ms: Elapsed in-process command duration in milliseconds.
        data: Parsed JSON payload when available.
        error: Optional server-side error message.
    """

    ok: bool
    command: list[str]
    code: int
    stdout: str
    stderr: str
    duration_ms: int
    data: Any = None
    error: str | None = None
    queue_ms: int = 0
    execution_ms: int = 0

    def to_payload(self) -> dict[str, Any]:
        """
        Return the public API payload shape.

        Returns:
            dict[str, Any]: JSON-safe command result payload.
        """
        payload: dict[str, Any] = {
            "ok": self.ok,
            "command": self.command,
            "code": self.code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "durationMs": self.duration_ms,
            "queueMs": self.queue_ms,
            "executionMs": self.execution_ms,
        }
        if self.data is not None:
            payload["data"] = self.data
        if self.error is not None:
            payload["error"] = self.error
        return payload


class BrainCliFacade:
    """
    Execute allowlisted Brain CLI commands through the live Brain runtime.

    Attributes:
        facade_path: Absolute path to the current workspace `brain.py` facade.
        timeout: Compatibility limit retained in the public server configuration.
        workspace_root: Current workspace root passed to delegated commands.
    """

    def __init__(
        self,
        facade_path: Path | None = None,
        timeout: float = 30.0,
        workspace_root: Path | None = None,
    ) -> None:
        """
        Initialize the CLI facade.

        Args:
            facade_path (Path | None): Optional explicit `brain.py` path.
            timeout (float): Compatibility limit retained for callers.
            workspace_root (Path | None): Optional workspace root override.
        """
        self.workspace_root: Path = get_workspace_root(workspace_root=workspace_root)
        self.facade_path: Path = (facade_path or self._default_facade_path()).resolve()
        self.timeout: float = timeout
        self.execution_lock = threading.RLock()
        self._read_cache: dict[tuple[str, str, int, int], CliCommandResult] = {}

    def run(
        self,
        arguments: list[str],
        stdin_text: str | None = None,
        expect_json: bool = True,
        workspace_root: Path | str | None = None,
    ) -> CliCommandResult:
        """
        Execute one safe argv vector through the live Brain CLI facade.

        Args:
            arguments (list[str]): Command arguments after the `brain.py` script path.
            stdin_text (str | None): Optional stdin payload.
            expect_json (bool): Whether to parse stdout as JSON.

        Returns:
            CliCommandResult: Captured command result.
        """
        start_time: float = time.perf_counter()
        runtime_arguments = ["--no-speak", *arguments]
        command: list[str] = ["brain(in-process)", *arguments]
        active_workspace_root = Path(workspace_root).resolve() if workspace_root else self.workspace_root
        cache_key = self._log_index_cache_key(arguments=arguments, workspace_root=active_workspace_root)
        if cache_key is not None:
            cached_result = self._read_cache.get(cache_key)
            if cached_result is not None:
                return replace(cached_result, duration_ms=0, queue_ms=0, execution_ms=0)
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        with self.execution_lock:
            acquired_at = time.perf_counter()
            previous_stdin = sys.stdin
            previous_workspace_root = os.environ.get("WORKSPACE_ROOT")
            try:
                sys.stdin = io.StringIO(stdin_text or "")
                os.environ["WORKSPACE_ROOT"] = str(active_workspace_root)
                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    try:
                        code = run_cli(argv=runtime_arguments)
                    except SystemExit as exc:
                        code = int(exc.code or 0)
            finally:
                sys.stdin = previous_stdin
                self._restore_environment("WORKSPACE_ROOT", previous_workspace_root)

        finished_at = time.perf_counter()
        queue_ms = int((acquired_at - start_time) * 1000)
        execution_ms = int((finished_at - acquired_at) * 1000)
        duration_ms = int((finished_at - start_time) * 1000)
        stdout = stdout_buffer.getvalue()
        stderr = stderr_buffer.getvalue()
        parsed_data: Any = None
        parse_error: str | None = None
        if expect_json and stdout.strip():
            try:
                parsed_data = json.loads(stdout)
            except json.JSONDecodeError as exc:
                parse_error = f"Invalid JSON from CLI: {exc.msg}"

        ok: bool = code == 0 and parse_error is None
        result = CliCommandResult(
            ok=ok,
            command=command,
            code=code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            queue_ms=queue_ms,
            execution_ms=execution_ms,
            data=parsed_data,
            error=parse_error,
        )
        if cache_key is not None and result.ok:
            self._read_cache = {cache_key: result}
        return result

    def _log_index_cache_key(
        self,
        arguments: list[str],
        workspace_root: Path,
    ) -> tuple[str, str, int, int] | None:
        """Return an invalidation-aware cache key for the complete log index."""
        if not arguments or arguments[0] != "log-index":
            return None
        database_path = get_local_database_dir(workspace_root=workspace_root) / "brain_logs.db"
        try:
            stat = database_path.stat()
        except OSError:
            return None
        domain = arguments[1] if len(arguments) > 1 else ""
        return (str(workspace_root), domain, stat.st_mtime_ns, stat.st_size)

    @contextmanager
    def workspace_context(self, workspace_root: Path | str | None = None) -> Iterator[None]:
        """Apply one idempotent, nestable workspace context for a request."""
        requested_root = Path(workspace_root) if workspace_root else self.workspace_root
        target_root = get_workspace_root(workspace_root=requested_root)
        with self.execution_lock:
            previous_root = self.workspace_root
            previous_env_root = os.environ.get("WORKSPACE_ROOT")
            target_text = str(target_root)
            changed = previous_root != target_root or previous_env_root != target_text
            if changed:
                self.workspace_root = target_root
                os.environ["WORKSPACE_ROOT"] = target_text
            try:
                yield
            finally:
                if changed:
                    self.workspace_root = previous_root
                    self._restore_environment("WORKSPACE_ROOT", previous_env_root)

    def _default_facade_path(self) -> Path:
        """
        Resolve the workspace-local `brain.py` facade.

        Returns:
            Path: Existing or intended facade path.
        """
        workspace_facade: Path = self.workspace_root / "$agent" / "scripts" / "brain.py"
        if workspace_facade.exists():
            return workspace_facade
        current_argv_path: Path = Path(sys.argv[0]).resolve()
        if current_argv_path.name == "brain.py":
            return current_argv_path
        return workspace_facade

    @staticmethod
    def _restore_environment(name: str, previous_value: str | None) -> None:
        """Restore one process environment variable after an isolated command."""
        if previous_value is None:
            os.environ.pop(name, None)
            return
        os.environ[name] = previous_value

    @staticmethod
    def _duration_ms(start_time: float) -> int:
        """
        Calculate elapsed milliseconds from a `perf_counter` start value.

        Args:
            start_time (float): Start timestamp.

        Returns:
            int: Elapsed milliseconds.
        """
        return int((time.perf_counter() - start_time) * 1000)

    @staticmethod
    def _coerce_output(value: str | bytes | None) -> str:
        """
        Convert timeout output values to text.

        Args:
            value (str | bytes | None): Captured timeout output.

        Returns:
            str: Text output.
        """
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value
