# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Registered command modules for the brain CLI router."""

from __future__ import annotations

# Application Modules Imports
from brain.presentation.commands.backlog import command_add_task, command_delete_task, command_edit_task, command_set_task_status, command_show_backlog, command_task_finished
from brain.presentation.commands.diary import command_edit_diary, command_read_diary, command_write_diary
from brain.presentation.commands.general import (
    command_resolve_avatar_message,
    command_avatar_outbox,
    command_check_workspace,
    command_complete_work,
    command_create_brain,
    command_get_context,
    command_init,
    command_list_messages,
    command_list_avatar_voices,
    command_query,
    command_register_project,
    command_registre_proyect,
    command_serve_explorer,
    command_show_help,
    command_speak,
    command_avatar_service_status,
    command_start_avatar_service,
    command_stop_avatar_service,
)
from brain.presentation.commands.knowledge import (
    command_delete_knowledge_deltas,
    command_dream,
    command_knowledge_deltas,
    command_knowledge_export,
    command_knowledge_init,
    command_knowledge_query,
    command_knowledge_show,
    command_knowledge_status,
)
from brain.presentation.commands.logs import (
    command_append_log,
    command_edit_log,
    command_export_logs,
    command_log_index,
    command_query_log,
    command_read_log,
    command_update_log_index,
)
from brain.presentation.commands.memory import (
    command_add_memory_domain,
    command_delete_memory_entry,
    command_export_domains,
    command_memory_structure,
    command_read_record,
    command_update_memory_index,
    command_write_record,
)
from brain.presentation.commands.profiles import command_list_profiles, command_read_profile
from brain.presentation.commands.pictures import (
    command_describe_picture,
    command_list_pictures,
    command_picture_status,
    command_scan_pictures,
)
from brain.presentation.commands.snippets import command_clone_snippet, command_list_snippets
from brain.presentation.commands.utilities import command_propagate_agent_prompt, command_wiki
from brain.presentation.commands.vectorstore import (
    command_local_vectorstore_status,
    command_rebuild_local_vectorstore,
    command_rebuild_vectorstore,
    command_update_vectorstore,
    command_vectorstore_status,
)


COMMAND_MODULES = [
    command_show_help,
    command_resolve_avatar_message,
    command_avatar_outbox,
    command_memory_structure,
    command_add_memory_domain,
    command_write_record,
    command_read_record,
    command_check_workspace,
    command_complete_work,
    command_export_domains,
    command_delete_memory_entry,
    command_write_diary,
    command_read_diary,
    command_edit_diary,
    command_get_context,
    command_init,
    command_list_profiles,
    command_read_profile,
    command_list_snippets,
    command_clone_snippet,
    command_wiki,
    command_propagate_agent_prompt,
    command_update_vectorstore,
    command_rebuild_vectorstore,
    command_query,
    command_serve_explorer,
    command_vectorstore_status,
    command_update_memory_index,
    command_append_log,
    command_edit_log,
    command_export_logs,
    command_log_index,
    command_update_log_index,
    command_create_brain,
    command_register_project,
    command_registre_proyect,
    command_read_log,
    command_query_log,
    command_rebuild_local_vectorstore,
    command_local_vectorstore_status,
    command_add_task,
    command_task_finished,
    command_set_task_status,
    command_edit_task,
    command_show_backlog,
    command_delete_task,
    command_knowledge_init,
    command_knowledge_status,
    command_knowledge_deltas,
    command_delete_knowledge_deltas,
    command_knowledge_query,
    command_knowledge_show,
    command_knowledge_export,
    command_dream,
    command_speak,
    command_list_messages,
    command_list_avatar_voices,
    command_start_avatar_service,
    command_stop_avatar_service,
    command_avatar_service_status,
    command_scan_pictures,
    command_list_pictures,
    command_describe_picture,
    command_picture_status,
]
