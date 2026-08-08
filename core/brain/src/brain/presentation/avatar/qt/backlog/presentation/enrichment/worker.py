"""Qt-thread adapters for blocking unsaved task-description enrichment."""
from __future__ import annotations

from threading import Event


from PySide6.QtCore import QObject, QThread, Signal, Slot

from brain.presentation.avatar.qt.backlog.contracts.models import (
    TaskEnrichmentDraft,
)
from brain.presentation.avatar.qt.backlog.contracts.ports import TaskDraftEnrichmentPort


_ACTIVE_RUNNERS: set[object] = set()
"""Runners retained until their QThread emits ``finished``."""


class EnrichmentWorker(QObject):
    """Run one blocking enrichment request on a dedicated Qt worker thread.

    The worker only cooperatively suppresses result delivery after cancellation.
    It never attempts to terminate its own thread or interrupt the application
    service while that service is blocked on network I/O.
    """

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        enricher: TaskDraftEnrichmentPort,
        draft: TaskEnrichmentDraft,
    ) -> None:
        """Initialize a worker with one immutable request and port.

        Args:
            enricher: Presentation-owned port backed by the application service.
            draft: Immutable values captured at the start of enrichment.
        """
        super().__init__()
        self._enricher = enricher
        self._draft = draft
        self._cancelled = Event()

    def cancel(self) -> None:
        """Request cooperative cancellation without terminating the thread."""
        self._cancelled.set()

    @Slot()
    def run(self) -> None:
        """Execute the blocking port call and publish a non-cancelled outcome."""
        try:
            result = self._enricher.enrich(self._draft)
        except Exception as error:  # noqa: BLE001 - report application failures to Qt.
            if not self._cancelled.is_set():
                self.failed.emit(error)
        else:
            if not self._cancelled.is_set():
                self.succeeded.emit(result)
        finally:
            self.finished.emit()


class EnrichmentRunner(QObject):
    """Own one QObject/QThread enrichment transaction and its cleanup lifecycle.

    A runner can be cancelled repeatedly. Cancellation only marks the request
    and lets the worker finish naturally; the GUI can restore controls
    immediately while late callbacks are ignored by the owning form.
    """

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        enricher: TaskDraftEnrichmentPort,
        draft: TaskEnrichmentDraft | None = None,
    ) -> None:
        """Initialize a runner with a port and optionally a first request.

        Args:
            enricher: Presentation-owned port backed by the application service.
            draft: Optional request supplied now or later to :meth:`start`.
        """
        super().__init__()
        self._enricher = enricher
        self._draft = draft
        self._thread: QThread | None = None
        self._worker: EnrichmentWorker | None = None

    @property
    def is_running(self) -> bool:
        """Return whether the dedicated worker thread is currently active."""
        thread = self._thread
        return thread is not None and thread.isRunning()

    @property
    def thread(self) -> QThread | None:
        """Return the active thread for diagnostics without exposing ownership."""
        return self._thread

    def start(self, draft: TaskEnrichmentDraft | None = None) -> None:
        """Start one request on a fresh QThread.

        Args:
            draft: Request to run, or the request supplied during construction.

        Raises:
            ValueError: If no draft was supplied or this runner is already active.
        """
        if self.is_running:
            raise ValueError("Enrichment is already running")

        if draft is not None:
            self._draft = draft
        request = self._draft
        if request is None:
            raise ValueError("Enrichment draft is required")

        thread = QThread()
        worker = EnrichmentWorker(self._enricher, request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self.succeeded)
        worker.failed.connect(self.failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._thread_finished)
        self._thread = thread
        self._worker = worker
        _ACTIVE_RUNNERS.add(self)
        thread.start()

    def cancel(self) -> None:
        """Request cooperative cancellation and return without blocking the GUI."""
        worker = self._worker
        if worker is not None and self.is_running:
            worker.cancel()

    def _thread_finished(self) -> None:
        """Release thread references after natural worker completion."""
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.deleteLater()
        self.finished.emit()
        _ACTIVE_RUNNERS.discard(self)






