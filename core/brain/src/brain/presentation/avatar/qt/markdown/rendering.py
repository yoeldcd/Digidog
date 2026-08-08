"""Shared Qt Markdown document rendering orchestration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QUrl

from brain.presentation.avatar.interactivity.markdown_document import avatar_markdown_source
from brain.presentation.avatar.qt.markdown.document import (
    AvatarTextBrowser,
    RenderedMarkdown,
    _qt_image_markdown,
)


class StyledMarkdownHost(Protocol):
    """Narrow styling surface consumed by the shared renderer."""

    document_view: AvatarTextBrowser

    def _normalize_inline_typography(self) -> None:
        """Normalize inline typography styling across rendered document blocks.

        Returns:
            None.
        """
        ...

    def _apply_semantic_highlighting(self) -> None:
        """Apply theme-matched semantic highlighting to code and quote elements.

        Returns:
            None.
        """
        ...

    def _apply_image_dimensions(self, dimensions: dict[str, tuple[int | None, int | None]]) -> None:
        """Constrain rendered inline images to their explicit pixel or percentage dimensions.

        Args:
            dimensions (dict[str, tuple[int | None, int | None]]): Image resource URLs mapped to width/height.

        Returns:
            None.
        """
        ...

    def _format_tables(self) -> None:
        """Format rendered HTML tables with consistent cell padding and borders.

        Returns:
            None.
        """
        ...



def render_avatar_markdown(
    host: StyledMarkdownHost,
    text: str,
    consumer_path: str = "",
) -> RenderedMarkdown:
    """Render avatar-normalized Markdown through one shared Qt styling pipeline.

    Args:
        host (StyledMarkdownHost): Target styling host providing document view and styling hooks.
        text (str): Raw Markdown source text.
        consumer_path (str): Optional file path used to resolve relative resource URLs.

    Returns:
        RenderedMarkdown: Rendered result containing normalized Markdown and image dimensions.
    """
    if consumer_path:
        base_path = Path(consumer_path).expanduser()
        if base_path.is_file():
            base_path = base_path.parent
        host.document_view.document().setBaseUrl(
            QUrl.fromLocalFile(str(base_path.resolve()) + os.sep),
        )

    rendered = _qt_image_markdown(avatar_markdown_source(text))
    host.document_view.setMarkdown(rendered.markdown)
    host._normalize_inline_typography()
    host._apply_semantic_highlighting()
    host._apply_image_dimensions(rendered.image_dimensions)
    host._format_tables()

    return rendered

