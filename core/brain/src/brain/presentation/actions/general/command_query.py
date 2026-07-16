# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module for the global brain query command."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json

# Application Modules Imports
from brain.presentation.terminal import render_placeholders, log_step
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryDeepResponseDTO
from brain.application.querying.service import query_deep, query_global
from brain.presentation.views.query.results import print_human_deep_response, print_human_results




def handle(args: argparse.Namespace) -> int:
    """
    Execute a global query across knowledge and memory backends.

    Args:
        args (argparse.Namespace): Parsed command arguments.

    Returns:
        int: Process status code.
    """
    log_step(args, "Querying brain knowledge...")
    color_enabled: bool = getattr(args, "color", False)

    try:
        domain, query_text = _resolve_query_arguments(args=args)
        args.narration_query = query_text
        if not query_text:
            msg = "__RED__Error: query string is required.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        if args.deep:
            response_dto: QueryDeepResponseDTO = query_deep(
                text=query_text,
                domain=domain,
                limit=args.limit,
                source=_resolve_query_source(args=args),
                mechanism=args.mechanism,
                knowledge_scope=args.knowledge_scope,
            )
            if args.json:
                args.narration_result_count = len(getattr(response_dto, "results", []) or [])
                print(json.dumps(response_dto.model_dump(mode="json"), ensure_ascii=False, indent=2))
                return 0
            print_human_deep_response(
                response_dto=response_dto,
                color_enabled=color_enabled,
                explain=bool(args.explain),
            )
            args.narration_result_count = len(getattr(response_dto, "results", []) or [])
            return 0

        results: list[GlobalQueryResultDTO] = query_global(
            text=query_text,
            domain=domain,
            limit=args.limit,
            source=_resolve_query_source(args=args),
            mechanism=args.mechanism,
            knowledge_scope=args.knowledge_scope,
        )

        if args.json:
            args.narration_result_count = len(results)
            payload: list[dict] = [
                result.model_dump(mode="json")
                for result in results
            ]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        print_human_results(
            results=results,
            query_text=query_text,
            color_enabled=color_enabled,
            explain=bool(args.explain),
        )
        args.narration_result_count = len(results)
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            msg = f"__RED__Error during query: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 1


def _resolve_query_arguments(args: argparse.Namespace) -> tuple[str, str]:
    """
    Resolve the legacy positional `domain query` contract.

    Args:
        args (argparse.Namespace): Parsed command arguments.

    Returns:
        tuple[str, str]: Memory domain filter and query text.
    """
    domain: str | None = args.domain
    query_text: str | None = args.query

    if domain is not None and query_text is None:
        return "all", domain
    if domain is not None and query_text is not None:
        return domain, query_text
    return "all", ""


def _resolve_query_source(args: argparse.Namespace) -> str:
    """
    Resolve source selection from `--source` and legacy `--scope`.

    Args:
        args (argparse.Namespace): Parsed command arguments.

    Returns:
        str: Selected query source.
    """
    source: str = getattr(args, "source", "all") or "all"
    legacy_scope: str | None = getattr(args, "scope", None)
    if source == "all" and legacy_scope:
        return legacy_scope
    return source
