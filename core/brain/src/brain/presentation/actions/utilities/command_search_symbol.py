# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action handler for searching code symbols in Python files."""

from __future__ import annotations

import argparse
import json

from brain.application.symbols import search_symbols
from brain.domain.symbols import SymbolKind, SymbolSearchQuery


def handle(args: argparse.Namespace) -> int:
    """Execute code symbol search according to parsed CLI flags.

    Args:
        args (argparse.Namespace): Parsed CLI arguments.

    Returns:
        int: Process exit status (0 for success).
    """
    raw_kind = getattr(args, "kind", "all") or "all"
    raw_kind = raw_kind.strip().lower()
    try:
        kind = SymbolKind(raw_kind)
    except ValueError:
        kind = SymbolKind.ALL

    query = SymbolSearchQuery(
        name_pattern=getattr(args, "name", "") or "",
        language=getattr(args, "language", "") or "",
        path=getattr(args, "path", ".") or ".",
        kind=kind,
    )

    symbols = search_symbols(query)
    is_json = getattr(args, "json", False)

    if is_json:
        payload = {
            "ok": True,
            "command": "search-symbol",
            "query": {
                "name": query.name_pattern,
                "language": query.language,
                "path": query.path,
                "kind": query.kind.value,
            },
            "count": len(symbols),
            "symbols": [symbol.as_dict() for symbol in symbols],
        }
        setattr(args, "json_payload", payload)
        print(json.dumps(payload, indent=2))
        return 0

    if not symbols:
        print(f"No symbols found matching name='{query.name_pattern}' in '{query.path}'.")
        return 0

    print(f"Found {len(symbols)} symbol(s) matching '{query.name_pattern}':\n")
    for symbol in symbols:
        parent_info = f" [{symbol.parent_symbol}]" if symbol.parent_symbol else ""
        print(
            f"- {symbol.kind.value.upper()}{parent_info} {symbol.name} "
            f"({symbol.filepath}:{symbol.start_line}-{symbol.end_line})"
        )
        print(f"  Signature: {symbol.signature}")
        if symbol.docstring_summary:
            print(f"  Summary: {symbol.docstring_summary}")
        print()

    return 0
