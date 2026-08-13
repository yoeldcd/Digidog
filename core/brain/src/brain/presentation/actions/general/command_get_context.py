# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to hydrate the agent's context with memories."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
from pathlib import Path

from brain.application.profiles.service import profile_summaries
from brain.infrastructure.runtime.paths import get_agent_home, get_workspace_root
from brain.presentation.terminal import log_step, render_markdown, render_placeholders


def _looks_like_embedding_failure(error: object) -> bool:
    """Detect embedding failures without making get-context depend on vectorstore imports."""
    try:
        from brain.infrastructure.vectorstores.recovery import is_embedding_unavailable_error

        return is_embedding_unavailable_error(error)
    except Exception:
        message = str(error).lower()
        return "embedding" in message or "winerror 10013" in message


def _embedding_notice(error: object | None = None) -> dict[str, object]:
    """Return a deterministic-context notice with a recovery guide."""
    return {
        "kind": "notice",
        "title": "Embedding Notice",
        "status": "warning",
        "summary": "Embedding model unavailable.",
        "body": "Retry with elevated permissions: `python .\\$agent\\scripts\\brain.py update-vectorstore`.",
        "error": str(error or ""),
    }


def _profiles_section(agent_home: Path) -> dict[str, object]:
    """Build structured profile context."""
    profiles_dir = agent_home / "memory" / "profiles"
    if not profiles_dir.exists():
        return {
            "kind": "profiles",
            "title": "Available Profiles",
            "status": "empty",
            "summary": "No profiles directory found.",
            "items": [],
        }
    profiles = profile_summaries(profiles_dir)
    return {
        "kind": "profiles",
        "title": "Available Profiles",
        "status": "ok" if profiles else "empty",
        "summary": f"{len(profiles)} profiles available.",
        "items": profiles,
    }


def _memory_section() -> dict[str, str]:
    """Build compact operational guidance for durable memory access."""
    return {
        "kind": "memory",
        "use_when": (
            "Use when durable context, preferences, relationships, notes, "
            "or reusable knowledge must be read or updated."
        ),
        "get_structure_command": "memory-structure",
        "read_entry_template": "get-memory-entry <DOMAIN> [KEY]",
        "write_item_template": "set-memory-entry <DOMAIN> <KEY> <CONTENT>",
    }


def _diary_header_items(path: Path, content: str) -> list[dict[str, object]]:
    """Build compact retrieval records for the headings in one diary file."""
    header_items: list[dict[str, object]] = []
    headers = [line[3:].strip() for line in content.splitlines() if line.startswith("## ")]
    if not headers:
        return [
            {
                "title": path.stem,
                "retrieve_command": f"read-diary -d {path.stem}",
            }
        ]
    for header in headers:
        time_match = re.match(rf"^{re.escape(path.stem)}\s+(\d{{2}}:\d{{2}})(?::\d{{2}})?\b", header)
        time_argument = f" --time {time_match.group(1)}" if time_match else ""
        title = re.sub(
            rf"^{re.escape(path.stem)}\s+\d{{2}}:\d{{2}}(?::\d{{2}})?\s*-\s*",
            "",
            header,
        ).strip() or header
        header_items.append({
            "title": title,
            "retrieve_command": f"read-diary -d {path.stem}{time_argument}",
        })
    return header_items


def _policies_section() -> dict[str, object]:
    """Build the always-on local policies section for every hydrated context."""
    from brain.application.records.service import list_live_records

    policies = list_live_records()
    policy_count = len(policies)
    return {
        "kind": "policies",
        "title": "Workspace Local Policies",
        "status": "ok",
        "summary": "{} always-on local {}.".format(policy_count, "policy" if policy_count == 1 else "policies"),
        "policies": {policy.id: policy.text for policy in policies},
    }

