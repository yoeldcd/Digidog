# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Semantic Markdown preparation shared by avatar presentation backends."""
from __future__ import annotations

import re
from html import escape

AVATAR_BASE_FONT_POINTS = 13.0

_EMBEDDED_FILE_BLOCK = re.compile(
    r'<!-- avatar-file:start name="([^"]*)" -->\s*(.*?)\s*<!-- avatar-file:end -->',
    flags=re.DOTALL,
)


def render_embedded_file_blocks(text: str) -> str:
    """Render explicit avatar file markers as bounded Markdown attachments.

    Args:
        text (str): Avatar Markdown containing file markers.

    Returns:
        str: Markdown with file markers rendered as quoted attachments.
    """

    def replace_file(match: re.Match[str]) -> str:
        """Render one matched file marker as a quoted attachment.

        Args:
            match (re.Match[str]): Marker match with name and content groups.

        Returns:
            str: Bounded Markdown attachment block.
        """
        name = match.group(1).strip() or "Attached file"
        content = match.group(2).strip()
        narrated_heading = f"## 📎 {name}"
        if content.startswith(narrated_heading):
            content = content[len(narrated_heading):].lstrip()
        quoted_content = "\n".join(">" if not line else f"> {line}" for line in content.splitlines())
        suffix = f"\n{quoted_content}" if quoted_content else ""
        return f"---\n\n> **📎 {name}**{suffix}\n\n---"

    return _EMBEDDED_FILE_BLOCK.sub(replace_file, text)


def _normalize_plain_markdown(text: str) -> str:
    """Normalize human-authored layout without rewriting fenced or inline code.

    Args:
        text (str): Plain Markdown segment outside code spans.

    Returns:
        str: Normalized plain Markdown segment.
    """
    source = text.replace("\r\n", "\n").replace("\r", "\n").replace(r"\r\n", "\n").replace(r"\n", "\n")
    source = re.sub(r"\*\*\s+([^\*\n]+?)\s*\*\*", r"**\1**", source)
    paragraphs = re.split(r"(\n\s*\n)", source)
    return "".join(
        _implicit_enumeration(paragraph) if index % 2 == 0 else paragraph
        for index, paragraph in enumerate(paragraphs)
    )


def _implicit_enumeration(paragraph: str) -> str:
    """Project one labelled, single-line comma enumeration as a list.

    Args:
        paragraph (str): Candidate paragraph to inspect.

    Returns:
        str: Original or list-formatted paragraph.
    """
    stripped = paragraph.strip()
    if not stripped or "\n" in stripped or stripped.startswith(("#", ">", "-", "*", "+", "<", "![")) or re.match(r"^\d+[\.\)]", stripped):
        return paragraph
    prefix, separator, candidate = stripped.partition(":")
    if not separator:
        return paragraph
    items = [item.strip() for item in candidate.split(",")]
    if len(items) < 4 or any(not item for item in items):
        return paragraph
    trailing_sentence = ""
    sentence_boundary = re.search(
        r"(?<=[.!?])\s+(?=[A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1\u00dc\u00bf\u00a1])",
        items[-1],
    )
    if sentence_boundary:
        trailing_sentence = items[-1][sentence_boundary.end():].strip()
        items[-1] = items[-1][:sentence_boundary.start()].strip()
    if any(len(item) > 80 for item in items):
        return paragraph
    rendered = "\n".join(f"- {item}" for item in items)
    replacement = f"{prefix.strip()}:\n\n{rendered}" if prefix else rendered
    if trailing_sentence:
        replacement = f"{replacement}\n\n{trailing_sentence}"
    return paragraph.replace(stripped, replacement)


def normalize_avatar_markdown(text: str) -> str:
    """Normalize avatar Markdown outside fenced and inline code spans.

    Args:
        text (str): Source avatar Markdown.

    Returns:
        str: Layout-normalized Markdown.
    """
    fenced_parts = re.split(r"(```[\s\S]*?```)", text)
    for index in range(0, len(fenced_parts), 2):
        inline_parts = re.split(r"(`[^`\n]*`)", fenced_parts[index])
        for inline_index in range(0, len(inline_parts), 2):
            inline_parts[inline_index] = _normalize_plain_markdown(inline_parts[inline_index])
        fenced_parts[index] = "".join(inline_parts)
    return "".join(fenced_parts)


def expand_avatar_images(text: str) -> str:
    """Convert extended Markdown image dimensions into safe HTML tags.

    Args:
        text (str): Source Markdown with optional image dimensions.

    Returns:
        str: Markdown with validated extended images expanded to HTML.
    """
    pattern = re.compile(r'!\[([^\]]*)\]\(([^\s)]+)(?:\s+"[^"]*")?\)\{([^}]*)\}')

    def replace_image(match: re.Match[str]) -> str:
        """Render one extended Markdown image match as safe HTML.

        Args:
            match (re.Match[str]): Regular-expression match containing image text,
                source URL, and optional dimensions.

        Returns:
            str: Escaped HTML ``img`` element with bounded dimensions.
        """
        attributes = dict(
            re.findall(r"(width|height)\s*=\s*(?:\"|')?(\d{1,4})(?:px)?(?:\"|')?", match.group(3))
        )
        dimensions = " ".join(
            f'{name}="{max(16, min(1200, int(value)))}"'
            for name, value in attributes.items()
        )
        suffix = f" {dimensions}" if dimensions else ""
        return f'<img src="{escape(match.group(2), quote=True)}" alt="{escape(match.group(1), quote=True)}"{suffix}>'

    return pattern.sub(replace_image, text)


