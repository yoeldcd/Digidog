# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Codex quota transport isolation regression tests."""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from brain.infrastructure.codex.quota_client import CodexQuotaClient


def test_app_server_process_uses_private_runtime_cwd() -> None:
    client = CodexQuotaClient()
    process = MagicMock()
    process.stdin = StringIO()
    process.stdout = StringIO()
    runtime_directory = Path("D:/private-agent/$agent/.tmp/codex-app-server")

    with (
        patch.object(client, "_find_executable", return_value=Path("C:/codex.exe")),
        patch.object(client, "_codex_home", return_value=Path("C:/codex-home")),
        patch.object(client, "_runtime_directory", return_value=runtime_directory),
        patch.object(client, "_request", return_value={}),
        patch.object(client, "_send"),
        patch("brain.infrastructure.codex.quota_client.subprocess.Popen", return_value=process) as popen,
    ):
        client._ensure_started()

    assert popen.call_args.kwargs["cwd"] == str(runtime_directory)
    assert popen.call_args.args[0][-2:] == ["app-server", "--stdio"]


def test_runtime_cwd_is_owned_by_agent_home_not_workspace() -> None:
    """WORKSPACE_ROOT must never influence the App Server working directory."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as root:
        agent_home = Path(root) / "agent-home"
        consumer = Path(root) / "consumer"
        with patch.dict(os.environ, {"AGENT_HOME": str(agent_home), "WORKSPACE_ROOT": str(consumer)}):
            runtime_directory = CodexQuotaClient._runtime_directory()

        assert runtime_directory == agent_home / "$agent" / ".tmp" / "codex-app-server"
        assert consumer not in runtime_directory.parents
