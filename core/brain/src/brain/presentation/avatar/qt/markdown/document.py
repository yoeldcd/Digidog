# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt Markdown normalization, image resources, and semantic token helpers.

File: core/brain/src/brain/presentation/avatar/qt/markdown/document.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from urllib.request import Request, urlopen

from PySide6.QtCore import QSize, QUrl
from PySide6.QtGui import QFont, QImage, QTextDocument
from PySide6.QtWidgets import QTextBrowser


UNBOUNDED_WIDGET_HEIGHT: Final[int] = 16_777_215
"""Qt canonical maximum dimension used only for vertically detached bubbles."""


@dataclass(frozen=True)
class SemanticTokenPattern:
    """Immutable Data Transfer Object for a semantic token pattern specification.

    Attributes:
        name: Unique token identifier (e.g. 'square', 'path', 'color').
        pattern: Regular expression pattern string.
        weight: Target PySide6 QFont weight for matching spans.
        description: Human-readable description of the captured syntax.
    """

    name: str
    pattern: str
    weight: QFont.Weight
    description: str


SEMANTIC_TOKEN_PATTERNS: Final[dict[str, SemanticTokenPattern]] = {
    "color": SemanticTokenPattern(
        name="color",
        pattern=(
            r"(?:●\s*)?(?:#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b"
            r"|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)"
            r"|hsla?\(\s*\d+\s*,\s*\d+%\s*,\s*\d+%\s*(?:,\s*[\d.]+\s*)?\))"
        ),
        weight=QFont.Weight.Medium,
        description="Color notations e.g. #382a14, rgb(255,0,0), hsl(120,50%,50%)",
    ),
    "angle": SemanticTokenPattern(
        name="angle",
        pattern=r"</?[A-Za-z][A-Za-z0-9_-]*(?:\s+[^>\r\n\u2028\u2029]*)?>",
        weight=QFont.Weight.DemiBold,
        description="Angle bracket HTML/XML tags e.g. <tag> or </tag>",
    ),
    "square": SemanticTokenPattern(
        name="square",
        pattern=r"\[[^\[\]\r\n\u2028\u2029]*\]",
        weight=QFont.Weight.DemiBold,
        description="Square bracket containers e.g. [text]",
    ),
    "round": SemanticTokenPattern(
        name="round",
        pattern=r"\([^()\r\n\u2028\u2029]*\)",
        weight=QFont.Weight.Medium,
        description="Parenthesized expressions e.g. (text)",
    ),
    "curly": SemanticTokenPattern(
        name="curly",
        pattern=r"\{[^{}\r\n\u2028\u2029]*\}",
        weight=QFont.Weight.DemiBold,
        description="Curly brace blocks e.g. {key: value}",
    ),
    "path": SemanticTokenPattern(
        name="path",
        pattern=r"(?<!\w)(?:\./|/|\\|[a-zA-Z]:[/\\])?[\w.\$@+-]+(?:[/\\][\w.\$@+-]+)+[/\\]?",
        weight=QFont.Weight.DemiBold,
        description="File and directory paths e.g. ./path/file.py",
    ),
    "upper": SemanticTokenPattern(
        name="upper",
        pattern=r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b",
        weight=QFont.Weight.Bold,
        description="UPPER_SNAKE_CASE constants e.g. MAX_SIZE",
    ),
    "snake": SemanticTokenPattern(
        name="snake",
        pattern=r"(?<!\w)_?[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?!\w)",
        weight=QFont.Weight.Medium,
        description="snake_case identifiers e.g. var_name",
    ),
    "camel": SemanticTokenPattern(
        name="camel",
        pattern=r"\b[a-z][a-z0-9]*(?:[A-Z][A-Za-z0-9]*)+\b",
        weight=QFont.Weight.Medium,
        description="camelCase identifiers e.g. functionName",
    ),
    "pascal": SemanticTokenPattern(
        name="pascal",
        pattern=r"\b[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+\b",
        weight=QFont.Weight.DemiBold,
        description="PascalCase class names e.g. UserProfile",
    ),
    "kebab": SemanticTokenPattern(
        name="kebab",
        pattern=r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b",
        weight=QFont.Weight.Medium,
        description="kebab-case identifiers e.g. option-flag",
    ),
    "code_id": SemanticTokenPattern(
        name="code_id",
        pattern=r"\b[A-Za-z]+[0-9]+\b",
        weight=QFont.Weight.Medium,
        description="Alphanumeric record IDs e.g. rec19, t720",
    ),
    "version": SemanticTokenPattern(
        name="version",
        pattern=r"\b[vV]?\d+(?:\.\d+)+(?:-[a-zA-Z0-9.]+)?\b",
        weight=QFont.Weight.DemiBold,
        description="Semantic version numbers e.g. v1.0.5",
    ),
    "number": SemanticTokenPattern(
        name="number",
        pattern=r"(?:\b[\$€£¥]?|[\$€£¥])\d+(?:[.,]\d+)*(?!\w)",
        weight=QFont.Weight.DemiBold,
        description="Numeric values and currency e.g. 100, $50.00",
    ),
    "math": SemanticTokenPattern(
        name="math",
        pattern=r"[=+\u2212\-\u00d7\u00f7\u2260\u2264\u2265\u2211\u221a\u221e\u2248\u00b1\u2202\u2206\u03c0%<>!]",
        weight=QFont.Weight.Bold,
        description="Math operators, comparison signs, and isolated symbols e.g. =, +, -, <, >, !, %, √",
    ),
}
"""Dictionary of semantic token DTOs keyed by token name."""


