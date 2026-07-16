# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Callback builders for live knowledge dream diagnostics."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
from typing import Any, Callable

# Application Modules Imports
from brain.application.knowledge.pipeline.delta_events import ApplicationEventCallback
from brain.presentation.terminal import render_placeholders
from brain.presentation.views.knowledge.dream_application_events import render_application_event_lines
from brain.presentation.views.knowledge.dream_llm_events import render_llm_event_lines
from brain.presentation.views.knowledge.dream_orchestration_events import render_dream_event_lines


def resolve_llm_event_callback(
    args: argparse.Namespace,
    color_enabled: bool,
) -> Callable[[dict[str, Any]], None] | None:
    """
    Return an LLM event logger only for explicit verbose diagnostics.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        Callable[[dict[str, Any]], None] | None: Event logger when enabled.
    """
    if bool(getattr(args, "json", False)):
        return None
    if not bool(getattr(args, "verbose_log", False)):
        return None
    return build_llm_event_logger(color_enabled=color_enabled)


def resolve_application_event_callback(
    args: argparse.Namespace,
    color_enabled: bool,
) -> ApplicationEventCallback | None:
    """
    Return an application event logger only for explicit verbose diagnostics.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        ApplicationEventCallback | None: Event logger when enabled.
    """
    if bool(getattr(args, "json", False)):
        return None
    if not bool(getattr(args, "verbose_log", False)):
        return None
    return build_application_event_logger(color_enabled=color_enabled)


def resolve_orchestration_event_callback(
    args: argparse.Namespace,
    color_enabled: bool,
) -> Callable[[dict[str, Any]], None] | None:
    """
    Return a dream orchestration event logger only for explicit verbose diagnostics.

    Args:
        args (argparse.Namespace): Parsed command arguments.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        Callable[[dict[str, Any]], None] | None: Event logger when enabled.
    """
    if bool(getattr(args, "json", False)):
        return None
    if not bool(getattr(args, "verbose_log", False)):
        return None
    return build_dream_event_logger(color_enabled=color_enabled)


def build_application_event_logger(color_enabled: bool) -> ApplicationEventCallback:
    """
    Build a console logger for delta application events.

    Args:
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        ApplicationEventCallback: Event sink passed to application helpers.
    """
    def log_application_event(event_payload: dict[str, Any]) -> None:
        """
        Print one application event.

        Args:
            event_payload (dict[str, Any]): Structured event emitted by delta application.
        """
        for line in render_application_event_lines(event_payload=event_payload):
            print(render_placeholders(line, color_enabled), flush=True)

    return log_application_event


def build_llm_event_logger(color_enabled: bool) -> Callable[[dict[str, Any]], None]:
    """
    Build a console logger for live LLM execution events.

    Args:
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        Callable[[dict[str, Any]], None]: Event sink passed to the dream runner.
    """
    def log_llm_event(event_payload: dict[str, Any]) -> None:
        """
        Print one LLM execution event.

        Args:
            event_payload (dict[str, Any]): Structured event emitted by the LLM client.
        """
        for line in render_llm_event_lines(event_payload=event_payload):
            print(render_placeholders(line, color_enabled), flush=True)

    return log_llm_event


def build_dream_event_logger(color_enabled: bool) -> Callable[[dict[str, Any]], None]:
    """
    Build a console logger for source and orchestration events.

    Args:
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        Callable[[dict[str, Any]], None]: Event sink passed to the dream runner.
    """
    def log_dream_event(event_payload: dict[str, Any]) -> None:
        """
        Print one dream orchestration event.

        Args:
            event_payload (dict[str, Any]): Structured event emitted by dream orchestration.
        """
        for line in render_dream_event_lines(event_payload=event_payload):
            print(render_placeholders(line, color_enabled), flush=True)

    return log_dream_event
