# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Define reviewed, data-driven spoken narration contracts for the CLI boundary.

Keep template selection deterministic and redact secret or digest material before
command evidence can cross into voice output or persisted narration history.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from brain.presentation.router.services.narration_templates import NARRATION_TEMPLATE_ROWS


_REDACTED_VALUE: Final[str] = "[REDACTED]"
_SHA256_DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])",
    re.IGNORECASE,
)
_SENSITIVE_KEY_MARKERS: Final[tuple[str, ...]] = (
    "password",
    "passwd",
    "passphrase",
    "pwd",
    "secret",
    "token",
    "credential",
    "api_key",
    "access_key",
    "private_key",
    "hash",
    "digest",
    "salt",
)


@dataclass(frozen=True)
class CommandNarration:
    """Call and outcome templates for one canonical CLI command.

    Keep the command's spoken lifecycle policy in one immutable record so routing
    can select reviewed wording, refinement, and emotion without executing logic.

    Attributes:
        call_template (str): Spoken template used before command execution.
        output_template (str): Spoken template used after command execution.
        refine_with_llm (bool): Whether the safe draft may be refined by an LLM.
        emotion (str): Avatar emotion selected for the command narration.
    """

    call_template: str
    output_template: str
    refine_with_llm: bool
    emotion: str = "focused"

    @property
    def announce_start(self) -> bool:
        """Return whether the reviewed contract speaks before execution.

        This sentinel check lets the router suppress call-phase voice output while
        leaving the command handler and its terminal presentation untouched.

        Args:
            None.

        Returns:
            bool: True when a non-empty call template permits start narration.
        """

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
    """Build package-owned narration contracts without reading workspace files.

    The cache provides deterministic, read-only policy lookup at runtime and keeps
    narration selection independent from mutable workspace configuration.

    Args:
        None.

    Returns:
        dict[str, CommandNarration]: Cached narration contracts keyed by command.
    """

    # Contract materialization: derive each runtime record from reviewed package rows.

    return {
        command: CommandNarration(
            call_template=row[0],
            output_template=row[1],
            refine_with_llm=row[2],
            emotion=_EMOTIONS.get(command, "focused"),
        )
        # Template iteration: preserve the packaged command-to-row contract exactly.

        for command, row in NARRATION_TEMPLATE_ROWS.items()
    }


def narration_for(command: str, args: argparse.Namespace) -> CommandNarration | None:
    """Return the reviewed narration contract for a configured command.

    Use the packaged registry as the single policy source while retaining the
    router's argument-aware interface without inspecting argument secrets here.

    Args:
        command (str): Canonical CLI command name.
        args (argparse.Namespace): Parsed command arguments reserved for future
            context-sensitive policy selection.

    Returns:
        CommandNarration | None: Contract for ``command``, or None when speech is
        not configured.
    """
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
    """Combine a reviewed template with bounded factual command evidence.

    This boundary turns command state into deterministic evidence for voice output,
    redacting sensitive facts and digest-shaped material before the draft is reused.

    Args:
        command (str): Canonical CLI command name.
        template (str): Reviewed narration template with variants.
        args (argparse.Namespace): Parsed arguments supplying safe factual values.
        output (str): Captured command output available to narration.
        succeeded (bool): Whether command execution succeeded.
        phase (str): Lifecycle phase that the draft describes.
        cause (str): Optional concise failure cause.

    Returns:
        str: Structured narration draft containing template, facts, and fallback.
    """
    # Fact capture: exclude router callables and empty values before security filtering.
    raw_facts = {
        key: value
        # Fact iteration: inspect every parsed field while retaining its source value.

        for key, value in vars(args).items()
        # Fact filtering: omit execution hooks and empty values from narrated evidence.

        if key not in {"handler", "func"} and value not in (None, "", False)
    }

    facts, sensitive_values = _redact_facts(raw_facts)
    selected = _redact_sensitive_text(
        _select_variant(
            command=command,
            template=template,
            args=args,
            output=output,
            succeeded=succeeded,
        ),
        sensitive_values,
    )

    # Failure evidence: retain the cause only after scrubbing it against collected secrets.

    if cause:
        safe_cause = _redact_sensitive_text(cause, sensitive_values)
        facts["cause"] = safe_cause
        facts["error"] = safe_cause

    bounded_output = _redact_sensitive_text(output.strip(), sensitive_values)

    # Output bound: keep narrated evidence finite while retaining both output edges.

    if len(bounded_output) > 4000:
        bounded_output = bounded_output[:2000] + "\n…\n" + bounded_output[-2000:]
    safe_fallback = render_safe_template(template=selected, facts=facts)
    draft = (
        f"Comando: {_redact_sensitive_text(command, sensitive_values)}\n"
        f"Fase: {phase}\n"
        f"Plantilla aprobada: {selected}\n"
        f"Fallback seguro: {safe_fallback}\n"
        f"Argumentos reales: {json.dumps(facts, ensure_ascii=False)}\n"
        f"Salida real: {bounded_output or 'sin salida textual'}"
    )

    return _redact_sensitive_text(draft, sensitive_values)


