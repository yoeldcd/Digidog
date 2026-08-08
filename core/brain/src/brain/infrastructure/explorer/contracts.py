# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Shared contracts for the Brain Explorer HTTP infrastructure."""

from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

from brain.infrastructure.explorer.cli_facade import BrainCliFacade


@dataclass(slots=True)
class BrainExplorerServerConfig:
    """Runtime dependencies and network settings for the Explorer server.

    Attributes:
        host (str): Interface address bound by the HTTP server.
        port (int): TCP port bound by the HTTP server.
        dist_dir (Path): Explorer static distribution directory.
        api_timeout (float): Compatibility timeout supplied to the CLI facade.
        facade (BrainCliFacade): In-process Brain command facade.
    """

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
