# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt Markdown typography, semantic styling, tables, and images.

File: core/brain/src/brain/presentation/avatar/qt/markdown/styling.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QFont,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFrameFormat,
    QTextLength,
    QTextTable,
)

from brain.presentation.avatar.interactivity.markdown_document import AVATAR_BASE_FONT_POINTS
from brain.presentation.avatar.qt.markdown.document import (
    _CONTAINER_TOKENS,
    normalized_image_size,
    semantic_token_ranges,
    table_column_percentages,
)


@dataclass(frozen=True)
class QtSemanticPalette:
    """Typed semantic palette contract containing hex colors for Markdown tokens.

    Attributes:
        path: Hex color for filesystem path tokens.
        square: Hex color for square bracket tokens.
        round: Hex color for round parenthesis tokens.
        curly: Hex color for curly brace tokens.
        number: Hex color for numeric tokens.
        camel: Hex color for camelCase tokens.
        pascal: Hex color for PascalCase tokens.
        snake: Hex color for snake_case tokens.
        upper: Hex color for CONSTANT/UPPER tokens.
        kebab: Hex color for kebab-case tokens.
        code_id: Hex color for alphanumeric code tokens (e.g. rec19, t720).
        version: Hex color for version string tokens (e.g. v1.0.5).
        math: Hex color for math symbol tokens.
        list: Hex color for bullet list tokens.
        heading: Hex color for heading text.
        bold: Hex color for bold text.
        code_text: Hex foreground for inline code fragments.
        code_bg: Hex background for inline code fragments.
        square_bg: Hex background for square bracket containers.
        round_bg: Hex background for round parenthesis containers.
        curly_bg: Hex background for curly brace containers.
        color: Hex color for color preview dot text.
        color_bg: Hex background color for color preview container.
        angle: Hex color for angle bracket HTML/XML tag tokens.
    """

    path: str
    square: str
    round: str
    curly: str
    number: str
    camel: str
    pascal: str
    snake: str
    upper: str
    kebab: str
    code_id: str
    version: str
    math: str
    list: str
    heading: str
    bold: str
    code_text: str
    code_bg: str
    square_bg: str
    round_bg: str
    curly_bg: str
    color: str
    color_bg: str
    angle: str

    def __getitem__(self, key: str) -> str:
        """Allow subscript access for token color lookup.

        Args:
            key: Semantic token or element name.

        Returns:
            str: Hex color string.
        """

        color_value: str = getattr(self, key)

        return color_value


def _parse_color_spec(spec: str) -> QColor:
    """Parse hex, RGB(A), or HSL(A) color strings into a Qt QColor object.

    Args:
        spec: Color specification text.

    Returns:
        QColor: Valid QColor object or invalid QColor when unparseable.
    """

    raw = spec.strip()

    if raw.startswith("#"):

        if len(raw) == 4:
            raw = f"#{raw[1]*2}{raw[2]*2}{raw[3]*2}"

        elif len(raw) == 5:
            raw = f"#{raw[1]*2}{raw[2]*2}{raw[3]*2}{raw[4]*2}"

        return QColor(raw)

    rgba_match = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)",
        raw,
        flags=re.IGNORECASE,
    )

    if rgba_match:

        r = int(rgba_match.group(1))
        g = int(rgba_match.group(2))
        b = int(rgba_match.group(3))
        alpha = 255

        if rgba_match.group(4) is not None:
            val = float(rgba_match.group(4))
            alpha = int(val * 255) if val <= 1.0 else int(val)

        return QColor.fromRgb(r, g, b, max(0, min(255, alpha)))

    hsla_match = re.match(
        r"hsla?\(\s*(\d+)\s*,\s*(\d+)%\s*,\s*(\d+)%(?:\s*,\s*([\d.]+))?\s*\)",
        raw,
        flags=re.IGNORECASE,
    )

    if hsla_match:

        h = int(hsla_match.group(1))
        s_pct = int(hsla_match.group(2))
        l_pct = int(hsla_match.group(3))
        alpha = 255

        if hsla_match.group(4) is not None:
            val = float(hsla_match.group(4))
            alpha = int(val * 255) if val <= 1.0 else int(val)

        return QColor.fromHslF(h / 360.0, s_pct / 100.0, l_pct / 100.0, max(0.0, min(1.0, alpha / 255.0)))

    return QColor()


