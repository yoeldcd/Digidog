"""Markdown section extraction and update helpers."""

from __future__ import annotations


def extract_from_markdown(content: str, target_key: str) -> str | None:
    """Try to extract a section or list item matching target_key from markdown content."""
    target = target_key.lower().strip()
    lines = content.splitlines()

    header_idx = -1
    header_level = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            parts = stripped.split(None, 1)
            if len(parts) == 2:
                level = len(parts[0])
                header_name = parts[1].lower().strip().strip("*:_#")
                if header_name == target:
                    header_idx = idx
                    header_level = level
                    break

    if header_idx != -1:
        extracted = []
        for line in lines[header_idx + 1:]:
            stripped = line.strip()
            if stripped.startswith("#"):
                parts = stripped.split(None, 1)
                if len(parts) == 2:
                    level = len(parts[0])
                    if level <= header_level:
                        break
            extracted.append(line)
        return "\n".join(extracted).strip()

    list_idx = -1
    list_indent = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("-", "*", "+")):
            marker_stripped = stripped[1:].strip()
            key_name = marker_stripped.split(":", 1)[0].strip().strip("*:_#`")
            if key_name.lower() == target:
                list_idx = idx
                list_indent = len(line) - len(line.lstrip())
                break

    if list_idx != -1:
        extracted = []
        first_line = lines[list_idx].strip()
        marker_stripped = first_line[1:].strip()
        if ":" in marker_stripped:
            after_colon = marker_stripped.split(":", 1)[1].strip()
            if after_colon:
                extracted.append(after_colon)

        for line in lines[list_idx + 1:]:
            if not line.strip():
                extracted.append(line)
                continue
            indent = len(line) - len(line.lstrip())
            if indent > list_indent:
                extracted.append(line)
            else:
                break
        return "\n".join(extracted).strip()

    return None


def update_markdown(content: str, target_key: str, new_value: str | None) -> str:
    """Update or delete a section/key in the markdown content."""
    target = target_key.lower().strip()
    lines = content.splitlines()

    list_idx = -1
    list_indent = 0
    end_idx = -1
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("-", "*", "+")):
            marker_stripped = stripped[1:].strip()
            key_name = marker_stripped.split(":", 1)[0].strip().strip("*:_#`")
            if key_name.lower() == target:
                list_idx = idx
                list_indent = len(line) - len(line.lstrip())
                break

    if list_idx != -1:
        end_idx = list_idx + 1
        for idx in range(list_idx + 1, len(lines)):
            line = lines[idx]
            if not line.strip():
                end_idx = idx + 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent > list_indent:
                end_idx = idx + 1
            else:
                break

        if new_value is None:
            new_lines = lines[:list_idx] + lines[end_idx:]
        else:
            marker = lines[list_idx].lstrip()[0]
            indent_str = " " * list_indent
            val_lines = new_value.splitlines()
            if len(val_lines) == 1:
                formatted_item = f"{indent_str}{marker} **{target_key}**: {new_value}"
            else:
                formatted_item = f"{indent_str}{marker} **{target_key}**:\n" + "\n".join(
                    f"{indent_str}  {value_line}" if value_line.strip() else value_line for value_line in val_lines
                )
            new_lines = lines[:list_idx] + [formatted_item] + lines[end_idx:]
        return "\n".join(new_lines)

    header_idx = -1
    header_level = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            parts = stripped.split(None, 1)
            if len(parts) == 2:
                level = len(parts[0])
                header_name = parts[1].lower().strip().strip("*:_#")
                if header_name == target:
                    header_idx = idx
                    header_level = level
                    break

    if header_idx != -1:
        end_idx = len(lines)
        for idx in range(header_idx + 1, len(lines)):
            line = lines[idx]
            stripped = line.strip()
            if stripped.startswith("#"):
                parts = stripped.split(None, 1)
                if len(parts) == 2:
                    level = len(parts[0])
                    if level <= header_level:
                        end_idx = idx
                        break

        if new_value is None:
            new_lines = lines[:header_idx] + lines[end_idx:]
        else:
            new_lines = lines[:header_idx + 1] + [new_value] + lines[end_idx:]
        return "\n".join(new_lines)

    if new_value is not None:
        if lines and lines[-1].strip():
            lines.append("")
        val_lines = new_value.splitlines()
        if len(val_lines) == 1:
            lines.append(f"- **{target_key}**: {new_value}")
        else:
            lines.append(f"- **{target_key}**:")
            lines.extend(f"  {value_line}" if value_line.strip() else value_line for value_line in val_lines)

    return "\n".join(lines)
