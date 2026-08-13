"""Public import-compatible façade for the modular Qt reply composer package."""
from __future__ import annotations

from brain.presentation.avatar.qt.reply_window.controller import AvatarReplyController
from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
    ReplyResultDTO,
    ReplyTerminalState,
)
from .screenshot import (
    CLIPBOARD_INSTRUCTION,
    QtReplyScreenshotCoordinator,
    append_clipboard_instruction,
)
from .window import QtReplyWindow

__all__ = [
    "AvatarReplyController",
    "CLIPBOARD_INSTRUCTION",
    "CodexThreadTargetDTO",
    "DeliveryMode",
    "QtReplyScreenshotCoordinator",
    "QtReplyWindow",
    "ReplyResultDTO",
    "ReplyTerminalState",
    "append_clipboard_instruction",
]
