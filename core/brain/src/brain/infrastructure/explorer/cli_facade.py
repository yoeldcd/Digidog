# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Provide an in-process bridge from Brain Explorer routes to CLI handlers.

The facade captures command I/O, enforces request-local runtime protections, and restores process state
so web requests can reuse the live Brain CLI without leaking server-only details.
"""

from __future__ import annotations

# Standard Libraries Imports
import json
import io
import os
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TypeAlias, cast

# Application Modules Imports
from brain.infrastructure.runtime.paths import get_local_database_dir, get_workspace_root
from brain.presentation.router.services.cli_runtime_service import run_cli


JsonScalar: TypeAlias = str | int | float | bool | None
"""JSON scalar values accepted by serialized Brain CLI result payloads."""

JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
"""Recursive JSON value shape used for parsed command output and public payloads."""


@dataclass(slots=True)
class CliCommandResult:
    """Represent the JSON-safe result of one delegated Brain CLI call.

    Centralizes execution status, sanitized command identity, captured streams, timing, and parsed
    payloads so Explorer routes can expose one stable response shape without leaking runtime flags.

    Attributes:
        ok: Whether the command exited successfully and produced parseable output when JSON was expected.
        command: Safe argv list represented by the in-process execution.
        code: CLI handler exit code or synthetic server-side failure code.
        stdout: Captured standard output.
        stderr: Captured standard error.
        duration_ms: Elapsed in-process command duration in milliseconds.
        data: Parsed JSON payload when available.
        error: Optional server-side error message.
        queue_ms (int): Milliseconds spent waiting for the execution lock.
        execution_ms (int): Milliseconds spent executing the delegated command.
    """

    ok: bool
    command: list[str]
    code: int
    stdout: str
    stderr: str
    duration_ms: int
    data: JsonValue = None
    error: str | None = None
    queue_ms: int = 0
    execution_ms: int = 0

    def to_payload(self) -> dict[str, JsonValue]:
        """Convert the internal result into the public Explorer response shape.

        Omits optional payload and error keys when absent while retaining stable status, command,
        captured-stream, and timing fields for route consumers.

        Args:
            None.

        Returns:
            dict[str, JsonValue]: JSON-safe command result payload.
        """
        payload: dict[str, JsonValue] = {
            "ok": self.ok,
            "command": self.command,
            "code": self.code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "durationMs": self.duration_ms,
            "queueMs": self.queue_ms,
            "executionMs": self.execution_ms,
        }

        # Payload projection: expose parsed command data only when JSON output was available.

        if self.data is not None:
            payload["data"] = self.data

        # Error projection: expose parse or server errors only when the command produced one.

        if self.error is not None:
            payload["error"] = self.error

        return payload


class BrainCliFacade:
    """Coordinate safe, in-process execution of allowlisted Brain CLI commands.

    Owns the execution lock, selected workspace, cache metadata, and facade path needed to keep
    request execution isolated while reusing the live Brain runtime.

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
        """Initialize the facade execution boundary and workspace-dependent state.

        Resolves the active workspace and local facade path, then creates the lock and read-cache
        state used to serialize process-global I/O and reuse stable log-index reads.

        Args:
            facade_path (Path | None): Optional explicit `brain.py` path.
            timeout (float): Compatibility limit retained for callers.
            workspace_root (Path | None): Optional workspace root override.

        Returns:
            None.
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
        """Execute one safe argv vector through the live Brain CLI facade.

        Adds internal silence and user authority flags to the delegated runtime vector, captures
        process I/O under the execution lock, and returns parsed output without exposing those flags.

        Args:
            arguments (list[str]): Command arguments after the `brain.py` script path.
            stdin_text (str | None): Optional stdin payload.
            expect_json (bool): Whether to parse stdout as JSON.
            workspace_root (Path | str | None): Optional registered workspace override.

        Returns:
            CliCommandResult: Captured command result.
        """
        start_time: float = time.perf_counter()
        runtime_arguments = ["--no-speak", *arguments, "--authority", "user"]
        command: list[str] = ["brain(in-process)", *arguments]
        active_workspace_root = Path(workspace_root).resolve() if workspace_root else self.workspace_root
        cache_key = self._log_index_cache_key(arguments=arguments, workspace_root=active_workspace_root)

        # Cache lookup: reuse only a log-index result whose database metadata still matches.

        if cache_key is not None:
            cached_result = self._read_cache.get(cache_key)

            # Cache hit: return a zero-work timing view without replaying the delegated command.

            if cached_result is not None:
                return replace(cached_result, duration_ms=0, queue_ms=0, execution_ms=0)

        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        # Process isolation: serialize mutations to stdin, stdout, stderr, and WORKSPACE_ROOT.

        with self.execution_lock:
            acquired_at = time.perf_counter()
            previous_stdin = sys.stdin
            previous_workspace_root = os.environ.get("WORKSPACE_ROOT")

            # State capture: preserve caller-owned process state before activating this request.

            try:
                sys.stdin = io.StringIO(stdin_text or "")
                os.environ["WORKSPACE_ROOT"] = str(active_workspace_root)

                # Stream capture: keep CLI output inside the request result instead of the server console.

                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):

                    # Exit normalization: convert CLI termination into the same result path as return codes.

                    try:
                        code = run_cli(argv=runtime_arguments)

                    # System-exit boundary: preserve the CLI explicit status without escaping the facade.

                    except SystemExit as exc:
                        code = int(exc.code or 0)

            # State restoration: return stdin and the workspace environment even when CLI execution fails.

            finally:
                sys.stdin = previous_stdin
                self._restore_environment("WORKSPACE_ROOT", previous_workspace_root)

        finished_at = time.perf_counter()
        queue_ms = int((acquired_at - start_time) * 1000)
        execution_ms = int((finished_at - acquired_at) * 1000)
        duration_ms = int((finished_at - start_time) * 1000)
        stdout = stdout_buffer.getvalue()
        stderr = stderr_buffer.getvalue()
        parsed_data: JsonValue = None
        parse_error: str | None = None

        # JSON parsing: interpret output only when the caller requested a structured response.

        if expect_json and stdout.strip():

            # Parse boundary: turn malformed CLI output into an explicit API error.

            try:
                parsed_data = cast(JsonValue, json.loads(stdout))

            # Invalid-output boundary: retain command completion while recording parse failure details.

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

        # Cache write: retain only successful log-index results for the exact current database identity.

        if cache_key is not None and result.ok:
            self._read_cache = {cache_key: result}

        return result

    def _log_index_cache_key(
        self,
        arguments: list[str],
        workspace_root: Path,
    ) -> tuple[str, str, int, int] | None:
        """Build the cache identity for log-index reads and invalidate it on database changes.

        Only log-index reads are cacheable; database modification time and size bind the key to the
        current durable projection, while unavailable metadata disables caching safely.

        Args:
            arguments: Command arguments used to identify log-index requests.
            workspace_root: Active workspace containing the log database.

        Returns:
            Cache key derived from database metadata, or ``None`` when unavailable.
        """

        # Command filter: restrict caching to the complete log-index projection.

        if not arguments or arguments[0] != "log-index":
            return None

        database_path = get_local_database_dir(workspace_root=workspace_root) / "brain_logs.db"

        # Metadata probe: use durable database identity to invalidate stale read results.

        try:
            stat = database_path.stat()

        # Availability boundary: skip caching when the workspace database cannot be inspected.

        except OSError:
            return None

        domain = arguments[1] if len(arguments) > 1 else ""

        return (str(workspace_root), domain, stat.st_mtime_ns, stat.st_size)

    @contextmanager
    def workspace_context(self, workspace_root: Path | str | None = None) -> Iterator[None]:
        """Temporarily activate a normalized workspace while preserving nesting semantics.

        Serializes process-global environment changes, updates state only when the target differs,
        and restores both the facade field and WORKSPACE_ROOT after the context exits.

        Args:
            workspace_root (Path | str | None): Optional workspace root to activate.

        Returns:
            Iterator[None]: Context manager yielding while the workspace is active.
        """
        requested_root = Path(workspace_root) if workspace_root else self.workspace_root
        target_root = get_workspace_root(workspace_root=requested_root)

        # Context serialization: guard the process-global workspace while the request is active.

        with self.execution_lock:
            previous_root = self.workspace_root
            previous_env_root = os.environ.get("WORKSPACE_ROOT")
            target_text = str(target_root)
            changed = previous_root != target_root or previous_env_root != target_text

            # Context activation: update local and environment state only when the target differs.

            if changed:
                self.workspace_root = target_root
                os.environ["WORKSPACE_ROOT"] = target_text

            # Context lifetime: yield the protected workspace to the caller route operation.

            try:
                yield

            # Context restoration: unwind only the state this context changed, preserving nesting.

            finally:

                # Restoration guard: leave an idempotent nested context inherited state untouched.

                if changed:
                    self.workspace_root = previous_root
                    self._restore_environment("WORKSPACE_ROOT", previous_env_root)

    def _default_facade_path(self) -> Path:
        """
        Prefer the active workspace agent script, fall back to the current process script when invoked
        from brain.py, and otherwise return the intended workspace path without starting a process.

        Resolve the workspace-local `brain.py` facade.

        Args:
            None.

        Returns:
            Path: Existing or intended facade path.
        """
        workspace_facade: Path = self.workspace_root / "$agent" / "scripts" / "brain.py"

        # Workspace preference: use the active workspace facade when it exists.

        if workspace_facade.exists():
            return workspace_facade

        current_argv_path: Path = Path(sys.argv[0]).resolve()

        # Direct-invocation fallback: reuse the current script when the process already runs brain.py.

        if current_argv_path.name == "brain.py":
            return current_argv_path

        return workspace_facade

    @staticmethod
    def _restore_environment(name: str, previous_value: str | None) -> None:
        """Restore one process environment variable to its captured pre-request state.

        Reinstate the previous value when present and remove the variable when it did not exist,
        preventing request-local workspace selection from leaking into later commands.

        Args:
            name: Environment variable name to restore.
            previous_value: Value to restore, or ``None`` to remove the variable.

        Returns:
            None.
        """

        # Removal branch: recreate the absence of a variable that was not set by the caller.

        if previous_value is None:
            os.environ.pop(name, None)

            return

        os.environ[name] = previous_value

    @staticmethod
    def _duration_ms(start_time: float) -> int:
        """
        Keeps queue, execution, and total duration calculations on one rounding convention so the
        public result reports comparable timing values.

        Calculate elapsed milliseconds from a `perf_counter` start value.

        Args:
            start_time (float): Start timestamp.

        Returns:
            int: Elapsed milliseconds.
        """

        return int((time.perf_counter() - start_time) * 1000)

    @staticmethod
    def _coerce_output(value: str | bytes | None) -> str:
        """Normalize optional process output to text for timeout and error reporting.

        Preserve text values, decode bytes with replacement for invalid UTF-8, and map missing output
        to an empty string so failure payloads remain serializable.

        Args:
            value (str | bytes | None): Captured timeout output.

        Returns:
            str: Text output.
        """

        # Missing-output normalization: represent absent process output as an empty response field.

        if value is None:
            return ""

        # Byte-output normalization: decode captured process bytes without raising on malformed text.

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        return value
