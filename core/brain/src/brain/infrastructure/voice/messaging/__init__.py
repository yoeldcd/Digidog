"""Voice message queue, session, and signal infrastructure."""

from brain.infrastructure.voice.contracts.instance_results import (
    InstanceEnqueueResult,
    InstanceTerminalResult,
    InstanceTerminalState,
)
from brain.infrastructure.voice.messaging.instance_lifecycle import (
    InstanceLifecycleRegistry,
)
from brain.infrastructure.voice.messaging.message_queue import (
    MAX_MEMORY_MESSAGES,
    MessageQueueMixin,
    bounded_prelude_seconds,
)
from brain.infrastructure.voice.messaging.message_session import (
    ActiveMessageSession,
    MessageSessionMixin,
    TtsBatchSession,
    WindowReadyLease,
)
from brain.infrastructure.voice.messaging.voice_signals import (
    VoiceSignalService,
    natural_timestamp,
)

__all__ = [
    "ActiveMessageSession",
    "InstanceEnqueueResult",
    "InstanceLifecycleRegistry",
    "InstanceTerminalResult",
    "InstanceTerminalState",
    "MAX_MEMORY_MESSAGES",
    "MessageQueueMixin",
    "MessageSessionMixin",
    "TtsBatchSession",
    "VoiceSignalService",
    "WindowReadyLease",
    "bounded_prelude_seconds",
    "natural_timestamp",
]
