"""Pinned markdown-it-py parsing and source-bounded Markdown structure facts."""

from __future__ import annotations

from dataclasses import dataclass

from markdown_it import MarkdownIt


@dataclass(frozen=True, slots=True)
class MarkdownParseResult:
    """Describe parsed Markdown tokens and prose-friendly structural counts.

    Attributes:
        syntax_valid: Whether Markdown parsing completed without an unclosed fence.
        token_types: Immutable markdown-it token type names in source order.
        token_lines: Immutable zero-independent one-based token start lines.
        heading_count: Number of heading-open tokens.
        list_count: Number of ordered and bullet list-open tokens.
        table_count: Number of table-open tokens.
        fence_count: Number of parsed fenced code blocks.
        html_count: Number of HTML block or inline tokens.
        comment_count: Number of HTML comment markers in source.
        unclosed_fence_lines: Opening lines for fences without a matching close.
        line_count: Number of source lines.
        error_kind: Bounded syntax classification, when invalid.
        structure_valid: Whether parsing produced a structurally usable token stream.
        compactness_valid: Whether required blank-line separation is present.
        missing_blank_before_headings: Heading lines missing a preceding blank line.
        missing_blank_after_headings: Heading lines missing a following blank line.
        missing_blank_before_lists: List lines missing a preceding blank line.
        missing_blank_after_lists: List lines missing a following blank line.
        missing_blank_before_tables: Table lines missing a preceding blank line.
        missing_blank_after_tables: Table lines missing a following blank line.
        missing_blank_before_fences: Fence lines missing a preceding blank line.
        missing_blank_after_fences: Fence lines missing a following blank line.
        missing_blank_before_thematic_breaks: Thematic-break lines missing a preceding blank line.
        missing_blank_after_thematic_breaks: Thematic-break lines missing a following blank line.
        adjacent_block_lines: Adjacent top-level block line pairs without separation.
    """

    syntax_valid: bool
    token_types: tuple[str, ...]
    token_lines: tuple[int, ...]
    heading_count: int
    list_count: int
    table_count: int
    fence_count: int
    html_count: int
    comment_count: int
    unclosed_fence_lines: tuple[int, ...]
    line_count: int
    error_kind: str | None
    structure_valid: bool = True
    compactness_valid: bool = True
    missing_blank_before_headings: tuple[int, ...] = ()
    missing_blank_after_headings: tuple[int, ...] = ()
    missing_blank_before_lists: tuple[int, ...] = ()
    missing_blank_after_lists: tuple[int, ...] = ()
    missing_blank_before_tables: tuple[int, ...] = ()
    missing_blank_after_tables: tuple[int, ...] = ()
    missing_blank_before_fences: tuple[int, ...] = ()
    missing_blank_after_fences: tuple[int, ...] = ()
    missing_blank_before_thematic_breaks: tuple[int, ...] = ()
    missing_blank_after_thematic_breaks: tuple[int, ...] = ()
    adjacent_block_lines: tuple[tuple[int, int], ...] = ()

    @property
    def missing_separation_lines(self) -> tuple[int, ...]:
        """Return immutable line numbers participating in compactness findings.

        Args:
            No arguments are accepted beyond the result instance.

        Returns:
            tuple[int, ...]: Sorted unique one-based source lines with findings.
        """
        lines = self.missing_blank_before_headings
        lines += self.missing_blank_after_headings
        lines += self.missing_blank_before_lists
        lines += self.missing_blank_after_lists
        lines += self.missing_blank_before_tables
        lines += self.missing_blank_after_tables
        lines += self.missing_blank_before_fences
        lines += self.missing_blank_after_fences
        lines += self.missing_blank_before_thematic_breaks
        lines += self.missing_blank_after_thematic_breaks
        adjacent_lines = tuple(
            line for pair in self.adjacent_block_lines for line in pair
        )

        return tuple(sorted(set(lines + adjacent_lines)))


