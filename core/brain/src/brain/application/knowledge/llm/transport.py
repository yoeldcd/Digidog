# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""HTTP transport for OpenAI-compatible chat completion requests."""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import dataclass
import json
import urllib.error
import urllib.request
from typing import Any


@dataclass(frozen=True)
class ChatCompletionResult:
    """Raw chat-completion response payload and transport metadata."""

    response_payload: dict[str, Any]
    response_chars: int
    status: int | str


class ChatCompletionHTTPError(RuntimeError):
    """HTTP error returned by an OpenAI-compatible chat-completion endpoint."""

    status_code: int
    response_text: str

    def __init__(self, status_code: int, response_text: str) -> None:
        super().__init__(f"Chat completion HTTP error {status_code}: {response_text}")
        self.status_code = status_code
        self.response_text = response_text


def post_chat_completion(
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> ChatCompletionResult:
    """
    POST one chat-completion request and return the decoded payload.

    Args:
        endpoint (str): Chat completion endpoint URL.
        api_key (str): Resolved bearer token.
        payload (dict[str, Any]): OpenAI-compatible request payload.
        timeout_seconds (int): Request timeout in seconds.

    Returns:
        ChatCompletionResult: Decoded JSON payload with response metadata.

    Raises:
        ChatCompletionHTTPError: When the endpoint returns an HTTP error.
    """
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_text: str = response.read().decode("utf-8")
            response_payload: dict[str, Any] = json.loads(response_text)
            return ChatCompletionResult(
                response_payload=response_payload,
                response_chars=len(response_text),
                status=getattr(response, "status", "unknown"),
            )
    except urllib.error.HTTPError as exc:
        error_text: str = exc.read().decode("utf-8", errors="replace")
        raise ChatCompletionHTTPError(status_code=exc.code, response_text=error_text) from exc
