"""Entity class normalization and catalog helpers."""

from __future__ import annotations

# Standard Libraries Imports
import re

# Application Modules Imports
from brain.application.knowledge.models.ontology_definitions import (
    AGENTIC_ENTITY_CLASS_DEFINITIONS,
    BASE_ENTITY_CLASS_DEFINITIONS,
    CORE_ENTITY_CLASS_DEFINITIONS,
    SPACY_ENTITY_CLASS_DEFINITIONS,
)
from brain.application.knowledge.models.ontology_keys import normalize_ontology_key


def is_entity_class_allowed(entity_class: str) -> bool:
    """
    Check whether an entity class key can be used by the discovered ontology.

    Args:
        entity_class (str): Candidate ontology class.

    Returns:
        bool: True when the class key is syntactically valid.
    """
    return is_valid_entity_class_key(canonical_entity_class(entity_class))


def canonical_entity_class(entity_class: str) -> str:
    """
    Return the canonical ontology class key.

    Args:
        entity_class (str): Raw entity class string.

    Returns:
        str: Canonical entity class key.
    """
    raw_class: str = " ".join(str(entity_class or "").strip().split())
    if not raw_class:
        return "MISC.Concept"
    if raw_class.casefold() == "cls":
        return "CLS"

    if "." in raw_class:
        base_class, subtype = raw_class.split(".", 1)
        canonical_base: str = _canonical_base_entity_class(value=base_class)
        canonical_subtype: str = canonical_class_name(subtype)
        if canonical_subtype:
            return f"{canonical_base}.{canonical_subtype}"
        return canonical_base

    upper_class: str = raw_class.upper()
    if upper_class in BASE_ENTITY_CLASS_DEFINITIONS:
        return upper_class

    normalized_class: str = normalize_ontology_key(raw_class)
    if normalized_class in ("concept", "consolidated_claim"):
        return f"MISC.{canonical_class_name(normalized_class)}"
    if not normalized_class:
        return "MISC.Concept"
    return f"MISC.{canonical_class_name(raw_class)}"


def canonical_class_name(value: str) -> str:
    """
    Return a PascalCase programmatic class name.

    Args:
        value (str): Raw class name or dotted class key.

    Returns:
        str: PascalCase class name without base prefix.
    """
    raw_value: str = " ".join(str(value or "").strip().split())
    if not raw_value:
        return "Concept"
    if "." in raw_value:
        _base_value, raw_value = raw_value.split(".", 1)
    words: list[str] = re.findall(r"[A-Za-z0-9]+", raw_value)
    if not words:
        return "Concept"
    return "".join(word[:1].upper() + word[1:] for word in words)[:64]


def is_valid_entity_class_key(value: str) -> bool:
    """
    Validate a spaCy-compatible entity class key.

    Args:
        value (str): Candidate entity class key.

    Returns:
        bool: True when the key is `CLS`, a base label, or `BASE.PascalCaseSubtype`.
    """
    if value == "CLS":
        return True
    if value in BASE_ENTITY_CLASS_DEFINITIONS:
        return True
    if "." not in value:
        return False
    base_class, subtype = value.split(".", 1)
    return base_class in BASE_ENTITY_CLASS_DEFINITIONS and is_valid_class_name(subtype)


def is_valid_class_name(value: str) -> bool:
    """
    Validate a programmatic class-definition name.

    Args:
        value (str): Candidate class name.

    Returns:
        bool: True when the value follows the PascalCase class-name contract.
    """
    return bool(re.fullmatch(r"[A-Z][A-Za-z0-9]{0,63}", value))


def class_name_from_entity_class(entity_class: str) -> str | None:
    """
    Return the discovered subtype class name from an entity class key.

    Args:
        entity_class (str): Entity class key.

    Returns:
        str | None: PascalCase subtype name when the class has a discovered subtype.
    """
    canonical_class: str = canonical_entity_class(entity_class)
    if "." not in canonical_class:
        return None
    _base_class, subtype = canonical_class.split(".", 1)
    return subtype


def is_class_definition_entity(entity_class: str) -> bool:
    """
    Return whether an entity class denotes a class-definition entity.

    Args:
        entity_class (str): Raw entity class value.

    Returns:
        bool: True when the class is `CLS`.
    """
    return canonical_entity_class(entity_class) == "CLS"


def build_entity_class_catalog(known_classes: dict[str, str] | None = None) -> str:
    """
    Render base and discovered class definitions for NER prompts.

    Args:
        known_classes (dict[str, str] | None): Additional class definitions keyed by class name.

    Returns:
        str: Line-oriented class catalog for the model prompt.
    """
    lines: list[str] = ["Base spaCy entity classes:"]
    for class_name, description in SPACY_ENTITY_CLASS_DEFINITIONS.items():
        lines.append(f"- {class_name}: {description}")
    lines.append("Base agentic entity classes:")
    for class_name, description in AGENTIC_ENTITY_CLASS_DEFINITIONS.items():
        lines.append(f"- {class_name}: {description}")
    lines.append("Known discovered subtypes:")
    normalized_known: dict[str, str] = {}
    for class_name, description in (known_classes or {}).items():
        canonical_name: str = canonical_entity_class(class_name)
        if canonical_name == "CLS" or canonical_name in BASE_ENTITY_CLASS_DEFINITIONS:
            class_label = canonical_class_name(class_name)
        elif is_valid_entity_class_key(canonical_name):
            class_label = class_name_from_entity_class(canonical_name) or canonical_class_name(canonical_name)
        else:
            class_label = canonical_class_name(class_name)
        if not is_valid_class_name(class_label):
            continue
        normalized_known[class_label] = str(description or "").strip()
    if not normalized_known:
        lines.append("- none yet")
    else:
        for class_name in sorted(normalized_known):
            description = normalized_known[class_name] or "Discovered subtype."
            lines.append(f"- {class_name}: {description}")
    return "\n".join(lines)


def _canonical_base_entity_class(value: str) -> str:
    """
    Normalize an entity class base to a registered base label.

    Args:
        value (str): Raw class base.

    Returns:
        str: Registered base label or `MISC` fallback.
    """
    upper_value: str = str(value or "").strip().upper()
    if upper_value in BASE_ENTITY_CLASS_DEFINITIONS:
        return upper_value
    return "MISC"