_CONTAINER_TOKENS: Final[frozenset[str]] = frozenset({"square", "round", "curly"})
"""Tokens whose matched range is transparent: child tokens can refine sub-ranges inside."""


@dataclass(frozen=True)
class RenderedMarkdown:
    """Immutable value object holding normalized markdown text and image dimensions.

    Attributes:
        markdown: Normalized markdown text suitable for Qt document setMarkdown.
        image_dimensions: Map of image URLs to requested (width, height) bounds.
    """

    markdown: str
    image_dimensions: dict[str, tuple[int | None, int | None]]


def table_column_percentages(headers: list[str]) -> list[float]:
    """Allocate most table width to semantic content columns.

    Args:
        headers: Header text names for each table column.

    Returns:
        list[float]: Percentage widths allocated for each column.
    """

    if not headers:
        return []

    content_names = {
        "content",
        "content|entity",
        "entity",
        "tarea",
        "task",
        "texto",
        "detalle",
        "description",
    }

    content_indexes = {
        index
        for index, header in enumerate(headers)
        if header.strip().casefold() in content_names
    }

    if not content_indexes:
        content_indexes = {len(headers) - 1}

    if len(headers) == len(content_indexes):
        return [100.0 / len(headers)] * len(headers)

    content_total = 64.0
    metadata_total = 100.0 - content_total

    column_widths = [
        content_total / len(content_indexes)
        if index in content_indexes
        else metadata_total / (len(headers) - len(content_indexes))
        for index in range(len(headers))
    ]

    return column_widths


def semantic_token_ranges(text: str) -> list[tuple[str, int, int, QFont.Weight]]:
    """Return recursive semantic ranges for one rendered text block.

    Container tokens (square, round, curly) claim their range but remain
    transparent: leaf tokens can match and refine sub-ranges inside them.
    Leaf tokens are opaque and block further matches within their span.

    Args:
        text: Plain text from one Qt document block.

    Returns:
        list[tuple[str, int, int, QFont.Weight]]: Ordered tuples containing
            token name, start, length, and font weight.
    """

    opaque_ranges: list[tuple[int, int]] = []
    ranges: list[tuple[str, int, int, QFont.Weight]] = []

    for dto in SEMANTIC_TOKEN_PATTERNS.values():

        is_container = dto.name in _CONTAINER_TOKENS

        for match in re.finditer(dto.pattern, text):

            start, end = match.span()

            if any(start < oe and end > os for os, oe in opaque_ranges):
                continue

            ranges.append((dto.name, start, end - start, dto.weight))

            if not is_container:
                opaque_ranges.append((start, end))

    sorted_ranges = sorted(ranges, key=lambda item: item[1])

    return sorted_ranges


