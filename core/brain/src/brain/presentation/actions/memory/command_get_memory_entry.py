"""Read authorized Markdown memory entries through the public CLI action.

This presentation boundary resolves indexes, domain trees, and individual keys while
preserving output contracts and applying authority checks before content is rendered.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from brain.application.authority.memory_guard import (
    AUTHORITY_REQUIRED_MESSAGE,
    is_memory_access_allowed,
)
from brain.application.memory import paths as memory_paths
from brain.application.memory.indexing.index_service import load_index
from brain.application.memory.paths import resolve_category_dir
from brain.application.memory.service import read_instance
from brain.application.profiles.service import render_profile_template_variables
from brain.presentation.actions.memory.command_memory_structure import (
    _iter_structure_items,
    _project_visible_tree,
)
from brain.presentation.terminal import log_step, render_markdown, render_placeholders

_RAW_DOCUMENT_PREAMBLE = "<RAW DOCUMENT>"


def _render_profile_content(content: str) -> str:
    """Localize runtime placeholders after storage and authority checks succeed.

    Centralizing interpolation keeps profile-dependent paths consistent without altering
    persisted Markdown or the caller's selected rendering contract.

    Args:
        content: Raw memory content loaded from persistent storage.

    Returns:
        str: Memory content with localized runtime path variables.
    """

    return render_profile_template_variables(content)


def _render_authority_denial(
    args: argparse.Namespace,
    reason: str,
    color_enabled: bool,
) -> int:
    """Render an authority denial in the caller's selected output format.

    This boundary gives terminal and JSON callers the same fail-closed result while
    ensuring a denied request stops before protected memory content is exposed.

    Args:
        args: Parsed output options selecting JSON or terminal rendering.
        reason: Safe denial message returned by the authority guard.
        color_enabled: Whether terminal color placeholders are enabled.

    Returns:
        int: One because an authority denial stops command processing.
    """

    # Output contract: choose machine-readable or terminal-safe denial rendering.

    if getattr(args, "json", False):
        print(json.dumps({"ok": False, "error": reason}, ensure_ascii=False))

    # Terminal rendering: preserve color placeholders for interactive callers.

    else:
        print(render_placeholders(f"__RED__Error: {reason}__RESET__", color_enabled))

    return 1


def _render_entry_result(
    args: argparse.Namespace,
    domain: str,
    key: str,
    content: str,
    color_enabled: bool,
) -> int:
    """Render one resolved memory entry using the requested output format.

    The helper applies line limits before selecting raw-document, envelope JSON, or
    terminal Markdown output, keeping ordering and status semantics consistent for reads.

    Args:
        args: Parsed output and line-limit options.
        domain: Logical domain reported to the caller.
        key: Resolved memory entry key.
        content: Localized Markdown content to render.
        color_enabled: Whether terminal color placeholders are enabled.

    Returns:
        int: Zero after rendering the entry.
    """
    limit = getattr(args, "limit", None)

    # Line-limit policy: truncate localized content before calculating omitted lines.

    if limit is not None:
        text_lines = content.splitlines()

        # Truncation notice: expose omitted-line counts without changing retained content.

        if len(text_lines) > limit:
            rest = len(text_lines) - limit
            content = (
                "\n".join(text_lines[:limit])
                + f"\n\n__DIM__... {rest} more lines__RESET__"
            )

    # Raw-document contract: keep default JSON mode byte-oriented for Markdown consumers.

    if args.json and not getattr(args, "json_envelope", False):
        args.raw_document_output = True
        trailing = "" if content.endswith("\n") else "\n"

        print(f"{_RAW_DOCUMENT_PREAMBLE}\n{content}", end=trailing)

    # Envelope contract: provide structured metadata only when explicitly requested.

    elif args.json:
        result = {
            "ok": True,
            "domain": domain,
            "key": key,
            "content": content,
        }

        print(json.dumps(result, ensure_ascii=False, indent=2))

    # Terminal contract: render Markdown through the existing color-aware formatter.

    else:
        print(render_markdown(content, color_enabled), end="")

    return 0


def handle(args: argparse.Namespace) -> int:
    """Route a request to an authorized index, directory, or single memory key.

    The handler fails closed when authority is absent, filters restricted entries during
    traversal, and preserves established rendering, error, and traversal-order semantics.

    Args:
        args: Parsed options containing the target, authority, output mode, and limits.

    Returns:
        int: Zero when content is rendered; otherwise one after error.

    Raises:
        ValueError: Raised internally for a negative limit and converted to status 1.
        BrainStoreError: Raised internally for missing index storage and converted to
            status 1.
    """
    color_enabled = getattr(args, "color", False)
    authority = getattr(args, "authority", None)

    # Authority gate: reject missing caller identity before logging or reading memory.

    if not isinstance(authority, str) or not authority.strip():
        denial_reason = AUTHORITY_REQUIRED_MESSAGE

        return _render_authority_denial(args, denial_reason, color_enabled)

    log_step(args, 'Reading memory entry...')

    # Error boundary: preserve CLI status and output contracts for expected failures.

    try:
        domain = args.domain
        key = args.key
        limit = getattr(args, "limit", None)

        # Input validation: reject negative truncation limits before any memory read.

        if limit is not None and limit < 0:
            raise ValueError("--limit must be zero or greater.")

        # Global-index route: read the root index only for the bare index target.

        if domain == "index" and key is None:
            index_path = memory_paths.MEMORY_ROOT / "index.md"

            # File precondition: require the global index before reading its content.

            if not index_path.is_file():
                raise memory_paths.BrainStoreError("Global memory index does not exist.")

            raw_content = index_path.read_text(encoding="utf-8")
            allowed, denial_reason = is_memory_access_allowed(raw_content, authority)

            # Authority gate: authorize the root index before localization or rendering.

            if not allowed:
                return _render_authority_denial(args, denial_reason, color_enabled)

            content = _render_profile_content(content=raw_content)

            return _render_entry_result(
                args=args,
                domain="global",
                key="index",
                content=content,
                color_enabled=color_enabled,
            )

        # Target classification: distinguish directory traversal from single-entry reads.
        is_dir_query = False

        # Directory resolution probe: inspect the target path without changing command state.

        try:

            # Query resolution: classify a bare domain as a directory when it exists.

            if key is None:
                is_dir_query = resolve_category_dir(domain).is_dir()

            # Keyed resolution: classify the combined dotted path for nested directories.

            else:
                is_dir_query = resolve_category_dir(f"{domain}.{key}").is_dir()

        # Resolution fallback: treat path-probe failures as single-entry requests.

        except Exception:
            pass

        # Directory route: render an authority-filtered tree or the domain's full text.

        if is_dir_query:

            # Target normalization: combine domain and key for nested directory queries.

            if key is not None:
                domain = f"{domain}.{key}"

            cat_dir = resolve_category_dir(domain)

            # Directory precondition: verify the normalized memory domain still exists.

            if not cat_dir.exists():
                msg = f"__RED__Error: Memory domain '{domain}' does not exist.__RESET__"

                # Failure output: preserve the safe message in JSON or terminal mode.

                if args.json:
                    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))

                # Terminal failure: render the same message with requested color handling.

                else:
                    print(render_placeholders(msg, color_enabled))

                return 1

            # Tree mode: traverse the authority-projected index without exposing restricted branches.

            if not getattr(args, "full_text", False):
                index_data = load_index(include_indexes=True)
                visible_index = _project_visible_tree(index_data, authority)
                parts = [p.strip() for p in domain.split(".") if p.strip()]
                current: dict[str, object] = visible_index

                # Navigation loop: follow each requested segment through the visible index tree.

                for p in parts:

                    # Branch guard: stop when a requested segment is absent from the visible tree.

                    node = current.get(p)

                    if not isinstance(node, dict):
                        current = {}

                        break

                    children = node.get("children", {})
                    current = children if isinstance(children, dict) else {}

                # Tree output: choose a machine-readable key list or interactive tree text.

                if args.json:
                    keys: list[str] = []
                    uptime_order = getattr(args, "uptime_order", False)

                    def _gather_keys(d: dict[str, object], prefix: str = "") -> None:
                        """Collect visible leaf keys recursively from an index branch.

                        The branch is already projected for the caller's authority, so this
                        helper preserves that security boundary while rebuilding dotted keys.

                        Args:
                            d: Index dictionary branch.
                            prefix: Current key prefix string.

                        Returns:
                            None.
                        """

                        # Leaf traversal: retain shared ordering and per-level limit semantics.

                        for k, v in _iter_structure_items(d, uptime_order, limit):

                            # Leaf check: append files without exposing directory metadata.

                            if v.get("__type__") == "file":
                                keys.append(f"{prefix}{k}")

                                continue

                            children = v.get("children", {})

                            # Recursion guard: descend only through typed child mappings.

                            if isinstance(children, dict):
                                _gather_keys(children, f"{prefix}{k}.")

                    _gather_keys(current)

                    print(json.dumps({"ok": True, "domain": domain, "keys": keys}, ensure_ascii=False, indent=2))

                # Terminal tree output: render the same visible branch with navigation metadata.

                else:
                    uptime_order = getattr(args, "uptime_order", False)
                    entries_root = len(_iter_structure_items(current, uptime_order))
                    lines = [f"__BOLD____CYAN__{domain}/__RESET__ __DIM__(E: {entries_root})__RESET__"]

                    def _walk_index(
                        d: dict[str, object],
                        indent: str = "    ",
                    ) -> None:
                        """Render an authority-filtered index branch as terminal tree lines.

                        Shared ordering and truncation rules keep this view aligned with the
                        JSON key listing while recursion is limited to typed child mappings.

                        Args:
                            d: Index dictionary branch.
                            indent: Line indentation prefix.
                        Returns:
                            None.
                        """
                        uptime_order = getattr(args, "uptime_order", False)
                        items = _iter_structure_items(d, uptime_order, limit)
                        all_items = _iter_structure_items(d, uptime_order)
                        rest_number = max(0, len(all_items) - len(items))

                        # Item traversal: apply shared visibility, ordering, and limit policies.

                        for i, (k, v) in enumerate(items):

                            is_last = (i == len(items) - 1) and (rest_number == 0)
                            connector = "└── " if is_last else "├── "
                            next_indent = indent + ("    " if is_last else "│   ")
                            mtime_str = ""

                            # Timestamp policy: add modification time only in uptime-order mode.

                            if uptime_order:
                                mtime = v.get("mtime", 0)

                                # Timestamp guard: format only numeric metadata from the index.

                                if isinstance(mtime, (int, float)):
                                    dt_str = datetime.fromtimestamp(float(mtime)).strftime("%d-%m-%Y %H:%M:%S")
                                    mtime_str = f" __DIM__[ Up: {dt_str} ]__RESET__"

                            # Node rendering: preserve distinct directory and file metadata.

                            if v.get("__type__") == "dir":
                                entries = v.get("entries", 0)
                                tree_line = (
                                    f"{indent}__DIM__{connector}__RESET__"
                                    f"__BOLD____CYAN__{k}/__RESET__ __DIM__(E: {entries})__RESET__{mtime_str}"
                                )

                                lines.append(tree_line)
                                children_dict = v.get("children", {})

                                # Recursion guard: continue only through a valid child mapping.

                                if isinstance(children_dict, dict):
                                    _walk_index(children_dict, next_indent)

                            # File rendering: format leaf metadata when the node is not a directory.

                            else:
                                sz, ln, ent = v.get("size", "0KB"), v.get("lines", "0"), v.get("entries", 0)
                                tree_line = (
                                    f"{indent}__DIM__{connector}__RESET__"
                                    f"__GREEN__{k}__RESET__ __DIM__(Sz: {sz} L: {ln} E: {ent})__RESET__{mtime_str}"
                                )

                                lines.append(tree_line)

                        # Truncation notice: make omitted siblings visible in the terminal tree.

                        if rest_number > 0:
                            lines.append(f"{indent}__DIM__└── ... {rest_number} more__RESET__")

                    _walk_index(current)

                    lines.append("")
                    help_hint = (
                        f"__DIM__💡 Help: To read a specific subitem, use dot notation. "
                        f"Example: `py core.py get-memory-entry {domain}.<subcategory>.<key>`__RESET__"
                    )

                    lines.append(help_hint)
                    print(render_placeholders("\n".join(lines), color_enabled))

                return 0

            # Full-text route: read each Markdown file while applying per-entry authority checks.
            results: dict[str, str] = {}

            # File traversal: scan Markdown descendants in stable filename order.

            for child in sorted(cat_dir.rglob("*.md"), key=lambda x: x.name):

                # File precondition: ignore directory entries that are not regular files.

                if child.is_file():
                    rel_path = child.relative_to(cat_dir).with_suffix("").as_posix()
                    key_name = rel_path.replace("/", ".")

                    # File read boundary: tolerate unreadable Markdown and continue the scan.

                    try:
                        raw_content = child.read_text(encoding="utf-8")

                    # Read fallback: skip only the unreadable child, retaining other entries.

                    except (OSError, UnicodeError):
                        continue

                    allowed, _ = is_memory_access_allowed(raw_content, authority)

                    # Authority gate: omit unauthorized files before they enter the result mapping.

                    if not allowed:
                        continue

                    results[key_name] = _render_profile_content(content=raw_content)

            # Full-text output: emit a structured dictionary or ordered terminal documents.

            if args.json:
                print(json.dumps({"ok": True, "domain": domain, "entries": results}, ensure_ascii=False, indent=2))

            # Terminal full-text output: report emptiness or render authorized entries.

            else:

                # Empty-domain contract: return success with a warning when nothing is visible.

                if not results:
                    msg = f"__YELLOW__Memory domain '{domain}' is empty.__RESET__"
                    print(render_placeholders(msg, color_enabled))

                    return 0

                # Entry rendering: preserve discovery order for each authorized Markdown file.

                for k, v in results.items():
                    header = f"\n# {domain}.{k}\n\n"
                    print(render_markdown(header + v, color_enabled))

            return 0

        # Single-entry route: read and render one resolved memory document.

        else:

            # Dotted-key normalization: split shorthand into its domain and final key.

            if key is None and "." in domain:
                domain, key = domain.rsplit(".", 1)

            # Domain precondition: verify a bare domain exists before resolving its entry.

            if key is None:
                cat_dir = resolve_category_dir(domain)

                # Directory guard: report an unknown domain before attempting instance access.

                if not cat_dir.exists():
                    msg = f"__RED__Error: Memory domain '{domain}' does not exist.__RESET__"

                    # Failure output: keep JSON and terminal callers on the same error path.

                    if args.json:
                        print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))

                    # Terminal failure: apply color-aware rendering without changing the message.

                    else:
                        print(render_placeholders(msg, color_enabled))

                    return 1

            raw_instance_content = read_instance(domain, key)
            allowed, denial_reason = is_memory_access_allowed(raw_instance_content, authority)

            # Authority gate: verify the target header before profile interpolation or rendering.

            if not allowed:
                return _render_authority_denial(args, denial_reason, color_enabled)

            content = _render_profile_content(content=raw_instance_content)

            return _render_entry_result(
                args=args,
                domain=domain,
                key=key,
                content=content,
                color_enabled=color_enabled,
            )

    # Failure boundary: serialize unexpected storage or rendering errors in the selected mode.

    except Exception as exc:

        # Structured failure: keep automation responses parseable and non-successful.

        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))

        # Terminal failure: preserve the existing color-aware error response.

        else:
            msg = f"__RED__Error: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))

        return 1
