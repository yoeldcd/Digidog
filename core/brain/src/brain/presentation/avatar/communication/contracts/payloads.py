# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Named JSON contracts that cross the avatar communication boundary."""

from __future__ import annotations

from typing import TypedDict


class AppServerErrorPayload(TypedDict, total=False):
    """Error fields returned by one Codex App Server JSON-RPC response.

    Attributes:
        message (str): Human-readable rejection detail.
        code (int): Optional protocol error code.
    """

    message: str
    code: int


class AppServerTurnPayload(TypedDict, total=False):
    """Turn fields required to identify an active Codex turn.

    Attributes:
        id (str): Stable turn identifier.
        status (str): Server lifecycle status for the turn.
    """

    id: str
    status: str


class AppServerThreadPayload(TypedDict, total=False):
    """Thread fields consumed while selecting a turn delivery strategy.

    Attributes:
        turns (list[AppServerTurnPayload]): Ordered turns in the conversation.
    """

    turns: list[AppServerTurnPayload]


class AppServerResultPayload(TypedDict, total=False):
    """Result object exposed by the App Server transport port.

    Attributes:
        thread (AppServerThreadPayload): Optional resumed-thread projection.
        value (object): Wrapped scalar result for non-object responses.
    """

    thread: AppServerThreadPayload
    value: object


class AppServerResponsePayload(TypedDict, total=False):
    """Top-level JSON-RPC response parsed by the private transport adapter.

    Attributes:
        id (int | str): Request identifier echoed by the server.
        result (AppServerResultPayload): Successful operation result.
        error (AppServerErrorPayload | str): Rejection detail, when present.
    """

    id: int | str
    result: AppServerResultPayload
    error: AppServerErrorPayload | str


class ConsumerMessagePayload(TypedDict):
    """Serialized consumer message delivered through the native bridge.

    Attributes:
        message_id (str): Opaque message UUID.
        text (str): Reply content.
        mode (str): Serialized delivery strategy.
        source_message_id (str): Avatar message that prompted the reply.
        created_at (float): Unix creation timestamp.
    """

    message_id: str
    text: str
    mode: str
    source_message_id: str
    created_at: float


class BridgeSignalPayload(TypedDict):
    """Serialized payload-blind routing signal for the native bridge.

    Attributes:
        message_id (str): Opaque queued-message UUID.
        thread_id (str): Target Codex conversation identifier.
        host_id (str): Host owning the target conversation.
        created_at (float): Unix creation timestamp.
    """

    message_id: str
    thread_id: str
    host_id: str
    created_at: float