def _select_variant(
    *,
    command: str,
    template: str,
    args: argparse.Namespace,
    output: str,
    succeeded: bool,
) -> str:
    """Select the reviewed success, error, state, empty, or populated branch.

    Apply lifecycle precedence in a fixed order so failures and explicit states
    remain more authoritative than generic result wording.

    Args:
        command: Canonical command name used for command-specific status rules.
        template: Reviewed template containing labeled narration variants.
        args: Parsed command arguments that may contain a status field.
        output: Command output used to detect empty-result variants.
        succeeded: Whether the command completed successfully.

    Returns:
        str: Selected narration variant without its routing label.
    """

    # Variant parsing: preserve reviewed order while discarding blank labels.
    variants = [
        part.strip()
        # Variant iteration: examine each reviewed segment in declaration order.

        for part in template.split(" | ")
        # Variant filtering: ignore empty segments that cannot produce speech.

        if part.strip()
    ]

    # Failure precedence: errors must win over success or empty-result wording.

    if not succeeded:
        return _variant(variants, "Error:") or variants[-1]

    status = str(getattr(args, "status", "") or "").upper()

    # Command-specific state: task completion uses DONE even when args omit a status.

    if command == "task-finished":
        status = "DONE"

    # Explicit state: prefer a matching labeled branch before inspecting text output.

    if status:
        state_variant = _variant(variants, f"{status}:")

        # State resolution: return only a branch whose reviewed label matches exactly.

        if state_variant:
            return state_variant

    normalized_output = output.casefold()
    # Empty-result detection: classify known no-data messages for reviewed fallbacks.

    empty = any(
        marker in normalized_output
        # Result markers: retain the existing operator-facing vocabulary unchanged.

        for marker in ("no matching", "no encontr", "0 result", "0 tareas", "no quedan tareas")
    )

    # Empty-result precedence: select explicit empty labels before generic success.

    if empty:
        return _variant(variants, "Sin resultados:") or _variant(variants, "Vacío:") or variants[0]

    return (
        _variant(variants, "Éxito:")
        or _variant(variants, "Con resultados:")
        or _variant(variants, "Con tareas:")
        or variants[0]
    )


def _variant(variants: list[str], prefix: str) -> str:
    """Return one branch without its routing label.

    Scan the reviewed labels in declaration order so template authors retain
    deterministic control over which matching branch is selected.

    Args:
        variants: Candidate labeled narration variants.
        prefix: Case-insensitive routing label to match.

    Returns:
        str: Matching variant without the routing label, or an empty string.
    """

    # Label scan: walk variants in declaration order to preserve template precedence.

    for variant in variants:

        # Label match: strip only the requested routing prefix from the selected branch.

        if variant.casefold().startswith(prefix.casefold()):
            return variant[len(prefix):].strip()

    return ""


