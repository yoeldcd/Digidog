"""Memory store operations that coordinate files, indexes, and vector sync."""

from __future__ import annotations

# Standard Libraries Imports
import shutil
from pathlib import Path

# Application Modules Imports
from brain.application.memory import paths
from brain.application.memory.markdown_sections import extract_from_markdown, update_markdown


def create_category(category: str) -> Path:
    """Create a category directory structure under MEMORY_ROOT."""
    paths.ensure_memory_root()
    dir_path = paths.resolve_category_dir(category)
    dir_path.mkdir(parents=True, exist_ok=True)
    from brain.application.memory.indexing.index_service import update_index_category

    update_index_category(category, deleted=False)
    return dir_path


def write_instance(category: str, key: str, content: str) -> Path:
    """Write pure Markdown content to the target category/key file."""
    paths.ensure_memory_root()
    from brain.application.memory.indexing.index_service import update_index_record

    parts = [part.strip() for part in category.split(".") if part.strip()]
    if len(parts) == 2:
        parent_dir = paths.MEMORY_ROOT / parts[0]
        file_path = parent_dir / f"{parts[1]}.md"
        if parent_dir.is_dir() and file_path.is_file():
            orig_content = file_path.read_text(encoding="utf-8")
            updated_content = update_markdown(orig_content, key, content)
            paths.write_text_atomic(file_path, updated_content)
            update_index_record(category, key)
            sync_vectorstore_file(parts[0], parts[1], updated_content)
            return file_path

    file_path = paths.resolve_file_path(category, key)
    paths.write_text_atomic(file_path, content)
    update_index_record(category, key)
    sync_vectorstore_file(category, key, content)
    return file_path


def read_instance(category: str, key: str) -> str:
    """Read and return Markdown content from the category/key file."""
    parts = [part.strip() for part in category.split(".") if part.strip()]
    if len(parts) == 2:
        parent_dir = paths.MEMORY_ROOT / parts[0]
        file_path = parent_dir / f"{parts[1]}.md"
        if parent_dir.is_dir() and file_path.is_file():
            content = file_path.read_text(encoding="utf-8")
            extracted = extract_from_markdown(content, key)
            if extracted is not None:
                return extracted
            return content

    file_path = paths.resolve_file_path(category, key)
    if not file_path.exists():
        raise paths.BrainStoreError(f"Record '{key}' does not exist in category '{category}'.")
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise paths.BrainStoreError(f"Could not read file {file_path}: {exc}") from exc


def delete_instance(category: str, key: str) -> None:
    """Delete the .md file for a category/key."""
    from brain.application.memory.indexing.index_service import update_index_record

    parts = [part.strip() for part in category.split(".") if part.strip()]
    if len(parts) == 2:
        parent_dir = paths.MEMORY_ROOT / parts[0]
        file_path = parent_dir / f"{parts[1]}.md"
        if parent_dir.is_dir() and file_path.is_file():
            orig_content = file_path.read_text(encoding="utf-8")
            updated_content = update_markdown(orig_content, key, None)
            paths.write_text_atomic(file_path, updated_content)
            update_index_record(category, key)
            sync_vectorstore_file(parts[0], parts[1], updated_content)
            return

    file_path = paths.resolve_file_path(category, key)
    if not file_path.exists():
        raise paths.BrainStoreError(f"Record '{key}' does not exist in category '{category}'.")
    try:
        file_path.unlink()
        update_index_record(category, key, deleted=True)
        delete_vectorstore_file(category, key)
    except Exception as exc:
        raise paths.BrainStoreError(f"Could not delete file {file_path}: {exc}") from exc


def delete_category(category: str, confirmation: str) -> None:
    """Recursively delete a category directory and all its contents."""
    from brain.application.memory.indexing.index_service import update_index_category

    dir_path = paths.resolve_category_dir(category)
    normalized_category = ".".join(part.strip() for part in category.split(".") if part.strip())
    if confirmation != normalized_category:
        raise paths.BrainStoreError(f"Deleting category '{normalized_category}' requires exact confirmation.")
    if not dir_path.exists():
        raise paths.BrainStoreError(f"Category directory '{dir_path}' does not exist.")
    try:
        shutil.rmtree(dir_path)
        update_index_category(category, deleted=True)
    except Exception as exc:
        raise paths.BrainStoreError(f"Could not delete category directory {dir_path}: {exc}") from exc


def sync_vectorstore_file(category: str, key: str, content: str) -> None:
    """Best-effort vectorstore update for one memory file."""
    try:
        from brain.infrastructure.vectorstores.manager import VectorStoreManager

        vectorstore = VectorStoreManager()
        vectorstore.add_or_update_file(category, key, content)
    except Exception:
        pass


def delete_vectorstore_file(category: str, key: str) -> None:
    """Best-effort vectorstore deletion for one memory file."""
    try:
        from brain.infrastructure.vectorstores.manager import VectorStoreManager

        vectorstore = VectorStoreManager()
        vectorstore.delete_file(category, key)
    except Exception:
        pass
