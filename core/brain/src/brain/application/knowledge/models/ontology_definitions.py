"""Static ontology definitions for the cognitive knowledge graph."""

from __future__ import annotations


SPACY_ENTITY_CLASS_DEFINITIONS: dict[str, str] = {
    "PERSON": "People, including fictional people.",
    "NORP": "Nationalities, religious groups, or political groups.",
    "FAC": "Buildings, airports, highways, bridges, and other facilities.",
    "ORG": "Companies, agencies, institutions, teams, systems, and organized groups.",
    "GPE": "Countries, cities, states, and geopolitical regions.",
    "LOC": "Non-GPE locations, mountain ranges, bodies of water, and spatial regions.",
    "PRODUCT": "Objects, vehicles, foods, software products, tools, and artifacts.",
    "EVENT": "Named events, incidents, meetings, procedures, and workflows.",
    "LAW": "Named laws, policies, rules, contracts, protocols, and standards.",
    "LANGUAGE": "Named languages and formal communication systems.",
    "DATE": "Absolute or relative dates and periods.",
    "TIME": "Times smaller than a day.",
    "PERCENT": "Percentage expressions.",
    "MONEY": "Monetary values.",
    "QUANTITY": "Measurements, counts, amounts, sizes, durations, and distances.",
    "ORDINAL": "Ordinal values.",
    "CARDINAL": "Numerals that do not fit another numeric type.",
    "MISC": "Fallback for abstract concepts or entities outside a more specific spaCy base class.",
}
"""spaCy-compatible base entity classes available to every NER frame."""


AGENTIC_ENTITY_CLASS_DEFINITIONS: dict[str, str] = {
    "FILE": "Files, documents, source artifacts, or persisted text objects.",
    "RULE": "Rules, policies, constraints, or normative instructions.",
    "BEHAVIOR": "Observed or prescribed behaviors, habits, interaction patterns, or tendencies.",
    "PROFILE": "Profiles, personas, capability records, or stable identity descriptions.",
    "COMMAND": "CLI commands, actions, invocations, or operational verbs exposed by tools.",
    "MODULE": "Code modules, packages, libraries, components, or importable units.",
    "CONFIG": "Configuration files, runtime settings, schemas, or tunable parameters.",
    "DATABASE": "Databases, stores, tables, indexes, or durable persistence layers.",
    "PROMPT": "Prompt templates, model instructions, message frames, or LLM task contracts.",
    "TOOL": "Tools, scripts, utilities, APIs, services, or executable capabilities.",
    "PROCESS": "Processes, procedures, pipelines, stages, or ordered operational methods.",
    "WORKFLOW": "Reusable workflows, routines, task flows, or orchestrated work patterns.",
}
"""Agent-friendly base entity classes available to every NER frame."""


BASE_ENTITY_CLASS_DEFINITIONS: dict[str, str] = {
    **SPACY_ENTITY_CLASS_DEFINITIONS,
    **AGENTIC_ENTITY_CLASS_DEFINITIONS,
}
"""All base entity classes available to every NER frame."""


CORE_ENTITY_CLASS_DEFINITIONS: dict[str, str] = {
    "CLS": "Knowledge-graph entity class definition; canonical_name stores the class key.",
    **BASE_ENTITY_CLASS_DEFINITIONS,
    "MISC.Concept": "Fallback class for a discovered abstract entity before a better subtype exists.",
    "MISC.ConsolidatedClaim": "Structural class for claims promoted from repeated evidence.",
}
"""Core class registry; domain subtypes are discovered from evidence."""


RELATION_TYPE_DEFINITIONS: dict[str, str] = {
    "mentions": "An entity label explicitly mentions another entity label.",
    "describes": "A subject describes another entity, value, or property.",
    "supports": "An entity or relation supports a claim.",
    "contradicts": "An entity or relation conflicts with a claim.",
    "supersedes": "A newer fact replaces an older one without deleting history.",
    "related_to": "A weak association when no more precise predicate is available.",
}
"""Minimal structural predicates; domain predicates are discovered from evidence."""


STATUS_VALUES: set[str] = {
    "active",
    "contested",
    "merged",
    "pending",
    "rejected",
}
"""Lifecycle states accepted for stored graph records."""
