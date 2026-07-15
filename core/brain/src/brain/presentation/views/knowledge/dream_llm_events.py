"""LLM event line renderers for knowledge dream diagnostics."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.presentation.views.knowledge.diagnostic_formatting import counts_text, field, live_text, number, schema_text


def render_llm_event_lines(event_payload: dict[str, Any]) -> list[str]:
    """
    Render structured LLM diagnostics using compact terminal syntax.

    Args:
        event_payload (dict[str, Any]): Structured event emitted by the LLM client.

    Returns:
        list[str]: Rendered log lines.
    """
    event_name: str = str(event_payload.get("event") or "llm")
    if event_name == "stage_start":
        return render_llm_start_event(event_payload=event_payload)
    if event_name == "http_response":
        return render_llm_http_event(event_payload=event_payload)
    if event_name == "stage_success":
        return render_llm_success_event(event_payload=event_payload)
    if event_name == "stage_error":
        return render_llm_error_event(event_payload=event_payload)
    return [f"__DIM__[llm:event]__RESET__ {live_text(event_name)}"]


def render_llm_start_event(event_payload: dict[str, Any]) -> list[str]:
    """
    Render a model stage start event.

    Args:
        event_payload (dict[str, Any]): Structured start event.

    Returns:
        list[str]: Rendered log lines.
    """
    prior_counts: dict[str, int] = event_payload.get("prior_delta_counts", {})
    return [
        (
            "__MAGENTA__[llm:start]__RESET__ "
            f"{field('stage')} {schema_text(event_payload.get('stage'))} "
            f"{field('provenance')} {live_text(event_payload.get('source_path'))} "
            f"{field('model')} {live_text(event_payload.get('model'))}"
        ),
        (
            f"    {field('input')} "
            f"source_chars {number(event_payload.get('source_chars', 0))}  "
            f"prompt_chars {number(event_payload.get('prompt_chars', 0))}  "
            f"graph_context_chars {number(event_payload.get('graph_context_chars', 0))}  "
            f"prior {counts_text(prior_counts)}"
        ),
        (
            f"    {field('request')} "
            f"endpoint {live_text(event_payload.get('base_url'))}  "
            f"temperature {number(event_payload.get('temperature', 0))}  "
            f"max_tokens {number(event_payload.get('max_tokens', 0))}"
        ),
        f"    {field('prompt_template')} {live_text(event_payload.get('prompt_template_path'))}",
    ]


def render_llm_http_event(event_payload: dict[str, Any]) -> list[str]:
    """
    Render an HTTP response event.

    Args:
        event_payload (dict[str, Any]): Structured HTTP response event.

    Returns:
        list[str]: Rendered log lines.
    """
    return [
        (
            "__CYAN__[llm:http]__RESET__ "
            f"{field('stage')} {schema_text(event_payload.get('stage'))} "
            f"{field('status')} {number(event_payload.get('status'))} "
            f"{field('response_chars')} {number(event_payload.get('response_chars', 0))} "
            f"{field('elapsed_ms')} {number(event_payload.get('elapsed_ms', 0))}"
        ),
    ]


def render_llm_success_event(event_payload: dict[str, Any]) -> list[str]:
    """
    Render a model stage success event.

    Args:
        event_payload (dict[str, Any]): Structured success event.

    Returns:
        list[str]: Rendered log lines.
    """
    delta_counts: dict[str, int] = event_payload.get("delta_counts", {})
    output_text: Any = event_payload.get("output_text") or event_payload.get("output_preview")
    return [
        (
            "__GREEN__[llm:success]__RESET__ "
            f"{field('stage')} {schema_text(event_payload.get('stage'))} "
            f"{field('delta')} {counts_text(delta_counts)} "
            f"{field('output_chars')} {number(event_payload.get('output_chars', 0))} "
            f"{field('elapsed_ms')} {number(event_payload.get('elapsed_ms', 0))}"
        ),
        f"    {field('output')} {live_text(output_text)}",
    ]


def render_llm_error_event(event_payload: dict[str, Any]) -> list[str]:
    """
    Render a model stage error event.

    Args:
        event_payload (dict[str, Any]): Structured error event.

    Returns:
        list[str]: Rendered log lines.
    """
    lines: list[str] = [
        (
            "__RED__[llm:error]__RESET__ "
            f"{field('stage')} {schema_text(event_payload.get('stage'))} "
            f"{field('provenance')} {live_text(event_payload.get('source_path'))} "
            f"{field('elapsed_ms')} {number(event_payload.get('elapsed_ms', 0))}"
        ),
        f"    {field('error')} {live_text(event_payload.get('error'))}",
    ]
    output_text: Any = event_payload.get("output_text") or event_payload.get("output_preview")
    if output_text:
        lines.append(f"    {field('output')} {live_text(output_text)}")
    return lines