def _safe_value(
    value: object,
    *,
    key: str = "",
    sensitive_values: tuple[str, ...] = (),
) -> object:
    """Convert one parser value into compact, recursively redacted facts.

    This recursive boundary preserves JSON-compatible evidence while replacing
    values identified as secret or digest material before they reach spoken output.

    Args:
        value: Parser value that may contain nested command payload data.
        key: Field name associated with ``value`` at the current recursion level.
        sensitive_values: Plaintext values collected from sensitive fields.

    Returns:
        object: JSON-compatible value with sensitive fields and digest text
        replaced by a stable redaction marker.
    """

    # Sensitive-key guard: collapse secret-labeled values before type serialization.

    if _is_sensitive_key(key):
        return _REDACTED_VALUE

    # Text sanitization: scrub collected secrets and standalone digest-shaped text.

    if isinstance(value, str):
        return _redact_sensitive_text(value, sensitive_values)

    # Primitive preservation: retain safe JSON-compatible facts without coercion.

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    # Sequence traversal: recurse without changing the caller-visible member order.

    if isinstance(value, (list, tuple)):
        return [
            _safe_value(item, sensitive_values=sensitive_values)
            # Sequence item iteration: apply the same redaction policy to each member.

            for item in value
        ]

    # Mapping traversal: retain keys while applying key-aware redaction recursively.

    if isinstance(value, dict):
        return {
            str(nested_key): _safe_value(
                nested_value,
                key=str(nested_key),
                sensitive_values=sensitive_values,
            )
            # Mapping item iteration: carry each nested field name into the guard.

            for nested_key, nested_value in value.items()
        }

    return str(value)


def _redact_facts(facts: dict[str, object]) -> tuple[dict[str, object], tuple[str, ...]]:
    """Recursively redact sensitive fields and collect their source values.

    Collect source values separately so the same plaintext is scrubbed from
    templates, causes, command output, and serialized draft context.

    Args:
        facts: Raw narration facts, including nested command payloads.

    Returns:
        tuple[dict[str, object], tuple[str, ...]]: Redacted facts and plaintext
        values used to scrub those values from nearby narration text.
    """

    # Secret collection: discover plaintext values before replacing sensitive fields.
    sensitive_values = _collect_sensitive_values(facts)
    # Fact projection: serialize the same tree with field-aware and text-level redaction.
    redacted_facts = {
        str(key): _safe_value(
            value,
            key=str(key),
            sensitive_values=sensitive_values,
        )
        # Fact iteration: preserve top-level fields while applying recursive safeguards.

        for key, value in facts.items()
    }

    return redacted_facts, sensitive_values


def _collect_sensitive_values(
    value: object,
    *,
    key: str = "",
    sensitive_context: bool = False,
) -> tuple[str, ...]:
    """Collect plaintext strings nested under sensitive fields.

    Track inherited sensitive context through mappings and sequences to provide
    complete redaction coverage without changing safe factual values.

    Args:
        value: Current value in a recursive fact tree.
        key: Field name associated with the current value.
        sensitive_context: Whether an ancestor field is already sensitive.

    Returns:
        tuple[str, ...]: Non-empty sensitive strings that must not enter speech.
    """

    current_context = sensitive_context or _is_sensitive_key(key)

    # Leaf handling: return only non-empty strings that are inside sensitive context.

    if isinstance(value, str):
        return (value,) if current_context and value else ()

    # Mapping traversal: propagate context while preserving each nested field name.

    if isinstance(value, dict):
        collected: list[str] = []

        # Nested mapping walk: inspect every child so secrets cannot hide in payload depth.

        for nested_key, nested_value in value.items():
            collected.extend(
                _collect_sensitive_values(
                    nested_value,
                    key=str(nested_key),
                    sensitive_context=current_context,
                )
            )

        return tuple(collected)

    # Sequence traversal: inherited sensitive context applies to every ordered member.

    if isinstance(value, (list, tuple)):
        collected = []

        # Nested sequence walk: collect secret descendants without rewriting their order.

        for nested_value in value:
            collected.extend(
                _collect_sensitive_values(
                    nested_value,
                    sensitive_context=current_context,
                )
            )

        return tuple(collected)

    return ()


