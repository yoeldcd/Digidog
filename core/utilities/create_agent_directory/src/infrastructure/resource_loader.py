"""Cwd-independent resource loading."""
from pathlib import Path

class ResourceLoader:
    """Load files relative to an injected utility root."""
    
    def __init__(self, utility_root: Path) -> None:
        """Initialize loader with utility root.

        Args:
            utility_root: Absolute or relative utility directory.
        """
        self._root = utility_root.resolve()
    
    def read_text(self, relative_path: str | Path) -> str:
        """Read UTF-8 text under utility root.

        Args:
            relative_path: Relative resource path.
        Returns:
            str: Resource text.
        Raises:
            ValueError: If path escapes root.
        """
    
        path = (self._root / relative_path).resolve()
    
        if self._root not in path.parents and path != self._root:
            raise ValueError("resource path escapes utility root")
        
        return path.read_text(encoding="utf-8")
