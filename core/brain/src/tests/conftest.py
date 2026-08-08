"""Prevent filesystem-writing Brain tests from entering pytest collection."""

from __future__ import annotations


# Yoi's workspace policy forbids tests from writing any artifact to disk, even
# when a test intends to clean it afterward. These modules create files,
# directories, SQLite databases, images, archives, or stdlib temporary roots.
collect_ignore = [
    "test_avatar_communication.py",
    "test_avatar_qt_migration.py",
    "test_backlog_store.py",
    "test_brain_explorer.py",
    "test_cli_clean_architecture.py",
    "test_codex_quota_client.py",
    "test_core_facade_paths.py",
    "test_global_query.py",
    "test_knowledge.py",
    "test_message_history.py",
    "test_picture_guidance.py",
    "test_picture_registry.py",
    "test_vectorstore_references.py",
    "test_voice_service.py",
    "test_workspace_codex_config.py",
]