def _qt_image_markdown(source: str) -> RenderedMarkdown:
    """Translate HTML image tags into Qt Markdown plus bounded dimension metadata.

    Args:
        source: Raw Markdown source text containing HTML or Markdown image tags.

    Returns:
        RenderedMarkdown: Rendered result containing normalized Markdown and image dimensions.
    """

    dimensions: dict[str, tuple[int | None, int | None]] = {}

    def replace_image(match: re.Match[str]) -> str:
        """Translate one HTML image tag to Markdown and retain dimensions.

        Args:
            match: Regular-expression match for an image element.

        Returns:
            str: Qt-compatible Markdown image token.
        """

        attributes = {
            name.lower(): value
            for name, _quote, value in re.findall(
                r"(src|alt|width|height)\s*=\s*([\"\']?)([^\s>\"\']+)\2",
                match.group(1),
                flags=re.IGNORECASE,
            )
        }

        source_url = attributes.get("src", "").strip()

        if not source_url:
            return ""

        raw_width = attributes.get("width", "")
        raw_height = attributes.get("height", "")

        width = max(16, min(1200, int(raw_width))) if raw_width.isdigit() else None
        height = max(16, min(1200, int(raw_height))) if raw_height.isdigit() else None

        dimensions[source_url] = (width, height)

        markdown_url = source_url

        if re.match(r"^[A-Za-z]:[\\/]", source_url) or source_url.startswith("\\\\"):
            markdown_url = QUrl.fromLocalFile(source_url).toString()
            dimensions[markdown_url] = (width, height)

        alt_text = attributes.get("alt", "image") or "image"

        return f"![{alt_text}]({markdown_url})"

    markdown = re.sub(r"<img\s+([^>]+)>", replace_image, source, flags=re.IGNORECASE)

    return RenderedMarkdown(markdown=markdown, image_dimensions=dimensions)


def normalized_image_size(
    intrinsic: QSize,
    requested: tuple[int | None, int | None],
    viewport: QSize,
    zoom_factor: float = 1.0,
) -> QSize:
    """Fit an image into requested bounds and viewport without distortion.

    Args:
        intrinsic: Natural image size.
        requested: Optional width and height.
        viewport: Available document viewport.
        zoom_factor: Current document zoom multiplier.

    Returns:
        QSize: Bounded aspect-preserving render size.
    """

    natural_width = max(1, intrinsic.width())
    natural_height = max(1, intrinsic.height())

    requested_width, requested_height = requested

    width_limit = requested_width or natural_width
    height_limit = requested_height or natural_height

    base_scale = min(width_limit / natural_width, height_limit / natural_height)
    desired_scale = max(0.1, base_scale * max(0.1, zoom_factor))

    viewport_width = max(1, viewport.width())
    viewport_height = max(1, viewport.height())
    viewport_scale = min(viewport_width / natural_width, viewport_height / natural_height)

    scale = min(desired_scale, viewport_scale)

    fitted_width = max(1, round(natural_width * scale))
    fitted_height = max(1, round(natural_height * scale))

    return QSize(fitted_width, fitted_height)


class AvatarTextBrowser(QTextBrowser):
    """Resolve bounded local and remote image resources for avatar Markdown.

    Attributes:
        MAX_IMAGE_BYTES: Maximum allowed byte size for HTTP image resource downloads.
    """

    MAX_IMAGE_BYTES: Final[int] = 100 * 1024 * 1024

    def loadResource(self, resource_type: int, name: QUrl) -> object:  # noqa: N802 - Qt API
        """Load image resources without allowing arbitrary navigation.

        Args:
            resource_type: Qt document resource type integer identifier.
            name: Resource locator URL.

        Returns:
            object: Decoded image resource or base-class resource value.
        """

        if resource_type != QTextDocument.ResourceType.ImageResource:
            return super().loadResource(resource_type, name)

        scheme = name.scheme().lower()

        if scheme in {"http", "https", "ftp", "data"}:

            try:
                request_url = name.toString()
                headers = {"User-Agent": "Codex-Dog-Avatar/1.0"}
                request = Request(request_url, headers=headers)

                with urlopen(request, timeout=5) as response:
                    payload = response.read(self.MAX_IMAGE_BYTES + 1)

                if len(payload) <= self.MAX_IMAGE_BYTES:
                    image = QImage.fromData(payload)

                    if not image.isNull():
                        return image

            except (OSError, ValueError):
                return QImage()

        if scheme in {"", "file"} or (len(scheme) == 1 and name.toString()[1:3] in {":/", ":\\"}):

            path = name.toLocalFile() if scheme == "file" else name.toString()
            image = QImage(path)

            if not image.isNull():
                return image

        return super().loadResource(resource_type, name)
