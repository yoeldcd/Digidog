# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Scope planning for knowledge dream runs."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.runtime.scopes import normalize_knowledge_scope


def resolve_dream_scope_plan(scope: str, domain: str) -> list[dict[str, str]]:
    """
    Resolve dream scope execution plans.

    Args:
        scope (str): Raw scope selector.
        domain (str): Source domain selector.

    Returns:
        list[dict[str, str]]: Physical scope plus source-domain filter pairs.
    """
    normalized_scope: str = scope.casefold().strip()
    normalized_domain: str = domain.casefold().strip()
    if normalized_scope == "auto":
        normalized_scope = "all"
    if normalized_scope == "all":
        plans: list[dict[str, str]] = []
        if normalized_domain != "logs":
            plans.append({"scope": "global", "domain": normalized_domain})
        if normalized_domain in ("all", "logs"):
            plans.append({"scope": "local", "domain": "logs"})
        return plans
    return [{"scope": normalize_knowledge_scope(scope=normalized_scope), "domain": normalized_domain}]
