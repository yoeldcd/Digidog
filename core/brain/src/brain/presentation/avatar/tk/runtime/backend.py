# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Tk-side HTTP adapter for the toolkit-neutral avatar controllers."""
from __future__ import annotations

import json
from typing import Any, Mapping, TypedDict, cast
from urllib.request import Request, urlopen

from brain.infrastructure.voice.daemon.daemon_client import VOICE_DAEMON_URL
from brain.presentation.avatar.interactivity.interaction_controller import AvatarCommand


class TkDaemonStatusDTO(TypedDict, total=False):
    """JSON status fields consumed by the shared daemon projection.

    Attributes:
        instanceId (str): Voice daemon instance identifier.
        state (str): Runtime state name.
        displayText (str): Current rendered text.
        emotion (str): Current emotion label.
        muteMode (str): Effective mute mode.
        queueDepth (int): Pending command count.
        historyCount (int): Number of retained messages.
    """

    instanceId: str
    state: str
    displayText: str
    emotion: str
    muteMode: str
    queueDepth: int
    historyCount: int


class TkDaemonMessagesDTO(TypedDict, total=False):
    """JSON history fields consumed by the Tk message controller.

    Attributes:
        speaks (list[Mapping[str, Any]]): Retained speech records.
        messages (list[Mapping[str, Any]]): Audio metadata records keyed by speech ID.
    """

    speaks: list[Mapping[str, Any]]
    messages: list[Mapping[str, Any]]


# Backward-compatible aliases for existing callers
TkStatusPayload = TkDaemonStatusDTO
TkMessagesPayload = TkDaemonMessagesDTO


class TkDaemonAdapter:
    """Translate semantic commands and status reads at the HTTP boundary.

    Attributes:
        base_url (str): HTTP origin of the local avatar daemon.
        timeout (float): Daemon request timeout in seconds.
    """

    def __init__(self, base_url: str = VOICE_DAEMON_URL, timeout: float = .5) -> None:
        """Initialize the component with its required Tk collaborators.

        Args:
            base_url (str): HTTP origin of the local avatar daemon.
            timeout (float): Daemon request timeout in seconds.

        Returns:
            None.
        """
        self.base_url = base_url
        self.timeout = timeout

    def execute(self, command: AvatarCommand) -> None:
        """Send one semantic avatar command to the daemon.

        Args:
            command (AvatarCommand): Shared command containing endpoint and JSON payload.

        Returns:
            None.
        """
        self.post(command.endpoint, command.payload)

    def post(self, path: str, payload: Mapping[str, Any] | None = None) -> None:
        """POST a JSON mapping to a daemon endpoint.

        Args:
            path (str): Daemon endpoint path.
            payload (Mapping[str, Any] | None): Optional JSON-compatible request mapping.

        Returns:
            None.
        """
        body = json.dumps(dict(payload or {})).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        urlopen(request, timeout=self.timeout).close()

    def status(self) -> TkDaemonStatusDTO:
        """Return the latest daemon status payload.

        Returns:
            TkDaemonStatusDTO: Latest typed daemon status mapping.
        """
        return cast(TkDaemonStatusDTO, self._get("/status"))

    def messages(self) -> TkDaemonMessagesDTO:
        """Return retained daemon history payloads.

        Returns:
            TkDaemonMessagesDTO: Typed retained-history payload.
        """
        return cast(TkDaemonMessagesDTO, self._get("/messages"))

    def _get(self, path: str) -> TkDaemonStatusDTO | TkDaemonMessagesDTO:
        """Fetch and validate a mapping-shaped JSON payload privately.

        Args:
            path (str): Daemon endpoint path.

        Returns:
            TkDaemonStatusDTO | TkDaemonMessagesDTO: A typed adapter payload, or an empty mapping for malformed JSON.
        """
        with urlopen(f"{self.base_url}{path}", timeout=min(self.timeout, .2)) as response:
            payload = json.loads(response.read())

        return payload if isinstance(payload, dict) else {}