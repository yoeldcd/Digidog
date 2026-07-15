"""Semantic framing for model-ready knowledge extraction inputs."""

from __future__ import annotations

# Standard Libraries Imports
import re

# Application Modules Imports
from brain.application.knowledge.models.dtos.sources import KnowledgeFrameDTO, SourceDTO


MAX_FRAME_BODY_CHARS = 14000
"""Maximum rendered frame body sent to model-backed stages."""

MAX_MARKDOWN_SECTIONS = 24
"""Maximum Markdown sections retained in a generic knowledge frame."""


def build_knowledge_frame(source_dto: SourceDTO, content: str) -> KnowledgeFrameDTO:
    """
    Convert raw source content into a semantic model input frame.

    Args:
        source_dto (SourceDTO): Source metadata kept by the harness.
        content (str): Raw source content.

    Returns:
        KnowledgeFrameDTO: Model-ready frame without filesystem metadata.
    """
    if source_dto.source_type in ("logs", "workspace_logs"):
        return _build_log_frame(content=content, source_type=source_dto.source_type)
    if source_dto.source_type == "diary":
        return _build_diary_frame(content=content, source_type=source_dto.source_type)
    return _build_markdown_frame(content=content, source_type=source_dto.source_type)


def render_knowledge_frame_for_llm(frame_dto: KnowledgeFrameDTO) -> str:
    """
    Render a knowledge frame as text for model-backed extraction.

    Args:
        frame_dto (KnowledgeFrameDTO): Semantic input frame.

    Returns:
        str: Model-ready text.
    """
    title_text: str = frame_dto.title.strip()
    lines: list[str] = [
        f"KNOWLEDGE_FRAME_KIND: {frame_dto.frame_kind}",
    ]
    if title_text:
        lines.append(f"TITLE: {title_text}")
    lines.extend(
        [
            "",
            "TEXT:",
            frame_dto.body.strip(),
        ],
    )
    return "\n".join(lines).strip()


def _build_log_frame(content: str, source_type: str) -> KnowledgeFrameDTO:
    """
    Build a frame from structured change log entries.

    Args:
        content (str): Raw log file content.
        source_type (str): Internal source family.

    Returns:
        KnowledgeFrameDTO: Change-record knowledge frame.
    """
    entries: list[str] = []
    entry_pattern = re.compile(
        r"##\s+(?P<timestamp>[^\n]+)\n"
        r"###\s+\((?P<domain>[^)]+)\)\s+\[(?P<title>[^\]]+)\]\n"
        r"(?P<body>.*?)(?=\n(?:---\n\n)?##\s+|\Z)",
        re.DOTALL,
    )
    for match in entry_pattern.finditer(content):
        body_fields: dict[str, str] = _extract_log_body_fields(body=match.group("body"))
        entries.append(
            "\n".join(
                [
                    "Change record:",
                    f"Domain: {_clean_text(match.group('domain'))}",
                    f"Title: {_clean_text(match.group('title'))}",
                    f"Type: {_clean_text(body_fields.get('type', ''))}",
                    f"Reason: {_clean_text(body_fields.get('why', ''))}",
                    f"Change: {_clean_text(body_fields.get('description', ''))}",
                    f"Impact: {_clean_text(body_fields.get('impact', ''))}",
                ],
            ),
        )
    if not entries:
        entries.append(_render_markdown_sections(content=content))
    body: str = _clip_text("\n\n".join(entries))
    return KnowledgeFrameDTO(
        frame_kind="change_log_records",
        title="Change log records",
        body=body,
        source_type=source_type,
        original_chars=len(content),
    )


