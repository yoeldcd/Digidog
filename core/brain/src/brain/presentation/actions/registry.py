"""Registered executable action modules for Brain CLI commands."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module


ACTION_HANDLERS: dict[str, str] = {
    "resolve-avatar-message": "brain.presentation.actions.general.command_resolve_avatar_message",
    "avatar-outbox": "brain.presentation.actions.general.command_avatar_outbox",
    "help": "brain.presentation.actions.general.command_show_help",
    "memory-structure": "brain.presentation.actions.memory.command_memory_structure",
    "add-memory-domain": "brain.presentation.actions.memory.command_add_memory_domain",
    "set-memory-entry": "brain.presentation.actions.memory.command_write_record",
    "get-memory-entry": "brain.presentation.actions.memory.command_read_record",
    "check-workspace": "brain.presentation.actions.general.command_check_workspace",
    "complete-work": "brain.presentation.actions.general.command_complete_work",
    "export": "brain.presentation.actions.memory.command_export_domains",
    "delete-memory-entry": "brain.presentation.actions.memory.command_delete_memory_entry",
    "write-diary": "brain.presentation.actions.diary.command_write_diary",
    "read-diary": "brain.presentation.actions.diary.command_read_diary",
    "edit-diary": "brain.presentation.actions.diary.command_edit_diary",
    "get-context": "brain.presentation.actions.general.command_get_context",
    "init": "brain.presentation.actions.general.command_init",
    "list-profiles": "brain.presentation.actions.profiles.command_list_profiles",
    "read-profile": "brain.presentation.actions.profiles.command_read_profile",
    "list-snippets": "brain.presentation.actions.snippets.command_list_snippets",
    "clone-snippet": "brain.presentation.actions.snippets.command_clone_snippet",
    "wiki": "brain.presentation.actions.utilities.command_wiki",
    "propagate-agent-prompt": "brain.presentation.actions.utilities.command_propagate_agent_prompt",
    "update-vectorstore": "brain.presentation.actions.vectorstore.command_update_vectorstore",
    "rebuild-vectorstore": "brain.presentation.actions.vectorstore.command_rebuild_vectorstore",
    "query": "brain.presentation.actions.general.command_query",
    "serve-explorer": "brain.presentation.actions.general.command_serve_explorer",
    "vectorstore-status": "brain.presentation.actions.vectorstore.command_vectorstore_status",
    "update-memory-index": "brain.presentation.actions.memory.command_update_memory_index",
    "append-log": "brain.presentation.actions.logs.command_append_log",
    "edit-log": "brain.presentation.actions.logs.command_edit_log",
    "export-logs": "brain.presentation.actions.logs.command_export_logs",
    "log-index": "brain.presentation.actions.logs.command_log_index",
    "update-log-index": "brain.presentation.actions.logs.command_update_log_index",
    "create-brain": "brain.presentation.actions.general.command_create_brain",
    "register-project": "brain.presentation.actions.general.command_register_project",
    "registre-proyect": "brain.presentation.actions.general.command_register_project",
    "read-log": "brain.presentation.actions.logs.command_read_log",
    "query-log": "brain.presentation.actions.logs.command_query_log",
    "rebuild-local-vectorstore": "brain.presentation.actions.vectorstore.command_rebuild_local_vectorstore",
    "local-vectorstore-status": "brain.presentation.actions.vectorstore.command_local_vectorstore_status",
    "add-task": "brain.presentation.actions.backlog.command_add_task",
    "task-finished": "brain.presentation.actions.backlog.command_task_finished",
    "set-task-status": "brain.presentation.actions.backlog.command_set_task_status",
    "edit-task": "brain.presentation.actions.backlog.command_edit_task",
    "show-backlog": "brain.presentation.actions.backlog.command_show_backlog",
    "delete-task": "brain.presentation.actions.backlog.command_delete_task",
    "knowledge-init": "brain.presentation.actions.knowledge.command_knowledge_init",
    "knowledge-status": "brain.presentation.actions.knowledge.command_knowledge_status",
    "knowledge-deltas": "brain.presentation.actions.knowledge.command_knowledge_deltas",
    "delete-knowledge-deltas": "brain.presentation.actions.knowledge.command_delete_knowledge_deltas",
    "knowledge-query": "brain.presentation.actions.knowledge.command_knowledge_query",
    "knowledge-show": "brain.presentation.actions.knowledge.command_knowledge_show",
    "knowledge-export": "brain.presentation.actions.knowledge.command_knowledge_export",
    "dream": "brain.presentation.actions.knowledge.command_dream",
    "speak": "brain.presentation.actions.general.command_speak",
    "list-messages": "brain.presentation.actions.general.command_list_messages",
    "list-avatar-voices": "brain.presentation.actions.general.command_list_avatar_voices",
    "start-avatar-service": "brain.presentation.actions.general.command_start_avatar_service",
    "stop-avatar-service": "brain.presentation.actions.general.command_stop_avatar_service",
    "avatar-service-status": "brain.presentation.actions.general.command_avatar_service_status",
}
"""Command name to lazy action-module import path."""

_RESOLVED_HANDLERS: dict[str, Callable] = {}


def get_action_handler(command_name: str) -> Callable | None:
    """Return the executable action handler for a command name."""
    if command_name in _RESOLVED_HANDLERS:
        return _RESOLVED_HANDLERS[command_name]
    action_module_path = ACTION_HANDLERS.get(command_name)
    if action_module_path is None:
        return None
    action_module = import_module(action_module_path)
    action_handler = getattr(action_module, "handle", None)
    if not callable(action_handler):
        return None
    _RESOLVED_HANDLERS[command_name] = action_handler
    return action_handler
