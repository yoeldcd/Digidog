# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

'Voice HTTP payload and message metadata contracts.'

import json
from io import BytesIO
from unittest.mock import Mock, patch
from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.daemon.daemon import VoiceDaemonHandler, VoiceMemory
from brain.infrastructure.voice.daemon.daemon_client import VoiceDaemonClient
from brain.infrastructure.voice.service.voice_service import VoiceService


def test_speak_http_accepts_a_full_embedded_file_payload_without_truncation() -> None:
    """A 48 KiB file duplicated into display and narration fits the HTTP contract."""
    embedded = "á" * 40_000
    payload = {
        "text": f"Plan {embedded}",
        "displayText": f"Plan\n\n## 📎 boundary.md\n\n{embedded}",
        "lang": "es",
        "hasEmbeddedFile": True,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert len(body) > 64_000

    handler = object.__new__(VoiceDaemonHandler)
    handler.path = "/speak"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler._send_json = Mock()
    memory = Mock()
    memory.enqueue.return_value = "speak-boundary"
    with patch("brain.infrastructure.voice.daemon.daemon.MEMORY", memory):
        handler.do_POST()

    assert memory.enqueue.call_args.kwargs["has_embedded_file"] is True
    assert memory.enqueue.call_args.kwargs["text"].endswith(embedded)
    handler._send_json.assert_called_once()
    assert handler._send_json.call_args.kwargs["status"].value == 202


def test_embedded_file_metadata_crosses_client_and_daemon_history_boundaries() -> None:
    client = VoiceDaemonClient()
    with (
        patch.object(client, "_ensure_daemon"),
        patch.object(client, "_request_json", return_value={"ok": True}) as request,
    ):
        client.speak(AvatarSpeakRequest(text="Plan", display_text="Plan completo", has_embedded_file=True))
    assert request.call_args.kwargs["payload"]["hasEmbeddedFile"] is True

    memory = VoiceMemory()
    speak_id = memory.enqueue(
        "Plan narrado",
        "es",
        display_text="Plan visual",
        has_embedded_file=True,
    )
    assert speak_id is not None
    memory.active_speak_id = speak_id
    assert memory.status()["hasEmbeddedFile"] is True
    message = memory.store(b"audio", speak_id=speak_id, text="Plan narrado")
    assert message["hasEmbeddedFile"] is True
    assert memory.snapshot()["messages"][0]["hasEmbeddedFile"] is True


def test_speak_propagates_codex_reply_target_as_metadata() -> None:
    service = VoiceService()
    thread_id = "019f5dad-af67-7533-b394-8fb55258adb2"
    with patch("brain.infrastructure.voice.service.voice_service.VoiceDaemonClient.speak") as speak:
        service.speak("Mensaje dirigido", codex_thread_id=thread_id)
    assert speak.call_args.args[0].codex_thread_id == thread_id
