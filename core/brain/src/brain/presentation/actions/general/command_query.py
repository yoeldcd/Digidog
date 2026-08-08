# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module for the global brain query command."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json

# Application Modules Imports
from brain.presentation.terminal import render_placeholders, log_step
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO, QueryDeepResponseDTO, QueryPageDTO, QuerySourceRefDTO
from brain.application.querying.service import query_deep, query_global, query_global_page
from brain.presentation.views.query.results import print_human_deep_response, print_human_results





def _utc_time_value(date_value: str, time_value: str) -> str:
    if len(date_value) == 10 and date_value[2] == "-" and date_value[5] == "-":
        day, month, year = date_value.split("-")
        date_value = f"{year}-{month}-{day}"
    return f"{date_value}T{time_value or '00:00:00'}Z"

def _message_time_value(value: str) -> str:
    return value.replace("+00:00", "Z") if value else ""

def _picture_absolute_path(scope: str, relative_path: str) -> str:
    from brain.infrastructure.runtime.paths import resolve_picture_path
    return str(resolve_picture_path(scope=scope or "local", relative_path=relative_path).resolve())

def _canonical_log_record(result: GlobalQueryResultDTO):
    """Hydrate canonical log fields from the indexed log database."""
    try:
        from brain.application.logs.store import connect_logs_database, get_log_entry_by_id
        from brain.infrastructure.runtime.paths import get_workspace_root
        from brain.application.logs.records import LogEntryRecord
        ws = get_workspace_root()
        sp = str(result.data.get("source_path") or result.source_ref.path or "")
        if sp:
            with connect_logs_database(workspace_root=ws) as conn:
                row = conn.execute("SELECT * FROM log_entries WHERE source_path = ? LIMIT 1", (sp,)).fetchone()
                if row is not None:
                    return LogEntryRecord(timestamp=row["timestamp"], domain=row["domain"], title=row["title"], change_type=row["change_type"], why=row["why"], description=row["description"], impact=row["impact"], source_path=row["source_path"] or "", source_mtime=float(row["source_mtime"] or 0), source_size=int(row["source_size"] or 0), record_id=int(row["id"]))
        rid = result.data.get("record_id") or result.data.get("log_record_id")
        if rid:
            return get_log_entry_by_id(workspace_root=ws, record_id=int(rid))
    except Exception:
        return None
    return None

def _reader_parameters(command: str) -> tuple[str, str]:
    import re
    dm = re.search(r"(?:-d|--date)\s+(\S+)", command)
    tm = re.search(r"--time\s+(\S+)", command)
    return (dm.group(1) if dm else "", tm.group(1) if tm else "")

def _compact_deep_payload(response: QueryDeepResponseDTO) -> dict[str, object]:
    compact = _compact_result_map(response.results)
    compact["summary"] = response.answer or ""
    compact["sub_queries"] = [sq.text for sq in response.subqueries]
    return compact
def _compact_result_map(results: list[GlobalQueryResultDTO]) -> dict[str, object]:
    """Project results into the compact public source schema."""
    payload: dict[str, object] = {}
    access_commands: dict[str, str] = {
        "memory": "get-memory-entry \"{key}\"",
        "diary": "read-diary --datetime {date} --time {time}",
        "logs": "read-log --datetime {date} --time {time}",
    }
    for result in results:
        source = result.source or "memory"
        source_type = result.source_ref.source_type
        if source == "policies":
            payload.setdefault("policies", {})[result.title] = result.content.body or result.content.excerpt or result.text
            continue
        if source == "pictures":
            items = payload.setdefault("pictures", [])
            items.append({"path": _picture_absolute_path(result.source_ref.scope, result.source_ref.path.removeprefix("pictures/")), "description": result.content.body or result.content.excerpt, "scope": result.source_ref.scope})
            continue
        if source == "messages":
            items = payload.setdefault("messages", [])
            items.append({"content": result.content.body or result.text or result.content.excerpt, "time": _message_time_value(result.content.location), "scope": result.source_ref.scope})
            continue
        if source_type == "diary":
            items = payload.setdefault("diary", [])
            cmd = result.source_ref.read_command
            dv, tv = _reader_parameters(cmd)
            items.append({"title": result.source_ref.title or result.data.get("entry_title") or result.title, "time": _utc_time_value(dv, tv)})
            continue
        if source == "logs":
            items = payload.setdefault("logs", [])
            d = result.data
            ts = str(d.get("timestamp") or "")
            items.append({
                "title": str(d.get("title") or result.source_ref.title or result.title or ""),
                "domain": str(d.get("domain") or ""),
                "time": _utc_time_value(ts[:10], ts[11:16] if len(ts) >= 16 else "") if ts else _utc_time_value("", ""),
            })
            continue
        if result.entities:
            payload.setdefault("knowledge", {}).setdefault("entities", []).extend({"name": e.name, "type": e.entity_class, "description": e.description, "confidence": e.confidence} for e in result.entities)
        if result.relations:
            payload.setdefault("knowledge", {}).setdefault("relations", []).extend({"subject": r.subject.name, "predicate": r.predicate, "object": r.object.name, "confidence": r.confidence} for r in result.relations)
        if source == "memory":
            items = payload.setdefault("memory", [])
            mk = result.data.get("key") or result.data.get("memory_key") or ""
            if not mk:
                mp = str(result.source_ref.path or result.data.get("path") or "")
                mp = mp.replace("\\\\", "/")
                if mp.startswith("memory/"):
                    mp = mp[len("memory/"):]
                if mp.endswith(".md"):
                    mp = mp[:-3]
                mk = mp.replace("/", ".")
            items.append({"content": result.content.body or result.text or result.content.excerpt, "key": mk, "scope": result.source_ref.scope or "local"})
    if access_commands:
        payload["access_commands"] = access_commands
    return payload