def _is_sensitive_key(key: str) -> bool:
    """Return whether a field name denotes secret or digest material.

    Treat normalized field names as untrusted metadata and match known credential
    markers so the redaction policy fails closed for common secret representations.

    Args:
        key: Raw parser or payload field name.

    Returns:
        bool: True when the normalized field name is security-sensitive.
    """

    normalized_key = _normalize_placeholder(key)

    return any(marker in normalized_key for marker in _SENSITIVE_KEY_MARKERS)


def _redact_sensitive_text(value: str, sensitive_values: tuple[str, ...] = ()) -> str:
    """Remove known secret values and SHA-256-looking digests from narration text.

    Apply a last-mile scrub to templates, causes, command output, and final drafts
    so sensitive material cannot bypass field-aware redaction through free-form text.

    Args:
        value: Text that may be included in a narration draft.
        sensitive_values: Plaintext values found under sensitive fields.

    Returns:
        str: Text with secret material replaced by ``[REDACTED]``.
    """

    redacted_value = value
    unique_values = sorted(set(sensitive_values), key=len, reverse=True)

    # Direct-value scrub: replace longest values first so overlapping secrets cannot leak.

    for sensitive_value in unique_values:
        # Empty-value guard: skip no-op replacements while preserving the input text.

        if sensitive_value:
            redacted_value = redacted_value.replace(sensitive_value, _REDACTED_VALUE)

    return _SHA256_DIGEST_PATTERN.sub(_REDACTED_VALUE, redacted_value)


def render_safe_template(*, template: str, facts: dict[str, object]) -> str:
    """Render a concise deterministic fallback without leaking raw arguments.

    Select only bounded, human-readable facts so speech remains useful while raw
    payloads, free-form descriptions, and secret material stay out of the fallback.

    Args:
        template (str): Reviewed template containing bounded placeholders.
        facts (dict[str, object]): Sanitized argument and outcome facts.

    Returns:
        str: Safe narration sentence with unresolved or sensitive values omitted.
    """
    redacted_facts, sensitive_values = _redact_facts(facts)
    normalized_facts: dict[str, object] = {}

    # Placeholder index: normalize aliases once before resolving reviewed labels.

    for key, value in redacted_facts.items():
        normalized_key = _normalize_placeholder(key)
        normalized_facts[normalized_key] = value

        # Alias projection: accept narration-prefixed fields without duplicating data.

        if normalized_key.startswith("narration_"):
            normalized_facts[normalized_key.removeprefix("narration_")] = value

    def replace(match: re.Match[str]) -> str:
        """Resolve one template placeholder from the safe fact mapping.

        Apply reviewed placeholder rules and omit payload-oriented fields so the
        deterministic fallback stays concise without reconstructing sensitive data.

        Args:
            match (re.Match[str]): Placeholder match enclosed by curly braces.

        Returns:
            str: Bounded spoken substitution or an empty string.
        """

        token = match.group(1).strip()
        normalized_token = _normalize_placeholder(token)

        # Payload omission: never speak large workflow summaries or task tables.

        if normalized_token == "log_summary_of_what_does":
            return ""

        # Table omission: keep row-oriented data in the visual channel only.

        if normalized_token == "task_list_with_title_ordered_by_priority":
            return ""

        # Count projection: convert aggregate result facts into a short spoken phrase.

        if normalized_token == "un_resultado_n_results_resultados":
            count = int(normalized_facts.get("result_count") or 0)

            return "un resultado" if count == 1 else f"{count} resultados"

        # Contextual prefix: render supported domain/location labels with stable phrasing.

        for prefix, spoken_prefix in (("del_dominio_", "del dominio "), ("en_", "en ")):
            # Prefix selection: emit the human prefix only when a safe fact is available.

            if normalized_token.startswith(prefix):
                value = _spoken_fact(normalized_facts.get(normalized_token.removeprefix(prefix)))

                return spoken_prefix + value if value else ""

        # Fallback token: honor reviewed default text for payload-heavy placeholders.

        if "|" in token:
            primary, default = token.split("|", 1)

            # Payload placeholder: prefer the reviewed default over free-form descriptions.

            if _normalize_placeholder(primary) in {"description", "info", "query", "summary", "title"}:
                return default.strip()

            value = _spoken_fact(normalized_facts.get(_normalize_placeholder(primary)))

            return value or default.strip()

        # Unresolved payload field: omit sensitive or verbose free-form content.

        if normalized_token in {"description", "info", "query", "summary", "title"}:
            return ""

        return _spoken_fact(normalized_facts.get(normalized_token))

    rendered = re.sub(r"\{([^{}]+)\}", replace, template)
    rendered = re.sub(r"\s+([,.;:!?])", r"\1", rendered)
    rendered = re.sub(r":([.;!?])", r"\1", rendered)
    rendered = re.sub(r"\.{2,}", ".", rendered)
    rendered = re.sub(r"\s{2,}", " ", rendered).strip(" ,")
    bounded_rendered = rendered[:1200].strip()
    safe_rendered = _redact_sensitive_text(bounded_rendered, sensitive_values)

    return safe_rendered or "He completado la operaci\u00f3n."


