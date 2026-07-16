# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Constants for the brain runtime.

This module intentionally contains no filesystem, JSON, environment, network,
or mutation logic. Runtime behavior belongs to service modules.
"""

from __future__ import annotations


DEFAULT_WORKSPACE_ROOT = "."
"""Default workspace root when `WORKSPACE_ROOT` is not set."""

CONFIGS_DIR_NAME = "configs"
"""Core-owned configuration directory name."""

ASSETS_DIR_NAME = "assets"
"""Core-owned static asset directory name."""

AVATAR_ASSETS_DIR_NAME = "avatar"
"""Avatar state asset directory inside the core assets root."""

DATABASE_DIR_NAME = "database"
"""Private runtime database directory name."""

GLOBAL_KNOWLEDGE_DIR_NAME = "knowledge"
"""Core database subdirectory that owns the global knowledge graph."""

GLOBAL_SOURCES_DIR_NAME = "sources"
"""Core database subdirectory that owns the global source registry."""

GLOBAL_LOGS_DIR_NAME = "logs"
"""Core database subdirectory reserved for global log stores."""

GLOBAL_VECTORSTORES_DIR_NAME = "vectorstores"
INSTRUCTION_MIRRORS_DIR_NAME = "instruction_mirrors"
INSTRUCTION_MIRRORS_FILE_NAME = "agent_prompt_mirrors.txt"
"""Core database subdirectory that owns global vector collections."""

AVATAR_STORAGE_DIR_NAME = "avatar_storage"
"""Core database subdirectory that owns retained avatar runtime state."""

BRAIN_CONFIGS_FILE_NAME = "brain_configs.json"
"""Unified brain configuration filename."""

BRAIN_MIRRORS_FILE_NAME = "brain_mirrors.json"
"""Registered consumer workspace configuration filename."""

BRAIN_AVATAR_CONFIG_FILE_NAME = "brain_avatar_config.json"
"""Avatar and voice configuration filename."""

CONFIG_FILE_NAME = BRAIN_CONFIGS_FILE_NAME
"""Unified runtime brain configuration filename."""

BRAIN_KNOWLEDGE_DB_NAME = "brain_knowledge.db"
"""Global knowledge graph database filename."""

BRAIN_SOURCES_DB_NAME = "brain_sources.db"
"""Brain source registry database filename."""

LOCAL_SOURCES_DB_NAME = "sources.db"
"""Workspace-local knowledge graph database filename."""

BRAIN_VECTORSTORE_DIR_NAME = "brain_vectorstore"
"""Brain vectorstore directory name."""

DATABASE_GITIGNORE_TEXT = "*\n!.gitignore\n"
"""Gitignore payload used inside private runtime directories."""

MEMORY_DIR_NAME = "memory"
"""Shared Markdown memory directory name."""

TMP_DIR_NAME = ".tmp"
"""Shared temporary directory name."""

KNOWLEDGE_SCOPES: tuple[str, ...] = ("global", "local")
"""Physical knowledge graph scopes backed by isolated SQLite databases."""

KNOWLEDGE_SCOPE_VALUES: tuple[str, ...] = ("all", *KNOWLEDGE_SCOPES)
"""Public scope selector values accepted by read-oriented commands."""

KNOWLEDGE_SCHEMA_VERSION = "2"
"""Current SQLite schema version for the knowledge graph."""

KNOWLEDGE_MAX_PROMPT_CONTENT_CHARS = 16000
"""Maximum framed source text included in one LLM stage prompt."""

KNOWLEDGE_MAX_ENTITY_DETECTION_ITEMS = 35
"""Maximum entity candidates accepted from the entity detection stage."""

KNOWLEDGE_MAX_RELATION_EXTRACTION_ITEMS = 24
"""Maximum relation candidates accepted from the relation extraction stage."""

KNOWLEDGE_MAX_RELATION_PROMPT_ENTITIES = 24
"""Maximum prior entities shown to the relation extraction stage."""

KNOWLEDGE_LOCAL_ENTITY_ID_BASE = 1_000_000_000
"""Base for local candidate entity IDs hidden from model prompts."""

KNOWLEDGE_DEFAULT_LLM_STAGE_NAMES: tuple[str, ...] = (
    "entity_detection",
    "relation_extraction",
)
"""Minimal LLM stages used by dream for compact structural graph proposals."""

KNOWLEDGE_LLM_TIMEOUT_SECONDS = 30
"""HTTP timeout for OpenAI-compatible knowledge LLM requests."""

KNOWLEDGE_DELTA_MAX_LIVE_TEXT_LENGTH = 96
"""Maximum inline length for quoted live text in terminal knowledge delta reviews."""

DEFAULT_STAGE_NAMES: tuple[str, ...] = (
    "entity_detection",
    "relation_extraction",
    "schema_evolution",
    "deduplication",
    "consolidation",
    "profile_synthesis",
)
"""Model-backed processing stages exposed by the knowledge subsystem."""

STRUCTURAL_EXTRACTION_STAGE_NAMES: tuple[str, ...] = (
    "entity_detection",
    "relation_extraction",
)
"""Model stages that need larger responses for dense structural extraction."""

LEGACY_STAGE_MAX_TOKENS = 2000
"""Previous default max token budget retained only for config migration."""

EMBEDDING_UNAVAILABLE_MARKERS: tuple[str, ...] = (
    "failed to fetch embedding",
    "embedding api",
    "/embeddings",
    "winerror 10013",
    "forbidden by its access permissions",
    "connection refused",
    "timed out",
    "timeout",
    "name resolution",
    "temporary failure in name resolution",
    "no route to host",
    "network is unreachable",
)
"""Message fragments that identify embedding service failures."""

VECTORSTORE_RETRY_COMMAND = "python .\\$agent\\scripts\\brain.py update-vectorstore"
"""Default CLI recovery command for vectorstore embedding failures."""