def _live_policy_results() -> list[GlobalQueryResultDTO]:
    """Project every workspace policy record as mandatory query context evidence."""
    from brain.application.records.service import list_live_records

    return [
        GlobalQueryResultDTO(source="policies", mechanism="live_context", kind="live_policy", rank=1.0, title=record.id, text=record.text,
            data={"id": record.id, "created_at": record.created_at},
            content=QueryContentDTO(title=record.id, excerpt=record.text, body=record.text),
            source_ref=QuerySourceRefDTO(scope="local", source_type="policies", domain="policies",
                read_command="show-policies --json", path="$agent/data/records.json#{}".format(record.id),
                title=record.id, structure=["policies", record.id]))
        for record in list_live_records()
    ]

def _configure_narration_table(args: argparse.Namespace, results: list[GlobalQueryResultDTO]) -> None:
    """Expose query evidence visually without feeding row content to narration."""
    args.narration_output = ''
    args.narration_table_columns = ['source', 'domain', 'content|entity']
    args.narration_table_rows = [
        {'source': result.source, 'domain': result.source_ref.domain,
         'content|entity': result.content.excerpt or result.title}
        for result in results
    ]

def handle(args: argparse.Namespace) -> int:
    """
    Execute a global query across knowledge and memory backends.

    Args:
        args (argparse.Namespace): Parsed command arguments.

    Returns:
        int: Process status code.
    """
    log_step(args, "Querying brain knowledge...")
    color_enabled: bool = getattr(args, "color", False)

    try:
        domain, query_text = _resolve_query_arguments(args=args)
        args.narration_query = query_text
        if not query_text:
            msg = "__RED__Error: query string is required.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        if args.deep:
            response_dto: QueryDeepResponseDTO = query_deep(
                text=query_text,
                domain=domain,
                limit=args.limit,
                source=_resolve_query_source(args=args),
                mechanism=args.mechanism,
                knowledge_scope=_resolve_query_knowledge_scope(args=args),
            )
            live_policies = _live_policy_results()
            response_dto.results = live_policies + response_dto.results
            _configure_narration_table(args, response_dto.results)
            for subquery in response_dto.subqueries:
                subquery.results = live_policies + subquery.results
            if args.json:
                args.narration_result_count = len(getattr(response_dto, "results", []) or [])
                payload = response_dto.model_dump(mode="json") if getattr(args, "verbose_schema", False) else _compact_deep_payload(response_dto)
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0
            print_human_deep_response(
                response_dto=response_dto,
                color_enabled=color_enabled,
                explain=bool(args.explain),
            )
            args.narration_result_count = len(getattr(response_dto, "results", []) or [])
            return 0

        page: int = max(1, int(args.page))
        page_size: int = int(args.page_size)
        if page_size not in {0, 10, 25, 50, 100}:
            raise ValueError("page-size must be one of: 0, 10, 25, 50, 100")

        response_page: QueryPageDTO = query_global_page(
            text=query_text,
            domain=domain,
            page=page,
            page_size=page_size,
            source=_resolve_query_source(args=args),
            mechanism=args.mechanism,
            knowledge_scope=_resolve_query_knowledge_scope(args=args),
            explain=bool(args.explain),
        )
        results: list[GlobalQueryResultDTO] = list(response_page.items)
        _configure_narration_table(args, results)

        if args.json:
            args.narration_result_count = response_page.totalItems
            payload = response_page.model_dump(mode="json")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        print_human_results(
            results=results,
            query_text=query_text,
            color_enabled=color_enabled,
            explain=bool(args.explain),
        )
        args.narration_result_count = len(results)
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            msg = f"__RED__Error during query: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 1


def _resolve_query_arguments(args: argparse.Namespace) -> tuple[str, str]:
    """
    Resolve the legacy positional `domain query` contract.

    Args:
        args (argparse.Namespace): Parsed command arguments.

    Returns:
        tuple[str, str]: Memory domain filter and query text.
    """
    domain: str | None = args.domain
    query_text: str | None = args.query

    if domain is not None and query_text is None:
        return "all", domain
    if domain is not None and query_text is not None:
        return domain, query_text
    return "all", ""


def _resolve_query_source(args: argparse.Namespace) -> str:
    """
    Resolve source selection from `--source` and `--messages`.

    Args:
        args (argparse.Namespace): Parsed command arguments.

    Returns:
        str: Selected query source.
    """
    if bool(getattr(args, "messages", False)):
        return "messages"
    return getattr(args, "source", "all") or "all"





def _resolve_query_knowledge_scope(args: argparse.Namespace) -> str:
    """Resolve knowledge database scope from its canonical option or alias."""
    scope: str | None = getattr(args, "scope", None)
    return scope or getattr(args, "knowledge_scope", "all") or "all"
