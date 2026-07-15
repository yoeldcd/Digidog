"""Action module to read pure Markdown content from a category/key."""

from __future__ import annotations

import argparse
import json
from brain.application.memory.paths import resolve_category_dir
from brain.application.memory.service import read_instance
from brain.presentation.terminal import render_placeholders, render_markdown, log_step



def handle(args: argparse.Namespace) -> int:
    """Read memory domain instance content or list domain directory structure."""
    log_step(args, 'Reading memory entry...')
    color_enabled = getattr(args, "color", False)
    try:
        domain = args.domain
        key = args.key

        # Check if the requested target is a domain/directory rather than a file
        is_dir_query = False
        try:
            if key is None:
                is_dir_query = resolve_category_dir(domain).is_dir()
            else:
                is_dir_query = resolve_category_dir(f"{domain}.{key}").is_dir()
        except Exception:
            pass

        if is_dir_query:
            if key is not None:
                domain = f"{domain}.{key}"

            cat_dir = resolve_category_dir(domain)
            if not cat_dir.exists():
                msg = f"__RED__Error: Memory domain '{domain}' does not exist.__RESET__"
                if args.json:
                    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
                else:
                    print(render_placeholders(msg, color_enabled))
                return 1

            if not getattr(args, "full_text", False):
                from brain.application.memory.indexing.index_service import load_index
                index_data = load_index()

                # Navigate index to the requested domain
                parts = [p.strip() for p in domain.split(".") if p.strip()]
                current = index_data
                for p in parts:
                    if p in current:
                        current = current[p].get("children", {})
                    else:
                        current = {}
                        break

                if args.json:
                    keys = []
                    def _gather_keys(d: dict, prefix: str = "") -> None:
                        for k, v in d.items():
                            if v.get("__type__") == "file":
                                keys.append(f"{prefix}{k}")
                            else:
                                _gather_keys(v.get("children", {}), f"{prefix}{k}.")
                    _gather_keys(current)
                    print(json.dumps({"ok": True, "domain": domain, "keys": keys}, ensure_ascii=False, indent=2))
                else:
                    entries_root = sum(1 for v in current.values() if v.get("__type__") in ("file", "dir"))
                    lines = [f"__BOLD____CYAN__{domain}/__RESET__ __DIM__(E: {entries_root})__RESET__"]

                    def _walk_index(
                        d: dict,
                        indent: str = "    ",
                        current_cat: str = "",
                        depth: int = 0,
                    ) -> None:
                        items = list(d.items())
                        uptime_order = getattr(args, "uptime_order", False)
                        limit = getattr(args, "limit", None)

                        if uptime_order:
                            items.sort(key=lambda x: x[1].get("mtime", 0), reverse=True)
                        else:
                            items.sort(key=lambda x: (x[1].get("__type__") != "dir", x[0].lower()))

                        rest_number = 0
                        if limit is not None and depth > 0 and len(items) > limit:
                            rest_number = len(items) - limit
                            items = items[:limit]

                        for i, (k, v) in enumerate(items):
                            is_last = (i == len(items) - 1) and (rest_number == 0)
                            connector = "└── " if is_last else "├── "
                            next_indent = indent + ("    " if is_last else "│   ")

                            mtime_str = ""
                            if uptime_order:
                                mtime = v.get("mtime", 0)
                                from datetime import datetime
                                dt_str = datetime.fromtimestamp(mtime).strftime("%d-%m-%Y %H:%M:%S")
                                mtime_str = f" __DIM__[ Up: {dt_str} ]__RESET__"

                            if v.get("__type__") == "dir":
                                entries = v.get("entries", 0)
                                lines.append(f"{indent}__DIM__{connector}__RESET____BOLD____CYAN__{k}/__RESET__ __DIM__(E: {entries})__RESET__{mtime_str}")
                                _walk_index(v.get("children", {}), next_indent, f"{current_cat}{k}.", depth + 1)
                            else:
                                sz, ln, ent = v.get("size", "0KB"), v.get("lines", "0"), v.get("entries", 0)
                                lines.append(f"{indent}__DIM__{connector}__RESET____GREEN__{k}__RESET__ __DIM__(Sz: {sz} L: {ln} E: {ent})__RESET__{mtime_str}")

                        if rest_number > 0:
                            lines.append(f"{indent}__DIM__└── ... {rest_number} more__RESET__")

                    _walk_index(current, current_cat=f"{domain}.")

                    lines.append("")
                    lines.append(f"__DIM__💡 Help: To read a specific subitem, use dot notation. Example: `py core.py get-memory-entry {domain}.<subcategory>.<key>`__RESET__")

                    print(render_placeholders("\n".join(lines), color_enabled))
                return 0

            results = {}
            for child in sorted(cat_dir.rglob("*.md"), key=lambda x: x.name):
                if child.is_file():
                    rel_path = child.relative_to(cat_dir).with_suffix("").as_posix()
                    key_name = rel_path.replace("/", ".")
                    results[key_name] = child.read_text(encoding="utf-8")

            if args.json:
                print(json.dumps({"ok": True, "domain": domain, "records": results}, ensure_ascii=False, indent=2))
            else:
                if not results:
                    msg = f"__YELLOW__Memory domain '{domain}' is empty.__RESET__"
                    print(render_placeholders(msg, color_enabled))
                    return 0

                for k, v in results.items():
                    header = f"\n# {domain}.{k}\n\n"
                    print(render_markdown(header + v, color_enabled))
            return 0

        else:
            if key is None and "." in domain:
                domain, key = domain.rsplit(".", 1)

            if key is None:
                cat_dir = resolve_category_dir(domain)
                if not cat_dir.exists():
                    msg = f"__RED__Error: Memory domain '{domain}' does not exist.__RESET__"
                    if args.json:
                        print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
                    else:
                        print(render_placeholders(msg, color_enabled))
                    return 1

            content = read_instance(domain, key)
            limit = getattr(args, "limit", None)
            if limit is not None:
                text_lines = content.splitlines()
                if len(text_lines) > limit:
                    rest = len(text_lines) - limit
                    content = "\n".join(text_lines[:limit]) + f"\n\n__DIM__... {rest} more lines__RESET__"

            if args.json:
                result = {
                    "ok": True,
                    "domain": domain,
                    "key": key,
                    "content": content
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(render_markdown(content, color_enabled), end="")
            return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            msg = f"__RED__Error: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 1
