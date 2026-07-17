# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Runtime configuration DTO models for brain knowledge services."""

from __future__ import annotations

# Third-party Libraries Imports
from pydantic import BaseModel, ConfigDict, Field


class StageModelConfigDTO(BaseModel):
    """
    Configuration for a model-backed knowledge processing stage.

    Attributes:
        model: Provider model identifier.
        base_url: OpenAI-compatible API base URL.
        api_key: Environment reference or resolved API token.
        temperature: Sampling temperature used for generation.
        max_tokens: Maximum output token count for the stage.
        enabled: Whether the stage may call the external model.
    """

    model_config = ConfigDict(extra="forbid")

    model: str = Field(default="google/gemini-2.5-flash")
    """Provider model identifier."""

    base_url: str = Field(default="https://openrouter.ai/api/v1")
    """OpenAI-compatible API base URL."""

    api_key: str = Field(default="$OPENROUTER_API_KEY")
    """Environment reference or resolved API token."""

    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    """Sampling temperature used for generation."""

    max_tokens: int = Field(default=6000, ge=128, le=20000)
    """Maximum output token count for the stage."""

    enabled: bool = Field(default=True)
    """Whether the stage may call the external model."""


class KnowledgeConfigDTO(BaseModel):
    """
    Runtime configuration for the private knowledge graph store.

    Attributes:
        version: Configuration schema version.
        minimum_confidence: Minimum confidence required for applied deltas.
        stages: Per-stage model configuration.
    """

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1)
    """Configuration schema version."""

    minimum_confidence: float = Field(default=0.65, ge=0.0, le=1.0)
    """Minimum confidence required for applied deltas."""

    stages: dict[str, StageModelConfigDTO] = Field(default_factory=dict)
    """Per-stage model configuration."""


class MemoryConfigDTO(BaseModel):
    """
    Runtime configuration for memory-backed brain services.

    Attributes:
        embedding_model: Embedding model configuration.
        text_model: Text model configuration used by memory helpers.
    """

    model_config = ConfigDict(extra="forbid")

    embedding_model: StageModelConfigDTO = Field(
        default_factory=lambda: StageModelConfigDTO(model="openai/text-embedding-3-small"),
    )
    """Embedding model configuration."""

    text_model: StageModelConfigDTO = Field(default_factory=StageModelConfigDTO)
    """Text model configuration used by memory helpers."""


class PicturesConfigDTO(BaseModel):
    """Runtime configuration for picture discovery and img2text descriptions."""

    model_config = ConfigDict(extra="forbid")

    image_model: StageModelConfigDTO = Field(
        default_factory=lambda: StageModelConfigDTO(
            model="google/gemini-2.5-flash",
            max_tokens=1200,
            enabled=False,
        ),
    )
    """Optional OpenAI-compatible vision model used to describe images."""

    supported_extensions: list[str] = Field(
        default_factory=lambda: [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"],
    )
    """Case-insensitive file extensions included by picture scans."""

class BrainConfigsDTO(BaseModel):
    """
    Unified runtime configuration for brain services.

    Attributes:
        version: Configuration schema version.
        agent_name: Canonical agent identity owned by this core.
        user_name: Canonical user identity associated with the agent.
        agent_dir: Canonical global directory for agent-owned memory and snippets.
        knowledge: Knowledge graph configuration.
        memory: Memory and vectorstore configuration.
    """

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1)
    """Configuration schema version."""

    agent_name: str = Field(default="")
    """Canonical agent identity owned by this core."""

    user_name: str = Field(default="")
    """Canonical user identity associated with the agent."""

    agent_dir: str = Field(default="")
    """Canonical global directory for agent-owned memory and snippets."""

    knowledge: KnowledgeConfigDTO = Field(default_factory=KnowledgeConfigDTO)
    """Knowledge graph configuration."""

    memory: MemoryConfigDTO = Field(default_factory=MemoryConfigDTO)
    """Memory and vectorstore configuration."""

    pictures: PicturesConfigDTO = Field(default_factory=PicturesConfigDTO)
    """Picture registry and optional img2text configuration."""
