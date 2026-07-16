# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Shared contracts for the Brain Explorer HTTP infrastructure."""

from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

from brain.infrastructure.explorer.cli_facade import BrainCliFacade


@dataclass(slots=True)
class BrainExplorerServerConfig:
    """Runtime dependencies and network settings for the Explorer server."""

    host: str
    port: int
    dist_dir: Path
    api_timeout: float
    facade: BrainCliFacade


class ApiRouteError(Exception):
    """Route-level failure carrying its HTTP response status."""

    def __init__(self, status: HTTPStatus, message: str) -> None:
        """Initialize a route failure with a status and safe message."""
        super().__init__(message)
        self.status = status
        self.message = message
