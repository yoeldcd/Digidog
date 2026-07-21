# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Build a speech-safe projection from visually rich Markdown messages."""

from __future__ import annotations

import re


FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
TABLE_DIVIDER_PATTERN = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
TABLE_ROW_PATTERN = re.compile(r"^\s*\|?.+\|.+\|?\s*$")
EMOJI_CHARACTER_PATTERN = re.compile(
    r"[#*0-9]\ufe0f?\u20e3"
    r"|[\U0001F1E6-\U0001F1FF]"
    r"|[\U0001F300-\U0001FAFF]"
    r"|[\u2300-\u23FF]"
    r"|[\u2600-\u27BF]"
    r"|[\u2B00-\u2BFF]"
    r"|[\u200D\uFE0E\uFE0F]"
)

ESCAPED_PREFIX_CONTROLS = {
    "\a": "a",
    "\b": "b",
    "\t": "t",
    "\v": "v",
    "\f": "f",
}


def normalize_avatar_message_text(source: str) -> str:
    """Repair escaped word prefixes and remove unsafe C0 controls.

    Python and JSON producers can accidentally materialize sequences such as
    ``\\thinking`` or ``\\application`` as a tab or bell character followed by
    the remainder of the word. Those controls create visual gaps and invalid
    SSML. A mnemonic control immediately followed by a letter is restored to
    its source letter; other controls become a space while line breaks remain
    intact.

    Args:
        source: Rich avatar message received from any producer.

    Returns:
        Text safe for Markdown rendering, narration, and persistence.
    """
    normalized: list[str] = []
    for index, character in enumerate(source):
        if character in {"\n", "\r"}:
            normalized.append(character)
            continue
        replacement = ESCAPED_PREFIX_CONTROLS.get(character)
        next_character = source[index + 1] if index + 1 < len(source) else ""
        if replacement and next_character.isalpha():
            normalized.append(replacement)
            continue
        normalized.append(" " if ord(character) < 32 else character)
    return "".join(normalized)


def markdown_text_for_speech(source: str) -> str:
    """
    Project Markdown into narration while retaining semantic prose.

    Fenced and indented code, tables, images, and raw URLs are visual-only.
    Headings, quotations, lists, emphasis, links, and bracketed narrative remain
    narrable after their presentation markers have been removed.

    Args:
        source: Original Markdown message shown by the avatar.

    Returns:
        A compact plain-text narration suitable for text-to-speech.
    """
    text = _normalize_legacy_line_breaks(_unwrap_legacy_dialogue(normalize_avatar_message_text(source)))
    lines = text.splitlines()
    table_lines = _table_line_indexes(lines)
    spoken_lines: list[str] = []
    active_fence = ""

    for index, line in enumerate(lines):
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            active_fence = "" if active_fence == marker else marker
            continue
        if active_fence or index in table_lines or line.startswith(("    ", "\t")):
            continue
        narrated = _narratable_inline_text(line)
        if narrated:
            spoken_lines.append(narrated)

    return re.sub(r"\s+", " ", " ".join(spoken_lines)).strip()


def _normalize_legacy_line_breaks(source: str) -> str:
    """Decode escaped line breaks left by legacy shell argument transport."""
    return source.replace(r"\r\n", "\n").replace(r"\n", "\n").replace(r"\r", "\n")


def _unwrap_legacy_dialogue(source: str) -> str:
    """Remove only the historical full-message avatar envelope."""
    match = re.fullmatch(
        r"\s*@[A-Za-z0-9_-]+[^.]*\.\*\*[^*]+\*\*\s*\([^)]+\)\s*\[(?P<body>.*)\]\s*",
        source,
        flags=re.DOTALL,
    )
    return match.group("body") if match else source


def _table_line_indexes(lines: list[str]) -> set[int]:
    """Identify complete pipe-table blocks from their required divider row."""
    indexes: set[int] = set()
    for index, line in enumerate(lines):
        if not TABLE_DIVIDER_PATTERN.match(line):
            continue
        if index > 0 and TABLE_ROW_PATTERN.match(lines[index - 1]):
            indexes.add(index - 1)
        indexes.add(index)
        cursor = index + 1
        while cursor < len(lines) and TABLE_ROW_PATTERN.match(lines[cursor]):
            indexes.add(cursor)
            cursor += 1
    return indexes


def _narratable_inline_text(line: str) -> str:
    """Strip Markdown presentation syntax from one narrable source line."""
    text = line.strip()
    inline_code: list[str] = []

    def retain_inline_code(match: re.Match[str]) -> str:
        inline_code.append(match.group(1))
        return f"\ufff0{len(inline_code) - 1}\ufff1"

    if not text or re.fullmatch(r"(?:[-*_]\s*){3,}", text):
        return ""
    text = re.sub(r"<img\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"!\[[^\]]*\]\[[^\]]*\]", "", text)
    text = re.sub(r"`+([^`]*)`+", retain_inline_code, text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"^\s{0,3}>+\s?", "", text)
    text = re.sub(r"^\s*(?:[-+*]|\d+[.)])\s+", "", text)
    text = re.sub(r"^\s*\[[ xX]\]\s+", "", text)
    text = re.sub(r"\[([^\]]+)\]", r"\1", text)
    text = re.sub(r"[*_~]+", "", text)
    for index, content in enumerate(inline_code):
        text = text.replace(f"\ufff0{index}\ufff1", content)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = EMOJI_CHARACTER_PATTERN.sub("", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()
