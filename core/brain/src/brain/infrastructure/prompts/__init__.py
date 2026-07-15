"""Markdown prompt template loader for knowledge LLM stages."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent
"""Directory that stores prompt templates shipped with the brain package."""

DEFAULT_STAGE_PROMPT = "consolidation"
"""Fallback stage prompt used when a stage-specific template is absent."""


def get_stage_system_prompt(stage_name: str) -> str:
    """
    Return the system prompt section for a stage.

    Args:
        stage_name (str): Knowledge stage name.

    Returns:
        str: System prompt text.
    """
    return _extract_section(
        template_text=_load_template(_stage_template_name(stage_name=stage_name)),
        heading="System Prompt",
    )


def get_stage_prompt_template_path(stage_name: str) -> Path:
    """
    Return the Markdown prompt template path used by a stage.

    Args:
        stage_name (str): Knowledge stage name.

    Returns:
        Path: Absolute prompt template path.
    """
    return PROMPT_DIR / _stage_template_name(stage_name=stage_name)


def render_stage_prompt(stage_name: str, values: dict[str, str]) -> str:
    """
    Render the common delta prompt with a stage-specific Markdown template.

    Args:
        stage_name (str): Knowledge stage name.
        values (dict[str, str]): Prompt placeholder values.

    Returns:
        str: Rendered user prompt.
    """
    stage_template: str = _load_template(_stage_template_name(stage_name=stage_name))
    stage_values: dict[str, str] = {
        "stage_system_prompt": _extract_section(stage_template, "System Prompt"),
        "stage_objective": _extract_section(stage_template, "Stage Objective"),
        "stage_output_policy": _extract_section(stage_template, "Stage Output Policy"),
    }
    render_values: dict[str, str] = {
        **values,
        **{
            key: _render_template(template_text=value, values=values)
            for key, value in stage_values.items()
        },
    }
    return _render_template(
        template_text=_load_template("common_delta.md"),
        values=render_values,
    ).strip()


def _stage_template_name(stage_name: str) -> str:
    """
    Return the prompt filename for a stage.

    Args:
        stage_name (str): Knowledge stage name.

    Returns:
        str: Prompt filename.
    """
    candidate_name = f"{stage_name}.md"
    if (PROMPT_DIR / candidate_name).exists():
        return candidate_name
    return f"{DEFAULT_STAGE_PROMPT}.md"


def _load_template(template_name: str) -> str:
    """
    Load one Markdown prompt template.

    Args:
        template_name (str): Template filename.

    Returns:
        str: Template text.
    """
    return (PROMPT_DIR / template_name).read_text(encoding="utf-8")


def _extract_section(template_text: str, heading: str) -> str:
    """
    Extract a second-level Markdown heading section.

    Args:
        template_text (str): Source Markdown.
        heading (str): Heading title without hashes.

    Returns:
        str: Section body.
    """
    marker = f"## {heading}"
    start_index = template_text.find(marker)
    if start_index < 0:
        return ""
    body_start = template_text.find("\n", start_index)
    if body_start < 0:
        return ""
    next_heading = template_text.find("\n## ", body_start + 1)
    if next_heading < 0:
        return template_text[body_start + 1 :].strip()
    return template_text[body_start + 1 : next_heading].strip()


def _render_template(template_text: str, values: dict[str, str]) -> str:
    """
    Render simple double-brace placeholders.

    Args:
        template_text (str): Template with `{{placeholder}}` tokens.
        values (dict[str, str]): Replacement values.

    Returns:
        str: Rendered template.
    """
    rendered_text: str = template_text
    for key, value in values.items():
        rendered_text = rendered_text.replace(f"{{{{{key}}}}}", str(value))
    return rendered_text
