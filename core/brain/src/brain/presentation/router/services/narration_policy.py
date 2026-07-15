"""Data-driven spoken narration contracts reviewed by the workspace owner."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from functools import lru_cache

from brain.presentation.router.services.narration_templates import NARRATION_TEMPLATE_ROWS


@dataclass(frozen=True)
class CommandNarration:
    """Call and outcome templates for one canonical CLI command."""

    call_template: str
    output_template: str
    refine_with_llm: bool
    emotion: str = "focused"

    @property
    def announce_start(self) -> bool:
        """Return whether the reviewed contract speaks before execution."""
        return bool(self.call_template and self.call_template.casefold() != "no-speak")


_EMOTIONS = {
    "dream": "sleepy",
    "query": "thinking",
    "query-log": "remembering",
    "read-diary": "remembering",
    "read-log": "remembering",
    "complete-work": "proud",
    "task-finished": "proud",
}

@lru_cache(maxsize=1)
def _load_templates() -> dict[str, CommandNarration]:
    """Build package-owned narration contracts without reading workspace files."""
    return {
        command: CommandNarration(
            call_template=row[0],
            output_template=row[1],
            refine_with_llm=row[2],
            emotion=_EMOTIONS.get(command, "focused"),
        )
        for command, row in NARRATION_TEMPLATE_ROWS.items()
    }


def narration_for(command: str, args: argparse.Namespace) -> CommandNarration | None:
    """Return the reviewed narration contract for a command, when configured."""
    del args
    return _load_templates().get(command)


def build_narration_draft(
    *,
    command: str,
    template: str,
    args: argparse.Namespace,
    output: str = "",
    succeeded: bool = True,
    phase: str,
    cause: str = "",
) -> str:
    """Combine one selected template with bounded, factual command evidence."""
    selected = _select_variant(
        command=command,
        template=template,
        args=args,
        output=output,
        succeeded=succeeded,
    )
    facts = {
        key: _safe_value(value)
        for key, value in vars(args).items()
        if key not in {"handler", "func"} and value not in (None, "", False)
    }
    if cause:
        facts["cause"] = cause
        facts["error"] = cause
    bounded_output = output.strip()
    if len(bounded_output) > 4000:
        bounded_output = bounded_output[:2000] + "\n…\n" + bounded_output[-2000:]
    safe_fallback = render_safe_template(template=selected, facts=facts)
    return (
        f"Comando: {command}\n"
        f"Fase: {phase}\n"
        f"Plantilla aprobada: {selected}\n"
        f"Fallback seguro: {safe_fallback}\n"
        f"Argumentos reales: {json.dumps(facts, ensure_ascii=False)}\n"
        f"Salida real: {bounded_output or 'sin salida textual'}"
    )


def _select_variant(
    *,
    command: str,
    template: str,
    args: argparse.Namespace,
    output: str,
    succeeded: bool,
) -> str:
    """Select the reviewed success, error, state, empty, or populated branch."""
    variants = [part.strip() for part in template.split(" | ") if part.strip()]
    if not succeeded:
        return _variant(variants, "Error:") or variants[-1]
    status = str(getattr(args, "status", "") or "").upper()
    if command == "task-finished":
        status = "DONE"
    if status:
        state_variant = _variant(variants, f"{status}:")
        if state_variant:
            return state_variant
    normalized_output = output.casefold()
    empty = any(
        marker in normalized_output
        for marker in ("no matching", "no encontr", "0 result", "0 tareas", "no quedan tareas")
    )
    if empty:
        return _variant(variants, "Sin resultados:") or _variant(variants, "Vacío:") or variants[0]
    return (
        _variant(variants, "Éxito:")
        or _variant(variants, "Con resultados:")
        or _variant(variants, "Con tareas:")
        or variants[0]
    )


def _variant(variants: list[str], prefix: str) -> str:
    """Return one branch without its routing label."""
    for variant in variants:
        if variant.casefold().startswith(prefix.casefold()):
            return variant[len(prefix):].strip()
    return ""


def _safe_value(value: object) -> object:
    """Convert parser values into compact JSON-compatible facts."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    return str(value)


def render_safe_template(*, template: str, facts: dict[str, object]) -> str:
    """Render a concise deterministic fallback without leaking raw arguments."""
    normalized_facts: dict[str, object] = {}
    for key, value in facts.items():
        normalized_key = _normalize_placeholder(key)
        normalized_facts[normalized_key] = value
        if normalized_key.startswith("narration_"):
            normalized_facts[normalized_key.removeprefix("narration_")] = value

    def replace(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        normalized_token = _normalize_placeholder(token)
        if normalized_token == "log_summary_of_what_does":
            return ""
        if normalized_token == "task_list_with_title_ordered_by_priority":
            return ""
        if normalized_token == "un_resultado_n_results_resultados":
            count = int(normalized_facts.get("result_count") or 0)
            return "un resultado" if count == 1 else f"{count} resultados"
        for prefix, spoken_prefix in (("del_dominio_", "del dominio "), ("en_", "en ")):
            if normalized_token.startswith(prefix):
                value = _spoken_fact(normalized_facts.get(normalized_token.removeprefix(prefix)))
                return spoken_prefix + value if value else ""
        if "|" in token:
            primary, default = token.split("|", 1)
            if _normalize_placeholder(primary) in {"description", "info", "query", "summary", "title"}:
                return default.strip()
            value = _spoken_fact(normalized_facts.get(_normalize_placeholder(primary)))
            return value or default.strip()
        if normalized_token in {"description", "info", "query", "summary", "title"}:
            return ""
        return _spoken_fact(normalized_facts.get(normalized_token))

    rendered = re.sub(r"\{([^{}]+)\}", replace, template)
    rendered = re.sub(r"\s+([,.;:!?])", r"\1", rendered)
    rendered = re.sub(r":([.;!?])", r"\1", rendered)
    rendered = re.sub(r"\.{2,}", ".", rendered)
    rendered = re.sub(r"\s{2,}", " ", rendered).strip(" ,")
    return rendered[:1200].strip() or "He completado la operaci\u00f3n."


def _normalize_placeholder(value: str) -> str:
    """Normalize parser keys and human-authored placeholder labels."""
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _spoken_fact(value: object) -> str:
    """Convert a selected fact to bounded speech without serializing payloads."""
    if value in (None, "", False):
        return ""
    if isinstance(value, list):
        items = []
        for item in value[:8]:
            if isinstance(item, dict):
                item = item.get("title") or item.get("name") or ""
            spoken = _spoken_fact(item)
            if spoken:
                items.append(spoken)
        return ", ".join(items)
    if isinstance(value, dict):
        return _spoken_fact(value.get("title") or value.get("name"))
    return str(value)[:600].strip()


def render_without_refinement(draft: str) -> str:
    """Return the pre-rendered safe sentence when a row disables the LLM."""
    fallback_line = next((line for line in draft.splitlines() if line.startswith("Fallback seguro: ")), "")
    return fallback_line.removeprefix("Fallback seguro: ").strip()