class MarkdownParser:
    """Parse Markdown through the pinned markdown-it-py CommonMark engine."""

    def __init__(self) -> None:
        """Initialize an HTML-aware CommonMark parser with table support.

        Args:
            No arguments are accepted beyond the parser instance.
        """
        parser = MarkdownIt(
            "commonmark", {"html": True, "linkify": False, "typographer": False}
        )
        parser.enable("table")
        self._markdown = parser

    def parse(self, content: str) -> MarkdownParseResult:
        """Parse Markdown and summarize token/line structure in memory.

        Args:
            content: Complete Markdown source text.

        Returns:
            MarkdownParseResult: Immutable token facts and fence diagnostics.
        """
        tokens = self._markdown.parse(content)
        token_types = tuple(token.type for token in tokens)
        token_lines = tuple((token.map[0] + 1) if token.map else 1 for token in tokens)
        unclosed = _unclosed_fences(content)
        heading_count = token_types.count("heading_open")
        list_count = token_types.count("bullet_list_open") + token_types.count(
            "ordered_list_open"
        )
        table_count = token_types.count("table_open")
        fence_count = token_types.count("fence")
        html_count = token_types.count("html_block") + token_types.count("html_inline")
        comment_count = min(content.count("<!--"), 10000)

        line_count = max(1, len(content.splitlines()))
        separation = _separation_facts(content, tokens, line_count)
        compactness_valid = not any(separation.values())

        return MarkdownParseResult(
            syntax_valid=not unclosed,
            token_types=token_types,
            token_lines=token_lines,
            heading_count=heading_count,
            list_count=list_count,
            table_count=table_count,
            fence_count=fence_count,
            html_count=html_count,
            comment_count=comment_count,
            unclosed_fence_lines=unclosed,
            line_count=line_count,
            error_kind="unclosed_fence" if unclosed else None,
            structure_valid=not unclosed,
            compactness_valid=compactness_valid,
            **separation,
        )


def _unclosed_fences(content: str) -> tuple[int, ...]:
    """Find fenced blocks left open after markdown-it tokenization.

    This is a narrow structural check; Markdown grammar itself is delegated to
    markdown-it-py. Only opening/closing fence delimiters are inspected here.

    Args:
        content: Complete Markdown source text held in memory.

    Returns:
        tuple[int, ...]: Opening lines for fences without matching closes.
    """
    active_char: str | None = None
    active_length = 0
    opening_lines: list[int] = []

    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.lstrip(" ")
        indentation = len(line) - len(stripped)

        if indentation > 3:
            continue

        if len(stripped) < 3:
            continue
        marker = stripped[0]

        if marker not in "`~":
            continue
        marker_length = 0

        while marker_length < len(stripped) and stripped[marker_length] == marker:
            marker_length += 1

        if marker_length < 3:
            continue

        if active_char is None:
            active_char = marker
            active_length = marker_length
            opening_lines.append(line_number)

            continue
        remainder = stripped[marker_length:]

        if (
            marker == active_char
            and marker_length >= active_length
            and not remainder.strip()
        ):
            active_char = None
            active_length = 0
            opening_lines.pop()

    return tuple(opening_lines)


@dataclass(frozen=True, slots=True)
class _MarkdownBlock:
    """Represent one top-level Markdown block span using one-based lines.

    Attributes:
        kind: Stable block category emitted by the parser.
        start: One-based first source line occupied by the block.
        end: One-based last non-blank source line occupied by the block.
    """

    kind: str
    start: int
    end: int


_SEPARATION_KINDS = frozenset(
    {
        "heading",
        "list",
        "fence",
        "thematic_break",
        "table",
    }
)
_BLOCK_KINDS = frozenset(
    {
        "heading",
        "list",
        "fence",
        "thematic_break",
        "paragraph",
        "table",
        "blockquote",
        "html",
    }
)
_KIND_FIELDS = {
    "heading": ("missing_blank_before_headings", "missing_blank_after_headings"),
    "list": ("missing_blank_before_lists", "missing_blank_after_lists"),
    "table": ("missing_blank_before_tables", "missing_blank_after_tables"),
    "fence": ("missing_blank_before_fences", "missing_blank_after_fences"),
    "thematic_break": (
        "missing_blank_before_thematic_breaks",
        "missing_blank_after_thematic_breaks",
    ),
}