def _diary_section(agent_home: Path, limit_diary: int) -> dict[str, object]:
    """Build structured diary index context."""
    diary_dir = agent_home / "memory" / "diary"
    diary_files: list[tuple[datetime.date, Path]] = []
    if diary_dir.exists():
        for path in diary_dir.rglob("*.md"):
            try:
                diary_files.append((datetime.datetime.strptime(path.stem, "%d-%m-%Y").date(), path))
            except ValueError:
                continue
    diary_files.sort(key=lambda item: item[0], reverse=True)
    items: list[dict[str, object]] = []
    for _, path in diary_files[:limit_diary]:
        try:
            content = path.read_text(encoding="utf-8")
            items.extend(_diary_header_items(path, content))
        except Exception:
            items.append({
                "title": path.stem,
                "retrieve_command": f"read-diary -d {path.stem}",
            })
    items = [{"id": index, **item} for index, item in enumerate(items, start=1)]
    return {
        "kind": "diary",
        "title": "Recent Diary Entries",
        "status": "ok" if items else "empty",
        "summary": f"{len(items)} diary context cards indexed.",
        "items": items,
    }


def _parse_log_index_items(domain_lines: list[str]) -> list[dict[str, object]]:
    """Parse rendered log-index Markdown into compact domain records."""
    items: list[dict[str, object]] = []
    stack: list[str] = []
    for line in domain_lines:
        heading = re.match(r"^(#{2,4})\s+(.+)$", line)
        if heading:
            depth = len(heading.group(1)) - 2
            label = heading.group(2).strip()
            parent = stack[depth - 1] if depth > 0 and len(stack) >= depth else ""
            path = f"{parent}.{label}" if parent and not label.startswith(f"{parent}.") else label
            stack = stack[:depth]
            stack.append(path)
            continue
        item = re.match(
            r"^\*\s+([^:]+)\s*:\s*\(([^)]+)\)\s+last entry\s+`([^`]+)`"
            r"(?:\s+\|\s+title:\s+(.+))?$",
            line,
        )
        if not item or not stack:
            continue
        terminal_label = item.group(1).strip()
        label = item.group(4).strip() if item.group(4) else terminal_label
        change_type = item.group(2).strip()
        command = item.group(3).strip()
        parent_domain = stack[-1]
        domain = f"{parent_domain}.{terminal_label}" if not terminal_label.startswith("(") else parent_domain
        items.append({
            "id": len(items) + 1,
            "domain": domain,
            "last_change": {
                "title": label,
                "type": change_type,
                "retrieve_command": command,
            },
        })
    return items


def _logs_section(
    workspace_root: Path,
    domain_filter: str | None = None,
) -> tuple[dict[str, object], str | None]:
    """Build structured workspace changelog context."""
    embedding_warning: str | None = None
    try:
        from brain.application.logs.store import rendered_logs_index

        content = rendered_logs_index(workspace_root=workspace_root, domain_filter=domain_filter)
        lines = content.splitlines()
        domain_lines: list[str] = []
        in_domains = False
        for line in lines:
            if line.startswith("## "):
                in_domains = True
            if in_domains:
                domain_lines.append(line)
        items = _parse_log_index_items(domain_lines)
        return {
            "kind": "logs",
            "title": "Workspace Changelog Index",
            "status": "ok" if items else "empty",
            "summary": f"{len(items)} log domains indexed." if items else "No registered logs.",
            "items": items,
        }, embedding_warning
    except Exception as exc:
        if _looks_like_embedding_failure(exc):
            embedding_warning = str(exc)
        return {
            "kind": "logs",
            "title": "Workspace Changelog Index",
            "status": "empty",
            "summary": "No registered logs.",
            "items": [],
        }, embedding_warning


def _system_section() -> dict[str, object]:
    """Build structured diagnostics context."""
    from brain.application.memory.diagnostics import doctor_report

    report = doctor_report()
    return {
        "kind": "system",
        "title": "System Checkings",
        "status": "ok" if report["ok"] else "error",
        "summary": (
            "Memory layout compliance check passed."
            if report["ok"]
            else "Memory layout compliance check has errors."
        ),
        "errors": report.get("errors", []),
    }


