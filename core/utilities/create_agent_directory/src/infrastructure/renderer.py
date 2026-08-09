"""Strict placeholder renderer with typed exact substitutions."""
import json
import re
from typing import Any, Mapping

_PLACEHOLDER = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*}}")

def render_template(template: str, values: Mapping[str, Any]) -> str:
    """Render known placeholders, preserving exact JSON value types.

    Args:
        template: Template text containing ``{{name}}`` placeholders.
        values: Explicit placeholder map.
    Returns:
        str: Rendered text.
    Raises:
        KeyError: If a placeholder is unknown.
        ValueError: If an exact placeholder value cannot be embedded.
    """

    matches = list(_PLACEHOLDER.finditer(template))
    
    for match in matches:
        name = match.group(1)
        if name not in values:
            raise KeyError(name)
    
    if len(matches) == 1 and matches[0].span() == (0, len(template)):
        return json.dumps(values[matches[0].group(1)], ensure_ascii=False)
    
    return _PLACEHOLDER.sub(lambda m: _escape(values[m.group(1)]), template)

def _escape(value: Any) -> str:
    """Serialize embedded values as escaped JSON strings."""
    
    return json.dumps(str(value), ensure_ascii=False)[1:-1]
