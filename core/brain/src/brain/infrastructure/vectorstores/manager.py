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
        """Split content into indexable chunks."""
        return chunk_content(category=category, key=key, content=content)

    def add_or_update_file(self, category: str, key: str, content: str) -> dict[str, int | str]:
        """Add or update a memory file in the vector store (global format)."""
        deleted_count = self.delete_file(category, key)
        chunks = self.chunk_content(category, key, content)
        if not chunks:
            return {
                "path": f"memory/{category.replace('.', '/')}/{key}.md",
                "entries_created": 0,
                "entries_deleted": deleted_count,
            }

        ids = []
        documents = []
        metadatas = []
        embeddings = []

        for chunk_id, text, meta in chunks:
            if not text.strip():
                continue
            emb = get_embedding(text)
            ids.append(chunk_id)
            documents.append(text)
            metadatas.append(meta)
            embeddings.append(emb)

        if ids:
            self.collection.add(
                ids=ids,
                documents=documents,
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
        """Delete all vectors matching a specific memory file (global format)."""
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

    def add_record(self, doc_id: str, text: str, metadata: dict, embedding: list[float] | None = None) -> None:
        """Add or update a single record in the collection (reusable format)."""
        self.delete_record(doc_id)
        if embedding is None:
            embedding = get_embedding(text)
        self.collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
            embeddings=[embedding],
        )

    def delete_record(self, doc_id: str) -> None:
        """Delete a record from the collection by ID."""
        try:
            self.collection.delete(ids=[doc_id])
        except Exception:
            pass

    def count_records(self) -> int:
        """Return the number of records currently stored in the collection."""
        try:
            records = self.collection.get()
        except Exception:
            return 0
        return len(records.get("ids") or [])

    def count_by_metadata(self, filter_dict: dict) -> int:
        """Return the number of records matching a metadata filter."""
        try:
            records = self.collection.get(where=filter_dict)
        except Exception:
            return 0
        return len(records.get("ids") or [])

    def delete_by_metadata(self, filter_dict: dict) -> int:
        """Delete records from the collection matching a metadata filter."""
        deleted_count = self.count_by_metadata(filter_dict)
        try:
            self.collection.delete(where=filter_dict)
        except Exception:
            pass
        return deleted_count

    def search(self, query: str, limit: int = 5, where_filter: dict | None = None) -> list[dict]:
        """Perform semantic search on the collection."""
        query_emb = get_embedding(query)
        kwargs = {
            "query_embeddings": [query_emb],
            "n_results": limit,
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = self.collection.query(**kwargs)
        formatted = []
        if not results or not results["ids"] or not results["ids"][0]:
            return formatted

        for index in range(len(results["ids"][0])):
            doc_id = results["ids"][0][index]
            doc_text = results["documents"][0][index]
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
        """Parse and index all entries inside a standard `.log.md` file."""
        return index_log_file_records(manager=self, file_path=file_path)

    def index_log_entries(self, entries: list[object]) -> dict[str, int | str]:
        """Index DB-backed log records into the local logs collection."""
        return index_log_entry_records(manager=self, entries=entries)

    def search_logs(self, query: str, domain_filter: str | None = None, limit: int = 5) -> list[dict]:
        """Perform semantic search on logs with optional domain filtering and recency decay."""
        return search_log_records(
            manager=self,
            query=query,
            domain_filter=domain_filter,
            limit=limit,
        )