def _build_payload(args: argparse.Namespace) -> dict[str, object]:
    """Build a structured context payload."""
    limit_diary = args.limit_diary
    workspace_root = get_workspace_root()
    agent_home = get_agent_home()
    sections: list[dict[str, object]] = [
        {
            "kind": "workspace",
            "title": "Workspace Root",
            "status": "ok",
            "summary": "Directory index for memories and profiles.",
            "path": workspace_root.as_posix(),
        },
        _memory_section(),
        _policies_section(),
    ]

    log_step(args, "[1/4] Loading available profiles...")
    sections.append(_profiles_section(agent_home))

    log_step(args, "[2/4] Indexing recent diary entries...")
    sections.append(_diary_section(agent_home, limit_diary))

    log_step(args, "[3/4] Loading workspace change domains...")
    domain_filter = getattr(args, "domain", "") or ""
    if domain_filter:
        from brain.application.logs.query_service import resolve_query_log_domain
        from brain.application.logs.store import list_log_domains

        domain_filter = resolve_query_log_domain(domain_filter, list_log_domains(workspace_root=workspace_root)) or ""
    logs_section, embedding_warning = _logs_section(workspace_root, domain_filter=domain_filter)
    sections.append(logs_section)

    log_step(args, "[4/4] Running system diagnostics...")
    sections.append(_system_section())

    explicit_embedding_warning = getattr(args, "embedding_unavailable", None)
    if explicit_embedding_warning or embedding_warning:
        sections.append(_embedding_notice(explicit_embedding_warning or embedding_warning))

    return {
        "ok": True,
        "workspaceRoot": workspace_root.as_posix(),
        "agentHome": agent_home.as_posix(),
        "limitDiary": limit_diary,
        "sections": sections,
    }


def _render_payload(payload: dict[str, object]) -> str:
    """Render the structured context payload as Markdown."""
    output: list[str] = [
        "# AGENT CONTEXT HYDRATION",
        f"**Workspace Root:** `{payload['workspaceRoot']}`",
        "Use this directory index to know what memories and profiles are available. Read them explicitly when needed.",
        "",
    ]
    for section in payload["sections"]:
        kind = section["kind"]
        if kind == "workspace":
            continue
        output.append(f"## {section.get('title') or kind.title()}")
        if kind == "profiles":
            items = section.get("items", [])
            if items:
                output.extend(f"- **{item['name']}**: read running `{item['retrieve_command']}`" for item in items)
            else:
                output.append("*(No profiles found)*")
        elif kind == "memory":
            output.extend([
                section["use_when"],
                f"- Structure: `{section['get_structure_command']}`",
                f"- Read: `{section['read_entry_template']}`",
                f"- Write: `{section['write_item_template']}`",
            ])
        elif kind == "policies":
            output.append(section["summary"])
            policies = section.get("policies", {})
            if policies:
                output.extend("- **{}**: {}".format(policy_id, text) for policy_id, text in policies.items())
            else:
                output.append("*(No local policies)*")
        elif kind == "diary":
            items = section.get("items", [])
            if items:
                for item in items:
                    output.append(f"- **{item['title']}**: `{item['retrieve_command']}`")
            else:
                output.append("*(No diary entries found)*")
        elif kind == "logs":
            items = section.get("items", [])
            output.extend(
                f"- {item['domain']}: ({item['last_change']['type']}) "
                f"{item['last_change']['title']} `{item['last_change']['retrieve_command']}`"
                for item in items
            )
            if not items:
                output.append("No registered logs")
        elif kind == "system":
            if section["status"] != "ok":
                output.append("Memory layout compliance check: **ERRORS DETECTED**")
                output.extend(f"- ERR: {error}" for error in section.get("errors", []))
        elif kind == "notice":
            output.append(section.get("summary", ""))
            output.append(section.get("body", ""))
        output.append("")
    return "\n".join(output)


def handle(args: argparse.Namespace) -> int:
    """Build and render the compact session-context hydration payload.

    Args:
        args (argparse.Namespace): Parsed context options selecting output format,
            diary limit, domain restriction, and activity logging.

    Returns:
        int: Zero when context is rendered; otherwise one after reporting an error.
    """
    color_enabled = getattr(args, "color", False)
    try:
        payload = _build_payload(args)
        args.json_payload = payload
        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        print(render_markdown(_render_payload(payload), color_enabled))
        return 0
    except Exception as exc:
        msg = f"__RED__Error during context retrieval: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
