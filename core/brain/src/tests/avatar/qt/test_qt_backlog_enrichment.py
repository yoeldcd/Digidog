"""Deterministic offscreen contracts for native backlog draft enrichment."""
from __future__ import annotations

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QAbstractAnimation
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QLayout

from brain.presentation.avatar.qt.backlog.contracts.models import (
    TaskEnrichmentDraft,
    TaskEnrichmentResult,
)
from brain.presentation.avatar.qt.backlog.presentation.form import TaskFormDialog
from brain.presentation.avatar.qt.backlog.presentation.icons import SVG_PATHS


def _app() -> QApplication:
    """Return the process-wide offscreen Qt application."""
    return QApplication.instance() or QApplication([])


def _wait_for(predicate: object, app: QApplication, timeout: float = 2.0) -> None:
    """Process Qt events until a callable predicate becomes true.

    Args:
        predicate: Zero-argument callable returning a truthy completion state.
        app: Qt application whose event queue must be processed.
        timeout: Maximum wait duration in seconds.

    Raises:
        AssertionError: If the predicate does not become true in time.
    """
    check = predicate
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if callable(check) and check():
            return
        QTest.qWait(10)
    app.processEvents()
    assert callable(check) and check()


class _BlockingEnricher:
    """Thread-observable fake port with externally released completion."""

    def __init__(self, description: str) -> None:
        """Initialize a fake response and synchronization events."""
        self.description = description
        self.started = threading.Event()
        self.release = threading.Event()
        self.thread_id: int | None = None
        self.draft: TaskEnrichmentDraft | None = None

    def enrich(self, draft: TaskEnrichmentDraft) -> TaskEnrichmentResult:
        """Record the request, block until released, and return a result."""
        self.thread_id = threading.get_ident()
        self.draft = draft
        self.started.set()
        self.release.wait(2.0)
        return TaskEnrichmentResult(description=self.description)


def _form(enricher: _BlockingEnricher) -> TaskFormDialog:
    """Build one populated add form using the deterministic fake port."""
    form = TaskFormDialog(project="alpha", enricher=enricher)
    form.domain_input.setText("core.brain.backlog")
    form.title_input.setText("Native enrichment")
    form.priority_selector.setCurrentText("HIGH")
    form.description_input.setPlainText("Current draft")
    return form


def _layout_widgets(layout: QLayout) -> list[object]:
    """Return direct widgets from one layout while ignoring stretch items.

    Args:
        layout: Qt layout whose direct widget items should be inspected.

    Returns:
        list[object]: Direct widget instances in visual order.
    """
    widgets: list[object] = []
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if widget is not None:
            widgets.append(widget)

    return widgets


def test_form_places_accent_enrich_in_heading_and_preserves_footer_actions() -> None:
    """The accent Enrich action lives in the marked heading slot, not the footer."""
    _app()
    enricher = _BlockingEnricher("Generated description")
    form = _form(enricher)
    form.show()
    root_layout = form.layout()
    assert root_layout is not None
    heading_layout = root_layout.itemAt(0).layout()
    footer_layout = root_layout.itemAt(root_layout.count() - 1).layout()
    assert heading_layout is not None
    assert footer_layout is not None

    assert heading_layout.indexOf(form.enrich_button) >= 0
    assert footer_layout.indexOf(form.enrich_button) == -1
    assert _layout_widgets(footer_layout) == [form.cancel_button, form.submit_button]
    footer_sizes = (form.cancel_button.size(), form.submit_button.size())
    stylesheet = form.styleSheet()
    assert "QPushButton#enrichButton" in stylesheet
    assert f"background: {form.theme_tokens.accent};" in stylesheet
    assert f"color: {form.theme_tokens.accent_text};" in stylesheet
    assert form.enrich_button.property("enrichmentActive") is False

    form.enrich_button.click()
    _wait_for(lambda: form._enrichment_active, _app())
    assert form.enrich_button.property("enrichmentActive") is True
    assert form.enrich_button.text() == "Cancel"
    assert form.cancel_button.size() == footer_sizes[0]
    assert form.submit_button.size() == footer_sizes[1]
    form.cancel_enrichment()
    enricher.release.set()
    _wait_for(lambda: not form._retired_enrichment_runners, _app())
    form.close()