def _normalize_placeholder(value: str) -> str:
    """Normalize parser keys and human-authored placeholder labels.

    Converge user-facing labels and parser names on one comparison form so
    reviewed templates can resolve aliases without changing their visible wording.

    Args:
        value: Parser key or placeholder label to normalize.

    Returns:
        str: Lowercase underscore-delimited placeholder key.
    """

    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _spoken_fact(value: object) -> str:
    """Convert a selected fact to bounded speech without serializing payloads.

    Restrict speech to short scalar values and selected names from collections so
    structured payloads remain visual or machine-readable rather than spoken verbatim.

    Args:
        value: Selected fact, list, or mapping to convert into speech.

    Returns:
        str: Bounded spoken representation of the selected fact.
    """

    # Empty-value guard: omit absent facts instead of manufacturing spoken content.

    if value in (None, "", False):
        return ""

    # List projection: narrate only a bounded set of selected item labels.

    if isinstance(value, list):
        items = []

        # List item traversal: retain useful title/name labels in their source order.

        for item in value[:8]:
            # Mapping projection: select a human label instead of serializing payload keys.

            if isinstance(item, dict):
                item = item.get("title") or item.get("name") or ""

            spoken = _spoken_fact(item)

            # Non-empty projection: omit items that produce no safe spoken text.

            if spoken:
                items.append(spoken)

        return ", ".join(items)

    # Mapping projection: select a human label and avoid serializing nested payloads.

    if isinstance(value, dict):
        return _spoken_fact(value.get("title") or value.get("name"))

    return str(value)[:600].strip()


def render_without_refinement(draft: str) -> str:
    """Extract the deterministic fallback when a row disables LLM refinement.

    Keep callers on the approved deterministic fallback path when refinement is
    disabled, preserving the selected narration contract and its output safety.

    Args:
        draft (str): Structured narration draft produced by this module.

    Returns:
        str: Safe fallback sentence, or an empty string when it is absent.
    """
    # Fallback extraction: keep only the reviewed deterministic line for no-refinement paths.

    fallback_line = next(
        (
            line
            # Draft line traversal: inspect the ordered draft without altering its content.

            for line in draft.splitlines()
            # Fallback filter: select only the approved deterministic output line.

            if line.startswith("Fallback seguro: ")
        ),
        "",
    )

    return fallback_line.removeprefix("Fallback seguro: ").strip()
