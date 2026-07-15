"""Execution flow for the knowledge dream CLI action."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
from typing import Any

# Application Modules Imports
from brain.application.knowledge.orchestration.dream import DreamRunner
from brain.application.knowledge.pipeline.delta_apply import apply_pending_delta_rows
from brain.application.knowledge.pipeline.delta_revalidation import revalidate_pending_delta_rows
from brain.presentation.views.knowledge.delta_review import render_delta_review
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.actions.knowledge.dream_review import (
    is_bootstrap_required,
    load_pending_rows,
    reload_review_rows,
    select_applicable_rows,
)
from brain.presentation.inputs.knowledge.delta_selection import prompt_delta_selection
from brain.presentation.terminal import render_placeholders
from brain.presentation.views.knowledge.dream_delta_buffer import (
    build_pending_delta_buffer_payload,
    handle_pending_delta_buffer,
)
from brain.presentation.views.knowledge.dream_event_callbacks import (
    resolve_application_event_callback,
    resolve_llm_event_callback,
    resolve_orchestration_event_callback,
)
from brain.presentation.views.knowledge.dream_prune import confirm_and_prune_knowledge_graph


def run_dream_scope(
    args: argparse.Namespace,
    scope_name: str,
    source_domain: str,
    color_enabled: bool,
) -> tuple[int, dict[str, Any]]:
    """
    Execute dream against one physical knowledge scope.

    Args:
        args (argparse.Namespace): Parsed CLI arguments.
        scope_name (str): Physical knowledge scope.
        source_domain (str): Source family filter for this scope.
        color_enabled (bool): Whether ANSI placeholders should render.

    Returns:
        tuple[int, dict[str, Any]]: Process status and JSON-compatible payload.
    """
    try:
        repository = KnowledgeRepository(scope=scope_name)
        if bool(getattr(args, "prune", False)):
            pruned_repository = confirm_and_prune_knowledge_graph(
                repository=repository,
                color_enabled=color_enabled,
                json_enabled=bool(args.json),
            )
            if pruned_repository is None:
                return 0, {
                    "ok": False,
                    "scope": scope_name,
                    "prune_status": repository.status(),
                    "confirmation": "interactive_required",
                }
            repository = pruned_repository
        pending_buffer_rows: list[dict[str, Any]] = repository.list_pending_deltas(
            limit=200,
            status="pending",
        )
        pending_buffer_rows = revalidate_pending_delta_rows(
            repository=repository,
            rows=pending_buffer_rows,
        )
        if pending_buffer_rows:
            return handle_pending_delta_buffer(
                args=args,
                repository=repository,
                scope_name=scope_name,
                pending_rows=pending_buffer_rows,
                color_enabled=color_enabled,
            ), build_pending_delta_buffer_payload(
                scope_name=scope_name,
                pending_rows=pending_buffer_rows,
            )
        bootstrap_required: bool = is_bootstrap_required(repository=repository)
        bootstrap_allowed: bool = bootstrap_required and not bool(args.json)
        runner = DreamRunner(repository=repository)
        llm_event_callback = resolve_llm_event_callback(args=args, color_enabled=color_enabled)
        application_event_callback = resolve_application_event_callback(args=args, color_enabled=color_enabled)
        orchestration_event_callback = resolve_orchestration_event_callback(args=args, color_enabled=color_enabled)
        runner_dry_run: bool = True
        dream_dto = runner.run(
            domain=source_domain,
            limit=args.limit,
            dry_run=runner_dry_run,
            use_llm=True,
            minimum_confidence=args.min_confidence,
            llm_event_callback=llm_event_callback,
            orchestration_event_callback=orchestration_event_callback,
            force_all=bool(getattr(args, "prune", False)),
        )
        pending_rows: list[dict[str, Any]] = load_pending_rows(
            repository=repository,
            pending_delta_ids=dream_dto.pending_delta_ids,
        )
        reviewing_existing: bool = False
        if not pending_rows:
            pending_rows = repository.list_pending_deltas(
                limit=int(args.limit or 20),
                status="pending",
            )
            pending_rows = revalidate_pending_delta_rows(
                repository=repository,
                rows=pending_rows,
            )
            reviewing_existing = bool(pending_rows)
        bootstrap_applied_count: int = dream_dto.deltas_applied if bootstrap_allowed else 0
        bootstrap_errors: list[str] = []
        bootstrap_rows: list[dict[str, Any]] = (
            select_applicable_rows(rows=pending_rows)
            if bootstrap_allowed and bootstrap_applied_count == 0
            else []
        )
        if bootstrap_rows:
            bootstrap_applied_count, bootstrap_errors, bootstrap_decisions = apply_pending_delta_rows(
                repository=repository,
                selected_rows=bootstrap_rows,
                event_callback=application_event_callback,
            )
            dream_dto.decisions.extend(bootstrap_decisions)
            pending_rows = reload_review_rows(
                repository=repository,
                previous_rows=pending_rows,
                pending_delta_ids=dream_dto.pending_delta_ids,
            )
        payload: dict[str, Any] = {
            "ok": True,
            "scope": scope_name,
            "source_domain": source_domain,
            "dream": dream_dto.model_dump(mode="json"),
            "pending_deltas": pending_rows,
            "reviewing_existing_pending": reviewing_existing,
            "bootstrap_required": bootstrap_required,
            "bootstrap_allowed": bootstrap_allowed,
            "bootstrap_applied": bootstrap_applied_count,
            "bootstrap_errors": bootstrap_errors,
            "confirmation": "disabled_in_json_mode" if args.json else "interactive_when_pending",
        }
        if not args.json:
            msg = (
                f"__GREEN__Dream proposals ready__RESET__ ({scope_name}): "
                f"inspected __CYAN__{dream_dto.sources_seen}__RESET__, "
                f"proposed __CYAN__{dream_dto.deltas_proposed}__RESET__, "
                f"applied __CYAN__{bootstrap_applied_count}__RESET__ before confirmation."
            )
            print(render_placeholders(msg, color_enabled))
            if bootstrap_applied_count:
                print(
                    render_placeholders(
                        "__GREEN__Empty graph bootstrap applied all valid deltas automatically.__RESET__",
                        color_enabled,
                    ),
                )
            if reviewing_existing:
                print(
                    render_placeholders(
                        "__YELLOW__No new source deltas were generated; reviewing existing pending proposals.__RESET__",
                        color_enabled,
                    ),
                )
            print(
                render_delta_review(
                    rows=pending_rows,
                    color_enabled=color_enabled,
                    title="Proposed Knowledge Deltas",
                    compact=False,
                    show_review_hint=True,
                    entity_rows=repository.list_entities(),
                ),
            )
            selected_rows: list[dict[str, Any]] = []
            if bootstrap_applied_count:
                for bootstrap_error in bootstrap_errors:
                    print(render_placeholders(f"__YELLOW__{bootstrap_error}__RESET__", color_enabled))
            else:
                selected_rows = prompt_delta_selection(
                    rows=pending_rows,
                    color_enabled=color_enabled,
                )
            applied_count, application_errors, decisions = apply_pending_delta_rows(
                repository=repository,
                selected_rows=selected_rows,
                event_callback=application_event_callback,
            )
            dream_dto.decisions.extend(decisions)
            if applied_count:
                print(
                    render_placeholders(
                        f"__GREEN__Applied {applied_count} selected deltas.__RESET__",
                        color_enabled,
                    ),
                )
            elif pending_rows and not bootstrap_applied_count:
                print(render_placeholders("__YELLOW__No deltas applied.__RESET__", color_enabled))
            for application_error in application_errors:
                print(render_placeholders(f"__YELLOW__{application_error}__RESET__", color_enabled))
            if dream_dto.errors:
                print(render_placeholders(f"__YELLOW__Warnings: {len(dream_dto.errors)}__RESET__", color_enabled))
        return 0, payload
    except Exception as exc:
        if args.json:
            return 1, {"ok": False, "scope": scope_name, "error": str(exc)}
        else:
            print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1, {"ok": False, "scope": scope_name, "error": str(exc)}
