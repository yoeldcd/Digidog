# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""ChromaDB collection manager for memory and local vector records."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Third-party Libraries Imports
import chromadb

# Application Modules Imports
from brain.infrastructure.runtime.paths import get_vectorstore_dir
from brain.infrastructure.vectorstores.chunking import chunk_content
from brain.infrastructure.vectorstores.embeddings import get_embedding
from brain.infrastructure.vectorstores.logs import index_log_file as index_log_file_records
from brain.infrastructure.vectorstores.logs import index_log_entries as index_log_entry_records
from brain.infrastructure.vectorstores.logs import search_logs as search_log_records


class VectorStoreManager:
    """Manages ChromaDB client, collections, and CRUD operations for memories and local directories."""

    def __init__(self, db_path: Path | str | None = None, collection_name: str = "memories") -> None:
        """Initialize ChromaDB client under db_path and load target collection."""
        if db_path is None:
            db_path = get_vectorstore_dir(scope="global")
        else:
            db_path = Path(db_path)

        db_path.mkdir(parents=True, exist_ok=True)

        gitignore_path = db_path / ".gitignore"
        if not gitignore_path.exists():
            try:
                gitignore_path.write_text("# Ignore all contents\n*\n!.gitignore\n", encoding="utf-8")
            except Exception:
                pass

        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=str(db_path))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def chunk_content(self, category: str, key: str, content: str) -> list[tuple[str, str, dict]]:
        """Split memory content into indexable chunks.

        Args:
            category (str): Dotted memory category.
            key (str): Entry key within the category.
            content (str): Canonical memory content.

        Returns:
            list[tuple[str, str, dict]]: Chunk IDs, searchable text, and metadata.
        """
        return chunk_content(category=category, key=key, content=content)

    def add_or_update_file(self, category: str, key: str, content: str) -> dict[str, int | str]:
        """Replace all vectors associated with one canonical memory entry.

        Args:
            category (str): Dotted memory category.
            key (str): Entry key within the category.
            content (str): Canonical memory content to index.

        Returns:
            dict[str, int | str]: Indexed path and created and deleted counts.
        """
        deleted_count = self.delete_file(category, key)
        chunks = self.chunk_content(category, key, content)
        if not chunks:
            return {
                "path": f"memory/{category.replace('.', '/')}/{key}.md",
                "entries_created": 0,
                "entries_deleted": deleted_count,
            }

        ids = []
        metadatas = []
        embeddings = []

        for chunk_id, text, meta in chunks:
            if not text.strip():
                continue
            emb = get_embedding(text)
            ids.append(chunk_id)
            metadatas.append({**meta, "vector_reference": chunk_id})
            embeddings.append(emb)

        if ids:
            self.collection.add(
                ids=ids,
                metadatas=metadatas,
                embeddings=embeddings,
            )
        fallback_path = f"memory/{category.replace('.', '/')}/{key}.md"
        indexed_path = str(metadatas[0].get("path") or fallback_path) if metadatas else fallback_path
        return {
            "path": indexed_path,
            "entries_created": len(ids),
            "entries_deleted": deleted_count,
        }

    def delete_file(self, category: str, key: str) -> int:
        """Delete every vector associated with one memory entry.

        Args:
            category (str): Dotted memory category.
            key (str): Entry key within the category.

        Returns:
            int: Number of records deleted.
        """
        deleted_count = self.count_by_metadata({"$and": [{"category": category}, {"key": key}]})
        self.collection.delete(
            where={"$and": [{"category": category}, {"key": key}]},
        )
        return deleted_count

    def reset_store(self) -> None:
        """Clear all entries in this collection."""
        name = self.collection.name
        try:
            self.client.delete_collection(name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def close(self) -> None:
        """Release Chroma resources so a vectorstore directory can be moved safely."""
        close_client = getattr(self.client, "close", None)
        if callable(close_client):
            close_client()

    def add_record(self, doc_id: str, text: str, metadata: dict, embedding: list[float] | None = None) -> None:
        """Add or update a reference-only vector record.

        ``text`` is used transiently to calculate the embedding. Canonical
        content remains in Markdown or SQLite and is recovered through the
        reference metadata when a query returns this record.

        Args:
            doc_id (str): Stable vector record identifier.
            text (str): Transient source text used to calculate an embedding.
            metadata (dict): Canonical-reference metadata for hydration.
            embedding (list[float] | None): Precomputed embedding, or ``None``
                to generate it from ``text``.
        """
        self.delete_record(doc_id)
        if embedding is None:
            embedding = get_embedding(text)
        self.collection.add(
            ids=[doc_id],
            metadatas=[{**metadata, "vector_reference": doc_id}],
            embeddings=[embedding],
        )

    def delete_record(self, doc_id: str) -> None:
        """Delete a collection record by identifier.

        Args:
            doc_id (str): Vector record identifier to remove.
        """
        try:
            self.collection.delete(ids=[doc_id])
        except Exception:
            pass

    def count_records(self) -> int:
        """Count records currently stored in the collection.

        Returns:
            int: Record count, or zero if the collection cannot be read.
        """
        try:
            records = self.collection.get()
        except Exception:
            return 0
        return len(records.get("ids") or [])

    def count_by_metadata(self, filter_dict: dict) -> int:
        """Count records matching a metadata filter.

        Args:
            filter_dict (dict): Chroma metadata filter expression.

        Returns:
            int: Matching record count, or zero when lookup fails.
        """
        try:
            records = self.collection.get(where=filter_dict)
        except Exception:
            return 0
        return len(records.get("ids") or [])

    def delete_by_metadata(self, filter_dict: dict) -> int:
        """Delete records matching a metadata filter.

        Args:
            filter_dict (dict): Chroma metadata filter expression.

        Returns:
            int: Number of records present before deletion.
        """
        deleted_count = self.count_by_metadata(filter_dict)
        try:
            self.collection.delete(where=filter_dict)
        except Exception:
            pass
        return deleted_count

    def search(self, query: str, limit: int | None = 5, where_filter: dict | None = None) -> list[dict]:
        """Perform semantic search on the collection.

        Args:
            query (str): Natural-language search query.
            limit (int): Maximum number of matches.
            where_filter (dict | None): Optional Chroma metadata constraints.

        Returns:
            list[dict]: Ranked and normalized vector matches.
        """
        query_emb = get_embedding(query)
        result_limit = self.count_by_metadata(where_filter) if limit is None and where_filter else (self.count_records() if limit is None else limit)
        kwargs = {"query_embeddings": [query_emb], "n_results": max(1, result_limit)}
        if where_filter:
            kwargs["where"] = where_filter

        results = self.collection.query(**kwargs)
        formatted = []
        if not results or not results["ids"] or not results["ids"][0]:
            return formatted

        documents = results.get("documents") or [[]]
        document_row = documents[0] if documents else []
        for index in range(len(results["ids"][0])):
            doc_id = results["ids"][0][index]
            doc_text = document_row[index] if index < len(document_row) and document_row[index] else ""
            meta = results["metadatas"][0][index]
            dist = results["distances"][0][index]
            similarity = 1.0 - dist

            formatted.append({
                "id": doc_id,
                "text": doc_text,
                "category": meta.get("category", ""),
                "key": meta.get("key", ""),
                "title": meta.get("title", ""),
                "similarity": similarity,
                "metadata": meta,
            })
        return formatted

    def index_log_file(self, file_path: Path) -> dict[str, int | str]:
        """Parse and index entries from one canonical legacy log file.

        Args:
            file_path (Path): Canonical ``.log.md`` file to index.

        Returns:
            dict[str, int | str]: Source path and synchronization counts.
        """
        return index_log_file_records(manager=self, file_path=file_path)

    def index_log_entries(self, entries: list[object]) -> dict[str, int | str]:
        """Index canonical database-backed log records.

        Args:
            entries (list[object]): Log entities to index.

        Returns:
            dict[str, int | str]: Source label and synchronization counts.
        """
        return index_log_entry_records(manager=self, entries=entries)

    def search_logs(self, query: str, domain_filter: str | None = None, limit: int | None = 5) -> list[dict]:
        """Search logs with optional domain filtering and recency decay.

        Args:
            query (str): Natural-language log query.
            domain_filter (str | None): Optional domain prefix constraint.
            limit (int): Maximum number of matches.

        Returns:
            list[dict]: Ranked and hydrated log matches.
        """
        return search_log_records(
            manager=self,
            query=query,
            domain_filter=domain_filter,
            limit=limit,
        )