def _build_diary_frame(content: str, source_type: str) -> KnowledgeFrameDTO:
    """
    Build a frame from diary records.

    Args:
        content (str): Raw diary Markdown content.
        source_type (str): Internal source family.

    Returns:
        KnowledgeFrameDTO: Diary-record knowledge frame.
    """
    entries: list[str] = []
    entry_pattern = re.compile(
        r"##\s+(?P<title>[^\n]+)\n(?P<body>.*?)(?=\n##\s+|\Z)",
        re.DOTALL,
    )
    for match in entry_pattern.finditer(content):
        entries.append(
            "\n".join(
                [
                    "Diary record:",
                    f"Title: {_clean_text(match.group('title'))}",
                    f"Narrative: {_clean_text(match.group('body'))}",
                ],
            ),
        )
    if not entries:
        entries.append(_render_markdown_sections(content=content))
    body: str = _clip_text("\n\n".join(entries))
    return KnowledgeFrameDTO(
        frame_kind="diary_records",
        title=_extract_markdown_title(content=content),
        body=body,
        source_type=source_type,
        original_chars=len(content),
    )


def _build_markdown_frame(content: str, source_type: str) -> KnowledgeFrameDTO:
    """
    Build a frame from generic Markdown memory content.

    Args:
        content (str): Raw Markdown content.
        source_type (str): Internal source family.

    Returns:
        KnowledgeFrameDTO: Generic knowledge-record frame.
    """
    title: str = _extract_markdown_title(content=content)
    body: str = _clip_text(_render_markdown_sections(content=content))
    return KnowledgeFrameDTO(
        frame_kind="knowledge_records",
        title=title,
        body=body,
        source_type=source_type,
        original_chars=len(content),
    )


def _extract_log_body_fields(body: str) -> dict[str, str]:
    """
    Extract structured log body fields.

    Args:
        body (str): Raw log entry body.

    Returns:
        dict[str, str]: Normalized field names to text.
    """
    field_matches = re.finditer(
        r"\*\*(?P<name>Type|Why|Description|Impact):?\*\*\s*(?P<value>.*?)(?=\n\s*\*\*|\Z)",
        body,
        re.DOTALL | re.IGNORECASE,
    )
    fields: dict[str, str] = {}
    for match in field_matches:
        key: str = match.group("name").casefold()
        fields[key] = _clean_text(match.group("value"))
    return fields


def _render_markdown_sections(content: str) -> str:
    """
    Render Markdown content as compact semantic sections.

    Args:
        content (str): Raw Markdown content.

    Returns:
        str: Compact section text.
    """
    content_without_code: str = re.sub(r"```.*?```", " ", content, flags=re.DOTALL)
    heading_pattern = re.compile(r"(?m)^(#{1,6})\s+(?P<title>.+)$")
    matches: list[re.Match[str]] = list(heading_pattern.finditer(content_without_code))
    if not matches:
        return _clean_text(content_without_code)

    sections: list[str] = []
    for index, match in enumerate(matches[:MAX_MARKDOWN_SECTIONS]):
        start_index: int = match.end()
        end_index: int = matches[index + 1].start() if index + 1 < len(matches) else len(content_without_code)
        title: str = _clean_text(match.group("title"))
        body: str = _clean_text(content_without_code[start_index:end_index])
        if body:
            sections.append(f"Section: {title}\nContent: {body}")
        else:
            sections.append(f"Section: {title}")
    return "\n\n".join(sections)


def _extract_markdown_title(content: str) -> str:
    """
    Extract the first Markdown heading.

    Args:
        content (str): Raw Markdown content.

    Returns:
        str: First heading or empty string.
    """
    match = re.search(r"(?m)^#\s+(.+)$", content)
    return _clean_text(match.group(1)) if match else ""


def _clip_text(text: str) -> str:
    """
    Bound frame text sent to the model.

    Args:
        text (str): Raw frame text.

    Returns:
        str: Bounded frame text.
    """
    clean_text: str = text.strip()
    if len(clean_text) <= MAX_FRAME_BODY_CHARS:
        return clean_text
    return clean_text[:MAX_FRAME_BODY_CHARS].rsplit(" ", 1)[0]


def _clean_text(text: str) -> str:
    """
    Normalize text for model-ready frames.

    Args:
        text (str): Raw text.

    Returns:
        str: Single-spaced text.
    """
    return " ".join(text.replace("\ufeff", "").split())
