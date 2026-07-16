# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Legacy workspace log migration service."""

from __future__ import annotations

# Standard Libraries Imports
import datetime
import re
import shutil
import sys
from pathlib import Path

# Application Modules Imports
from brain.application.logs.parsing import is_canonical_log_file, is_previous_log_file, log_file_name, to_slug


def migrate_legacy_md_logs(workspace_root: Path) -> list[str]:
    """Convert legacy `.md` and previous `.log` files to standard `.log.md` files."""
    logs_dir = workspace_root / "$agent" / "logs"
    if not logs_dir.exists():
        return []

    created: list[str] = []
    previous_log_files = [
        file_path
        for file_path in logs_dir.rglob("*.log")
        if file_path.is_file() and is_previous_log_file(file_path)
    ]
    for file_path in previous_log_files:
        target_file = file_path.with_name(f"{file_path.name}.md")
        if target_file.exists():
            rel_to_ws = file_path.relative_to(workspace_root).as_posix()
            sys.stderr.write(f"\033[91m[WARNING] Could not migrate {rel_to_ws}: target already exists.\033[0m\n")
            continue
        shutil.move(str(file_path), str(target_file))
        created.append(target_file.relative_to(workspace_root).as_posix())

    all_md_files = [
        file_path
        for file_path in logs_dir.rglob("*.md")
        if file_path.name != "index.md" and not is_canonical_log_file(file_path)
    ]
    legacy_files = []

    for file_path in all_md_files:
        date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", file_path.name)
        if date_match:
            legacy_files.append(file_path)
        else:
            rel_to_ws = file_path.relative_to(workspace_root).as_posix()
            sys.stderr.write(f"\033[90m[INFO] Skipping non-log markdown file: {rel_to_ws}\033[0m\n")

    if not legacy_files:
        return created

    by_date: dict[str, list[dict]] = {}
    migrated_files = []

    for file_path in legacy_files:
        parsed_entries = parse_legacy_md_file(file_path=file_path)
        if not parsed_entries:
            rel_to_ws = file_path.relative_to(workspace_root).as_posix()
            sys.stderr.write(
                "\033[91m[WARNING] Could not parse legacy log format in "
                f"{rel_to_ws}. Skipping migration to prevent content loss.\033[0m\n",
            )
            continue

        migrated_files.append(file_path)
        for entry in parsed_entries:
            date_text = entry["date"]
            if date_text not in by_date:
                by_date[date_text] = []
            if not any(existing["domain"] == entry["domain"] and existing["title"] == entry["title"] for existing in by_date[date_text]):
                by_date[date_text].append(entry)

    for date_text, entries in by_date.items():
        dt = datetime.datetime.strptime(date_text, "%d-%m-%Y")
        target_dir = logs_dir / dt.strftime("%Y-%m")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / log_file_name(date_text)

        parts_out = []
        for index, entry in enumerate(entries):
            desc = "\n".join("    " + line for line in entry["description"].splitlines())
            impact = "\n".join("    " + line for line in entry["impact"].splitlines())
            parts_out.append(
                f"\n## {date_text} 12:00 am\n"
                f"### ({entry['domain']}) [{entry['title']}]\n"
                f"  **Type:**\n    {entry['git_type']}\n"
                f"  **Why:**\n    Legacy log migration.\n"
                f"  **Description**\n{desc}\n"
                f"  **Impact**\n{impact}"
            )
            if index < len(entries) - 1:
                parts_out.append("\n---")

        if target_file.exists():
            current_content = target_file.read_text(encoding="utf-8").rstrip()
            target_file.write_text(f"{current_content}\n\n---\n\n" + "\n".join(parts_out).lstrip(), encoding="utf-8")
        else:
            target_file.write_text("\n".join([legacy_preamble(date_text), *parts_out]), encoding="utf-8")
        rel_created = target_file.relative_to(workspace_root).as_posix()
        if rel_created not in created:
            created.append(rel_created)

    backup_and_delete_migrated_logs(workspace_root=workspace_root, migrated_files=migrated_files)
    return created


def legacy_preamble(date_text: str) -> str:
    """Return the canonical preamble used for migrated log files."""
    return (
        f"# Lof file for date {date_text}\n\n"
        "Any entry will use structure:\n\n"
        "```md\n\n"
        "## DD-MM-YYYY HH:mm am/pm\n"
        "### (domain[.subdomain]) [Change Title]\n"
        "  **Type:**\n"
        "    What type of change is? Accepts [feature, fix, refactor, performance, improvement or documantation]\n"
        "  **Why:**\n"
        "    What's Reason/motivation for this change?\n"
        "  **Description**\n"
        "    What's elements and how has be changed?\n"
        "  **Impact**\n"
        "    What's the impact of maked change on the context?\n"
        "    ```\n\n"
        "    The entries are ordered in ascending order, from oldest to newest.\n\n"
        "---\n"
    )


def parse_legacy_md_file(file_path: Path) -> list[dict]:
    """Parse one legacy markdown log file into canonical entry dictionaries."""
    content = file_path.read_text(encoding="utf-8")
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", file_path.name)
    if not date_match:
        return []
    year, month, day = date_match.groups()
    date_text = f"{day}-{month}-{year}"

    content_norm = content.replace("\r\n", "\n")
    if content_norm.startswith("# "):
        content_norm = "\n" + content_norm
    parts = content_norm.split("\n# ")

    entries = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        header_line = lines[0].strip()

        header_match = re.search(r"^([^\/]+)\s*/\s*(.*)$", header_line)
        git_type = header_match.group(1).strip().lower() if header_match else "feature"
        title = header_match.group(2).strip() if header_match else header_line

        sections: dict[str, str] = {}
        current_section = None
        current_lines: list[str] = []
        for line in lines[1:]:
            if line.startswith("## "):
                if current_section:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = line[3:].strip().lower()
                current_lines = []
            else:
                current_lines.append(line)
        if current_section:
            sections[current_section] = "\n".join(current_lines).strip()

        topics = [
            topic.strip().strip("-").strip()
            for topic in sections.get("topics", "").splitlines()
            if topic.strip().strip("-").strip()
        ]
        domain = to_slug(topics[0]) if topics else "legacy"
        description = sections.get("description", "No description provided.")
        impact = sections.get("impact", "No impact provided.")
        verification = sections.get("verification", "")
        if verification:
            description += f"\n\nVerification:\n{verification}"

        entries.append({
            "date": date_text,
            "git_type": git_type,
            "title": title,
            "domain": domain,
            "description": description,
            "impact": impact,
        })
    return entries


def backup_and_delete_migrated_logs(workspace_root: Path, migrated_files: list[Path]) -> None:
    """Back up and remove legacy log files that migrated successfully."""
    if not migrated_files:
        return
    backup_dir = workspace_root / "$agent" / ".tmp" / "migrated_logs_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for file_path in migrated_files:
        try:
            shutil.copy2(file_path, backup_dir / file_path.name)
            sys.stderr.write(f"\033[92m[INFO] Legacy log backed up to $agent/.tmp/migrated_logs_backup/{file_path.name}\033[0m\n")
            file_path.unlink()
        except Exception as error:
            sys.stderr.write(f"\033[91m[ERROR] Failed to backup or delete legacy log {file_path.name}: {error}\033[0m\n")
