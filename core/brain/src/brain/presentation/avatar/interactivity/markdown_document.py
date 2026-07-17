# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Semantic Markdown preparation shared by avatar presentation backends."""
from __future__ import annotations

import re
from html import escape


def _normalize_plain_markdown(text: str) -> str:
    """Normalize human-authored layout without rewriting fenced or inline code."""
    source = text.replace(r"\r\n", "\n").replace(r"\n", "\n").replace(r"\r", "\n")
    source = re.sub(r"(?<!\n)[ \t]+(?=(?:[-+*]|\d+[.)])\s+)", "\n", source)
    paragraphs = re.split(r"(\n\s*\n)", source)
    return "".join(
        _implicit_enumeration(paragraph) if index % 2 == 0 else paragraph
        for index, paragraph in enumerate(paragraphs)
    )


def _implicit_enumeration(paragraph: str) -> str:
    """Project an unambiguous comma enumeration of four or more items as a list."""
    stripped = paragraph.strip()
    if not stripped or stripped.startswith(("#", ">", "-", "*", "+", "<", "![")):
        return paragraph
    prefix, separator, candidate = stripped.partition(":")
    if not separator:
        prefix, candidate = "", stripped
    items = [item.strip() for item in candidate.split(",")]
    if len(items) < 4 or any(not item or len(item) > 80 for item in items):
        return paragraph
    rendered = "\n".join(f"- {item}" for item in items)
    replacement = f"{prefix.strip()}:\n\n{rendered}" if prefix else rendered
    return paragraph.replace(stripped, replacement)


def normalize_avatar_markdown(text: str) -> str:
    """Apply layout normalization only outside fenced and inline code spans."""
    fenced_parts = re.split(r"(```[\s\S]*?```)", text)
    for index in range(0, len(fenced_parts), 2):
        inline_parts = re.split(r"(`[^`\n]*`)", fenced_parts[index])
        for inline_index in range(0, len(inline_parts), 2):
            inline_parts[inline_index] = _normalize_plain_markdown(inline_parts[inline_index])
        fenced_parts[index] = "".join(inline_parts)
    return "".join(fenced_parts)


def expand_avatar_images(text: str) -> str:
    """Convert extended Markdown image dimensions into safe HTML image tags."""
    pattern = re.compile(r'!\[([^\]]*)\]\(([^\s)]+)(?:\s+"[^"]*")?\)\{([^}]*)\}')

    def replace_image(match: re.Match[str]) -> str:
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


def avatar_markdown_source(text: str, emotion_prefix: str = "") -> str:
    """Convert bracket-delimited narrative into styled Markdown blockquotes."""
    source = expand_avatar_images(normalize_avatar_markdown(text)).strip()
    blocks: list[str] = []
    cursor = 0
    prefix = emotion_prefix.strip()
    narrative_pattern = r"(?<!!)\[([^\[\]]+)\](?!\s*(?:\(|\[))"
    for match in re.finditer(narrative_pattern, source, flags=re.DOTALL):
        dialogue = source[cursor:match.start()].strip()
        if dialogue:
            blocks.append(dialogue)
        narrative = " ".join(match.group(1).split())
        if narrative:
            marker = f"{prefix} " if prefix and not blocks else ""
            blocks.append(f"> *{marker}{narrative}*")
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
    """Return contrast-safe Markdown styling for one supported avatar theme."""
    dark = mode == "dark"
    text = "#f9edf5" if dark else "#211522"
    heading = "#fff6fb" if dark else "#251326"
    muted = "#dec5d5" if dark else "#60445a"
    surface = "#302532" if dark else "#f2e4ed"
    border = "#a96b91" if dark else "#765568"
    link = "#ff9bd3" if dark else "#78124e"
    return f"""
body {{ color: {text}; font-family: Arial, sans-serif; font-size: 12pt; line-height: 1.35; }}
h1 {{ color: {heading}; font-size: 22pt; margin: 4px 0 16px 0; }}
h2 {{ color: {heading}; font-size: 17pt; margin: 20px 0 10px 0; padding-bottom: 5px; border-bottom: 2px solid #f062b7; }}
h3, h4, h5, h6 {{ color: {heading}; margin: 17px 0 8px 0; padding-bottom: 4px; border-bottom: 1px solid #d990b8; }}
p {{ margin: 0 0 12px 0; }}
blockquote {{ color: {muted}; font-style: italic; margin: 8px 0 14px 12px; padding-left: 12px; border-left: 3px solid #d94e9f; }}
table {{ border-collapse: collapse; margin: 8px 0 18px 0; border: 2px solid {border}; }}
th {{ color: {text}; background: {surface}; font-weight: 700; padding: 8px; border: 2px solid {border}; }}
td {{ color: {text}; padding: 8px; border: 2px solid {border}; }}
pre {{ color: {text}; background: {surface}; border: 1px solid {border}; margin: 8px 0 16px 0; padding: 10px; white-space: pre-wrap; }}
code {{ color: {link}; font-family: Consolas, monospace; background: {surface}; }}
a {{ color: {link}; font-weight: 700; text-decoration: underline; }}
ul, ol {{ margin-top: 5px; margin-bottom: 14px; }}
li {{ margin-bottom: 5px; }}
""".strip()


AVATAR_DOCUMENT_CSS = avatar_document_css()