def _separation_facts(
    content: str,
    tokens: tuple[object, ...] | list[object],
    line_count: int,
) -> dict[str, object]:
    """Collect bounded blank-line facts from top-level markdown-it blocks.

    Args:
        content: Complete Markdown source held in memory.
        tokens: markdown-it token sequence in source order.
        line_count: One-based source line count.

    Returns:
        dict[str, object]: Immutable tuples keyed by parse-result field names.
    """
    lines = content.splitlines() or [""]
    blocks = tuple(
        _trim_trailing_blank_lines(block, lines) for block in _top_level_blocks(tokens)
    )
    findings: dict[str, list[int]] = {
        field: [] for fields in _KIND_FIELDS.values() for field in fields
    }

    for block in blocks:
        fields = _KIND_FIELDS.get(block.kind)

        if fields is None or _nested_source_line(lines, block.start):
            continue

        before_field, after_field = fields

        if block.start > 1 and not _blank_line(lines, block.start - 1):
            findings[before_field].append(block.start)

        if block.end < line_count and not _blank_line(lines, block.end + 1):
            findings[after_field].append(block.end)

    adjacent: list[tuple[int, int]] = []

    for previous, current in zip(blocks, blocks[1:]):
        if current.start != previous.end + 1:
            continue

        if previous.kind not in _BLOCK_KINDS or current.kind not in _BLOCK_KINDS:
            continue

        if previous.kind not in _SEPARATION_KINDS and current.kind not in _SEPARATION_KINDS:
            continue

        if _nested_source_line(lines, current.start):
            continue

        adjacent.append((previous.end, current.start))

    return {
        **{field: tuple(values) for field, values in findings.items()},
        "adjacent_block_lines": tuple(adjacent),
    }


def _top_level_blocks(
    tokens: tuple[object, ...] | list[object],
) -> tuple[_MarkdownBlock, ...]:
    """Return source-spanning top-level block tokens in stable order.

    Args:
        tokens: markdown-it token sequence.

    Returns:
        tuple[_MarkdownBlock, ...]: Immutable block spans with no nested tokens.
    """
    blocks: list[_MarkdownBlock] = []
    token_kinds = {
        "heading_open": "heading",
        "bullet_list_open": "list",
        "ordered_list_open": "list",
        "fence": "fence",
        "hr": "thematic_break",
        "paragraph_open": "paragraph",
        "table_open": "table",
        "blockquote_open": "blockquote",
        "html_block": "html",
    }

    for token in tokens:
        token_type = getattr(token, "type", None)
        token_map = getattr(token, "map", None)
        token_level = getattr(token, "level", None)

        if token_level != 0 or token_type not in token_kinds or not token_map:
            continue

        start, end = token_map
        blocks.append(
            _MarkdownBlock(
                kind=token_kinds[token_type],
                start=start + 1,
                end=max(start + 1, end),
            )
        )

    return tuple(blocks)


def _blank_line(lines: list[str], line_number: int) -> bool:
    """Return whether one one-based source line is blank.

    Args:
        lines: Source lines held in memory.
        line_number: One-based line number to inspect.

    Returns:
        bool: Whether the selected source line contains no non-whitespace text.
    """

    return not lines[line_number - 1].strip()


def _trim_trailing_blank_lines(
    block: _MarkdownBlock,
    lines: list[str],
) -> _MarkdownBlock:
    """Exclude blank lines absorbed into a markdown-it block's source map.

    Args:
        block: Parsed top-level block span.
        lines: One-based source lines.

    Returns:
        _MarkdownBlock: Span ending on the last non-blank source line.
    """
    end = block.end

    while end > block.start and _blank_line(lines, end):
        end -= 1

    return _MarkdownBlock(kind=block.kind, start=block.start, end=end)


def _nested_source_line(lines: list[str], line_number: int) -> bool:
    """Return whether a block begins inside blockquote context.

    Args:
        lines: Source lines held in memory.
        line_number: One-based line number to inspect.

    Returns:
        bool: Whether blockquote syntax indicates a nested block.
    """

    line = lines[line_number - 1]
    stripped = line.lstrip(" ")

    return stripped.startswith(">")


__all__ = ["MarkdownParseResult", "MarkdownParser"]