def _convert_fenced_code_blocks(text: str) -> str:
    """Convert fenced Markdown code blocks to safe pre/code HTML blocks.

    Args:
        text (str): Source Markdown text with optional fenced code blocks.

    Returns:
        str: Markdown text with fenced code blocks converted to pre/code HTML.
    """
    pattern = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\n([\s\S]*?)```", flags=re.MULTILINE)

    def replace_block(match: re.Match[str]) -> str:
        code_content = match.group(1).rstrip()
        escaped_code = escape(code_content)
        return f"\n\n<pre><code>{escaped_code}</code></pre>\n\n"

    return pattern.sub(replace_block, text)


def _format_color_references(text: str) -> str:
    """Format hex, RGB, and HSL color references outside fenced blocks as dot-prefixed color chips.

    Args:
        text (str): Source Markdown text.

    Returns:
        str: Markdown text with color references prefixed by a color dot indicator.
    """
    pattern = re.compile(
        r"```[\s\S]*?```|((?<!●\s)(?<!●)"
        r"(?:#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b"
        r"|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)"
        r"|hsla?\(\s*\d+\s*,\s*\d+%\s*,\s*\d+%\s*(?:,\s*[\d.]+\s*)?\)))",
        flags=re.IGNORECASE,
    )
    return pattern.sub(
        lambda m: m.group(0) if m.group(0).startswith("```") else f"● {m.group(0)}",
        text,
    )


def avatar_markdown_source(text: str, emotion_prefix: str = "") -> str:
    """Convert standalone bracket narratives into quoted Markdown blockquotes.

    Args:
        text (str): Source avatar Markdown.
        emotion_prefix (str): Optional leading emotion narration prefix.

    Returns:
        str: Markdown source ready for backend rendering.
    """
    source = _format_color_references(
        expand_avatar_images(normalize_avatar_markdown(render_embedded_file_blocks(text)))
    ).strip()
    source = _convert_fenced_code_blocks(source)
    blocks: list[str] = []
    cursor = 0
    prefix = emotion_prefix.strip()
    narrative_pattern = r"^[ \t]*\[([^\[\]\n]+)\][ \t]*(?!\()"
    for match in re.finditer(narrative_pattern, source, flags=re.MULTILINE):
        dialogue = source[cursor:match.start()].strip()
        if dialogue:
            blocks.append(dialogue)
        narrative = " ".join(match.group(1).split())
        if narrative:
            marker = f"{prefix} " if prefix and not blocks else ""
            blocks.append(f'> *{marker}{narrative}*')
            prefix = ""
        cursor = match.end()
    remainder = source[cursor:].strip()
    if remainder:
        marker = f"{prefix} " if prefix and not blocks else ""
        blocks.append(f"{marker}{remainder}")
        prefix = ""
    if not blocks and prefix:
        blocks.append(prefix)
    markdown = "\n\n".join(blocks)
    return re.sub(r"^(#{2,6}\s+.+)$", r"\1\n\n---", markdown, flags=re.MULTILINE)


def avatar_document_css(mode: str = "light") -> str:
    """Build contrast-safe Markdown styling for an avatar theme.

    Args:
        mode (str): ``light`` or ``dark`` theme identifier.

    Returns:
        str: CSS document stylesheet.
    """
    dark = mode == "dark"
    text = "#f9edf5" if dark else "#211522"
    heading = "#fff6fb" if dark else "#251326"
    muted = "#dec5d5" if dark else "#60445a"
    surface = "#2c1c2e" if dark else "#f2e4ed"
    pre_bg = "#38243b" if dark else "#ebd5e6"
    pre_text = "#ffb0de" if dark else "#6b0a43"
    pre_border = "#a96b91" if dark else "#765568"
    code_bg = "#1b2b45" if dark else "#dbeafe"
    code_text = "#93c5fd" if dark else "#1e40af"
    table_border = "#a96b91" if dark else "#765568"
    link = "#ff9bd3" if dark else "#78124e"
    return f"""
body {{ color: {text}; font-family: Arial, sans-serif; font-size: {AVATAR_BASE_FONT_POINTS:g}pt; line-height: 1.4; }}
h1 {{ color: {heading}; font-size: 22pt; margin: 4px 0 16px 0; }}
h2 {{ color: {heading}; font-size: 17pt; margin: 20px 0 10px 0; padding-bottom: 5px; border-bottom: 2px solid #f062b7; }}
h3, h4, h5, h6 {{ color: {heading}; margin: 17px 0 8px 0; padding-bottom: 4px; border-bottom: 1px solid #d990b8; }}
p {{ margin: 0 0 12px 0; }}
blockquote {{ color: {muted}; font-style: italic; margin: 8px 0 14px 12px; padding-left: 12px; border-left: 3px solid #d94e9f; }}
table {{ border-collapse: collapse; margin: 8px 0 18px 0; border: 2px solid {table_border}; }}
th {{ color: {text}; background: {surface}; font-weight: 700; padding: 8px; border: 2px solid {table_border}; }}
td {{ color: {text}; padding: 8px; border: 2px solid {table_border}; }}
pre {{ color: {pre_text}; background: {pre_bg}; border: 1px solid {pre_border}; margin: 8px 0 16px 0; padding: 10px; white-space: pre-wrap; }}
code {{ color: {code_text}; font-family: Consolas, monospace; background: {code_bg}; padding: 2px 4px; }}
a {{ color: {link}; font-weight: 700; text-decoration: underline; }}
ul, ol {{ margin-top: 5px; margin-bottom: 14px; }}
li {{ margin-bottom: 5px; }}
""".strip()


AVATAR_DOCUMENT_CSS = avatar_document_css()