def test_explorer_paths_are_exact_and_dtos_are_immutable() -> None:
    """The native contract owns exact Explorer paths and frozen request values."""
    assert SVG_PATHS["enrich"] == (
        '<path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/>'
        '<path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>'
        '<path d="M5 14l.7 1.8 1.8.7-1.8.7L5 19l-.7-1.8-1.8-.7 1.8-.7z"/>'
    )
    assert SVG_PATHS["pause"] == '<path d="M8 5v14M16 5v14"/>'
    request = TaskEnrichmentDraft("domain", "title", "HIGH", "description")
    try:
        request.title = "changed"  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("Task enrichment DTO must be immutable")


def test_form_enrichment_runs_off_gui_thread_and_replaces_description() -> None:
    """A successful current response locks controls, then updates description only."""
    app = _app()
    enricher = _BlockingEnricher("Generated description")
    form = _form(enricher)
    form.show()
    form.enrich_button.click()
    assert enricher.started.wait(1.0)
    _wait_for(lambda: form._enrichment_active, app)

    assert enricher.thread_id != threading.get_ident()
    assert enricher.draft == TaskEnrichmentDraft(
        "core.brain.backlog",
        "Native enrichment",
        "HIGH",
        "Current draft",
    )
    assert not form.domain_input.isEnabled()
    assert not form.title_input.isEnabled()
    assert not form.priority_selector.isEnabled()
    assert not form.description_input.isEnabled()
    assert not form.capture_button.isEnabled()
    assert not form.cancel_button.isEnabled()
    assert not form.submit_button.isEnabled()
    assert form.enrich_button.isEnabled()
    assert form.enrich_button.text() == "Cancel"
    assert not form.enrich_button.icon().isNull()

    effect = form.description_input.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    assert form._description_fade_animation is not None
    assert form._description_fade_animation.loopCount() == -1
    assert effect.opacity() == 1.0
    _wait_for(lambda: effect.opacity() < 0.99, app)

    enricher.release.set()
    _wait_for(lambda: not form._enrichment_active, app)
    assert form.description_input.toPlainText() == "Generated description"
    assert form._description_opacity_effect is not None
    assert form._description_opacity_effect.opacity() == 1.0
    assert form._description_fade_animation is not None
    assert form._description_fade_animation.state() == QAbstractAnimation.State.Stopped
    assert form.domain_input.isEnabled()
    assert form.title_input.isEnabled()
    assert form.priority_selector.isEnabled()
    assert form.description_input.isEnabled()
    assert form.cancel_button.isEnabled()
    assert form.submit_button.isEnabled()
    assert form.enrich_button.text() == "Enrich"
    form.close()


def test_cancel_restores_immediately_and_discards_late_result() -> None:
    """Cancellation invalidates the generation and ignores a late worker result."""
    app = _app()
    enricher = _BlockingEnricher("Late generated description")
    form = _form(enricher)
    form.show()
    form.enrich_button.click()
    assert enricher.started.wait(1.0)
    _wait_for(lambda: form._enrichment_active, app)

    form.enrich_button.click()
    assert not form._enrichment_active
    assert form.enrich_button.text() == "Enrich"
    assert form.description_input.toPlainText() == "Current draft"
    assert form._description_opacity_effect is not None
    assert form._description_opacity_effect.opacity() == 1.0
    assert form.cancel_button.isEnabled()
    assert form.submit_button.isEnabled()

    enricher.release.set()
    _wait_for(lambda: not form._retired_enrichment_runners, app)
    assert form.description_input.toPlainText() == "Current draft"
    form.close()


def test_close_during_enrichment_retains_thread_and_discards_result() -> None:
    """Closing a modeless form keeps its worker alive until natural shutdown."""
    app = _app()
    enricher = _BlockingEnricher("Result after close")
    form = _form(enricher)
    form.show()
    form.enrich_button.click()
    assert enricher.started.wait(1.0)
    _wait_for(lambda: form._enrichment_active, app)
    runner = form._enrichment_runner
    assert runner is not None

    form.close()
    assert not form._enrichment_active
    assert form._description_opacity_effect is not None
    assert form._description_opacity_effect.opacity() == 1.0
    enricher.release.set()
    _wait_for(lambda: not runner.is_running, app)
    assert form.description_input.toPlainText() == "Current draft"