"""Semantic Markdown preparation shared by avatar presentation backends."""
from __future__ import annotations

import re


def avatar_markdown_source(text: str, emotion_prefix: str = "") -> str:
    """Convert bracket-delimited narrative into styled Markdown blockquotes."""
    source = text.strip()
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


AVATAR_DOCUMENT_CSS = """
body { color: #211522; font-family: Arial, sans-serif; font-size: 12pt; line-height: 1.35; }
h1 { color: #251326; font-size: 22pt; margin: 4px 0 16px 0; }
h2 { color: #32162d; font-size: 17pt; margin: 20px 0 10px 0; padding-bottom: 5px; border-bottom: 2px solid #d94e9f; }
h3, h4, h5, h6 { color: #3b1933; margin: 17px 0 8px 0; padding-bottom: 4px; border-bottom: 1px solid #d990b8; }
p { margin: 0 0 12px 0; }
blockquote { color: #60445a; font-style: italic; margin: 8px 0 14px 12px; padding-left: 12px; border-left: 3px solid #d94e9f; }
table { border-collapse: collapse; margin: 8px 0 18px 0; border: 2px solid #765568; }
th { color: #211522; background: #f1d9e9; font-weight: 700; padding: 8px; border: 2px solid #765568; }
td { color: #2b1b29; padding: 8px; border: 2px solid #876a7a; }
pre { color: #211522; background: #f2e4ed; border: 1px solid #c49aae; margin: 8px 0 16px 0; padding: 10px; white-space: pre-wrap; }
code { color: #6f164e; font-family: Consolas, monospace; background: #f2e4ed; }
a { color: #8c1760; text-decoration: underline; }
ul, ol { margin-top: 5px; margin-bottom: 14px; }
li { margin-bottom: 5px; }
""".strip()