class QtDocumentStylingMixin:
    """Mixin providing document typography, semantic colors, images, and tables for Qt."""

    def _normalize_inline_typography(self) -> None:
        """Keep Markdown spans on the same font family as their surrounding text.

        Returns:
            None.
        """

        document = self.document_view.document()
        block = document.begin()

        while block.isValid():

            fragments = []
            iterator = block.begin()

            while not iterator.atEnd():

                fragment = iterator.fragment()

                if fragment.isValid() and not fragment.charFormat().isImageFormat():
                    fragments.append(fragment)

                iterator += 1

            point_sizes = [
                fragment.charFormat().font().pointSizeF()
                for fragment in fragments
                if fragment.charFormat().font().pointSizeF() > 0
            ]
            block_point_size = max(AVATAR_BASE_FONT_POINTS, max(point_sizes, default=0.0))

            for fragment in fragments:

                char_format = fragment.charFormat()
                char_format.setFontFamilies(["Arial"])
                char_format.setFontPointSize(block_point_size)

                cursor = QTextCursor(document)
                cursor.setPosition(fragment.position())
                cursor.setPosition(
                    fragment.position() + fragment.length(),
                    QTextCursor.MoveMode.KeepAnchor,
                )
                cursor.mergeCharFormat(char_format)

            block = block.next()

    def _semantic_palette(self) -> QtSemanticPalette:
        """Return accessible token colors matched to the active bubble theme.

        Returns:
            QtSemanticPalette: Typed palette contract containing token colors.
        """

        if self._theme_mode == "dark":
            return QtSemanticPalette(
                path="#ffd27f",
                square="#ff9bd3",
                round="#8fdcff",
                curly="#ffd27f",
                number="#a8e6a3",
                camel="#d7b5ff",
                pascal="#f5a9ff",
                snake="#7ee7d6",
                upper="#ffbf8f",
                kebab="#9fc7ff",
                code_id="#7ee7d6",
                version="#8fdcff",
                math="#ffd166",
                list="#9fc7ff",
                heading="#fff6fb",
                bold="#ffffff",
                code_text="#93c5fd",
                code_bg="#1b2b45",
                square_bg="#3d1d2e",
                round_bg="#14283b",
                curly_bg="#382a14",
                color="#f9edf5",
                color_bg="#252830",
                angle="#8fdcff",
            )

        return QtSemanticPalette(
            path="#8a5200",
            square="#a31969",
            round="#075f8f",
            curly="#8a5200",
            number="#276b25",
            camel="#6532a3",
            pascal="#8a247c",
            snake="#087466",
            upper="#a34408",
            kebab="#245f9f",
            code_id="#087466",
            version="#075f8f",
            math="#8a6200",
            list="#245f9f",
            heading="#35152d",
            bold="#21101d",
            code_text="#1e40af",
            code_bg="#dbeafe",
            square_bg="#fce4ec",
            round_bg="#e0f2fe",
            curly_bg="#fff3e0",
            color="#211522",
            color_bg="#e2e4ea",
            angle="#075f8f",
        )

    def _merge_text_format(
        self,
        start: int,
        length: int,
        color: str,
        weight: QFont.Weight | None = None,
        bg_color: str | None = None,
    ) -> None:
        """Merge a semantic foreground and optional background into one document range.

        Args:
            start: Document character start index.
            length: Range length in characters.
            color: Hex color string.
            weight: Optional font weight override.
            bg_color: Optional hex background color string.

        Returns:
            None.
        """

        if length <= 0:
            return

        char_format = QTextCharFormat()
        char_format.setForeground(QColor(color))

        if bg_color:
            char_format.setBackground(QColor(bg_color))

        if weight is not None:
            char_format.setFontWeight(weight)

        cursor = QTextCursor(self.document_view.document())
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        cursor.mergeCharFormat(char_format)

    def _apply_semantic_highlighting(self) -> None:
        """Apply two-level semantic styling: fragment-level first, token-level second.

        Level 1 (fragment-level): Code backgrounds, headings, and bold formatting
        are applied from Qt's parsed font metadata. Code fragments are opaque
        and fully protected from Level 2 overwrite. Headings and bold are
        transparent containers that allow Level 2 tokens inside.

        Level 2 (token-level): Regex-based semantic tokens (path, snake_case, etc.)
        are applied only to character ranges not claimed by opaque Level 1 fragments.

        Returns:
            None.
        """

        document = self.document_view.document()

        if document.isEmpty():
            return

        colors = self._semantic_palette()
        block = document.begin()

        while block.isValid():

            block_text = block.text()

            if block_text.strip():

                block_start = block.position()
                protected_ranges: list[tuple[int, int]] = []
                iterator = block.begin()

                while not iterator.atEnd():

                    fragment = iterator.fragment()

                    if fragment.isValid() and not fragment.charFormat().isImageFormat():
                        font = fragment.charFormat().font()
                        frag_start = fragment.position() - block_start
                        frag_end = frag_start + fragment.length()
                        is_heading = font.pointSizeF() >= 14 and font.weight() >= QFont.Weight.DemiBold
                        is_bold = font.weight() >= QFont.Weight.Bold
                        is_code = font.family() in ("Courier New", "Consolas", "Monospace", "monospace")

                        if is_code:
                            self._merge_text_format(
                                fragment.position(),
                                fragment.length(),
                                colors["code_text"],
                                bg_color=colors["code_bg"],
                            )
                            protected_ranges.append((frag_start, frag_end))

                        elif is_heading or is_bold:
                            highlight_key = "heading" if is_heading else "bold"
                            self._merge_text_format(
                                fragment.position(),
                                fragment.length(),
                                colors[highlight_key],
                            )

                    iterator += 1

                entity_ranges = [m.span() for m in re.finditer(r"&[a-zA-Z0-9#]+;", block_text)]

                for token, start, length, weight in semantic_token_ranges(block_text):

                    end = start + length

                    if any(start >= es and end <= ee for es, ee in entity_ranges):
                        continue

                    if any(start < pe and end > ps for ps, pe in protected_ranges):
                        continue

                    if token == "color":
                        matched_text = block_text[start:end]
                        spec_match = re.search(
                            r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"
                            r"|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)"
                            r"|hsla?\(\s*\d+\s*,\s*\d+%\s*,\s*\d+%\s*(?:,\s*[\d.]+\s*)?\)",
                            matched_text,
                            flags=re.IGNORECASE,
                        )

                        if spec_match:
                            raw_spec = spec_match.group(0)
                            dot_color = _parse_color_spec(raw_spec)

                            if dot_color.isValid():
                                dot_offset = matched_text.find(raw_spec)

                                if dot_offset > 0:
                                    self._merge_text_format(
                                        block_start + start,
                                        dot_offset,
                                        dot_color,
                                        weight=weight,
                                        bg_color=colors["color_bg"],
                                    )
                                    self._merge_text_format(
                                        block_start + start + dot_offset,
                                        length - dot_offset,
                                        colors["color"],
                                        weight=weight,
                                        bg_color=colors["color_bg"],
                                    )

                                else:
                                    self._merge_text_format(
                                        block_start + start,
                                        length,
                                        colors["color"],
                                        weight=weight,
                                        bg_color=colors["color_bg"],
                                    )

                                continue

                    bg_color = colors[f"{token}_bg"] if token in _CONTAINER_TOKENS else None

                    self._merge_text_format(
                        block_start + start,
                        length,
                        colors[token],
                        weight,
                        bg_color=bg_color,
                    )

            block = block.next()

    def _requested_image_dimensions(
        self,
        resolved: tuple[int | None, int | None],
        viewport: QSize,
    ) -> tuple[int | None, int | None]:
        """Return author-requested image dimensions before common fitting.

        Hosts can override this protected variation point to supply bounds for
        otherwise-unrequested images. The default preserves natural-size image
        behavior used by shared avatar Markdown surfaces.

        Args:
            resolved: Width and height explicitly requested by Markdown, if any.
            viewport: Current maximum render bounds for the image.

        Returns:
            tuple[int | None, int | None]: Requested dimensions passed to the
            shared aspect-fit calculation.
        """

        del viewport

        return resolved

    def _apply_image_dimensions(self, dimensions: dict[str, tuple[int | None, int | None]]) -> None:
        """Center and fit every rendered image inside the message viewport.

        Args:
            dimensions: Requested image dimension map.

        Returns:
            None.
        """

        viewport = self._image_viewport_size()
        zoom_factor = 1.2 ** self._zoom_step
        block = self.document_view.document().begin()

        while block.isValid():

            iterator = block.begin()

            while not iterator.atEnd():

                fragment = iterator.fragment()
                image_format = fragment.charFormat().toImageFormat()

                if fragment.isValid() and image_format.isValid():

                    image_name = image_format.name()

                    resolved = next(
                        (
                            value
                            for source, value in dimensions.items()
                            if image_name == source or image_name.endswith(source)
                        ),
                        (None, None),
                    )

                    resource = self.document_view.document().resource(
                        QTextDocument.ResourceType.ImageResource,
                        QUrl(image_name),
                    )

                    intrinsic = resource.size() if resource is not None and hasattr(resource, "size") else QSize()

                    if intrinsic.isEmpty():
                        fallback_width = round(image_format.width()) or resolved[0] or viewport.width()
                        fallback_height = round(image_format.height()) or resolved[1] or viewport.height()
                        intrinsic = QSize(fallback_width, fallback_height)

                    requested = self._requested_image_dimensions(resolved, viewport)
                    fitted = normalized_image_size(intrinsic, requested, viewport, zoom_factor)

                    image_format.setWidth(fitted.width())
                    image_format.setHeight(fitted.height())

                    block_format = block.blockFormat()
                    block_format.setAlignment(Qt.AlignmentFlag.AlignCenter)

                    block_cursor = QTextCursor(block)
                    block_cursor.setBlockFormat(block_format)

                    if fitted.isValid():
                        cursor = QTextCursor(self.document_view.document())
                        cursor.setPosition(fragment.position())
                        cursor.setPosition(
                            fragment.position() + fragment.length(),
                            QTextCursor.MoveMode.KeepAnchor,
                        )
                        cursor.setCharFormat(image_format)

                iterator += 1

            block = block.next()

    def _image_viewport_size(self) -> QSize:
        """Return the largest image layer that remains wholly inside the bubble.

        Returns:
            QSize: Usable viewport bounds for embedded images.
        """

        if self.layout():
            self.layout().activate()

        document_margin = round(self.document_view.document().documentMargin() * 2)
        layout_margins = self.layout().contentsMargins() if self.layout() else None

        horizontal_margins = layout_margins.left() + layout_margins.right() if layout_margins else 64
        width = max(48, self.width() - horizontal_margins - document_margin)

        vertical_margins = layout_margins.top() + layout_margins.bottom() if layout_margins else 48
        fixed_widgets = (self.header, self.footer, self.separator_a, self.separator_b)
        fixed_height = sum(widget.height() for widget in fixed_widgets)
        height = max(48, self.maximumHeight() - vertical_margins - fixed_height - 16)

        return QSize(width, height)

    def _format_tables(self) -> None:
        """Apply strong rules and align cells according to readable text length.

        Returns:
            None.
        """

        for frame in self.document_view.document().rootFrame().childFrames():

            if not isinstance(frame, QTextTable):
                continue

            table_format = frame.format()
            table_format.setBorder(2)
            table_format.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)

            headers: list[str] = []

            for column in range(frame.columns()):

                header_cell = frame.cellAt(0, column)
                header_cursor = header_cell.firstCursorPosition()
                header_probe = QTextCursor(header_cursor)

                header_probe.setPosition(
                    header_cell.lastCursorPosition().position(),
                    QTextCursor.MoveMode.KeepAnchor,
                )

                headers.append(header_probe.selectedText().strip())

            constraints = [
                QTextLength(QTextLength.Type.PercentageLength, percentage)
                for percentage in table_column_percentages(headers)
            ]

            table_format.setColumnWidthConstraints(constraints)
            table_format.setCellPadding(7)
            table_format.setCellSpacing(0)

            frame.setFormat(table_format)

            for row in range(frame.rows()):

                for column in range(frame.columns()):

                    cell = frame.cellAt(row, column)
                    cursor = cell.firstCursorPosition()
                    end = cell.lastCursorPosition().position()

                    probe = QTextCursor(cursor)
                    probe.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

                    cell_text_length = len(probe.selectedText().strip())

                    alignment = (
                        Qt.AlignmentFlag.AlignCenter
                        if cell_text_length <= 18
                        else Qt.AlignmentFlag.AlignLeft
                    )

                    while cursor.block().isValid() and cursor.position() <= end:

                        block_format = cursor.blockFormat()
                        block_format.setAlignment(alignment)
                        cursor.setBlockFormat(block_format)

                        if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                            break
