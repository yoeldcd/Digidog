"""Picture metadata and semantic search backend."""

from __future__ import annotations

from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO, QuerySourceRefDTO
from brain.infrastructure.pictures.models import PictureRecord
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.pictures.scanner import scan_pictures
from brain.infrastructure.vectorstores.pictures import search_picture_vectors


def query_pictures_backend(text: str, domain: str, limit: int) -> list[GlobalQueryResultDTO]:
    """Search picture filenames, domains, paths, and canonical descriptions."""
    scan_pictures()
    records = PictureRepository().search(query=text, domain="" if domain == "all" else domain, limit=limit)
    return [_to_result(record=record, mechanism="text", rank=float(index)) for index, record in enumerate(records, 1)]


def query_pictures_vector_backend(text: str, limit: int) -> list[GlobalQueryResultDTO]:
    """Search picture embeddings and hydrate every match from SQLite."""
    try:
        matches = search_picture_vectors(text=text, limit=limit)
    except Exception as exc:
        return [
            GlobalQueryResultDTO(
                source="pictures", mechanism="vector", kind="warning", rank=999.0,
                title="Picture vectorstore unavailable",
                content=QueryContentDTO(title="Picture vectorstore unavailable", excerpt=str(exc)),
                warning=str(exc),
            ),
        ]
    return [
        _to_result(
            record=match["record"],
            mechanism="vector",
            rank=1.0 - float(match.get("similarity", 0.0)),
        )
        for match in matches
    ]


def _to_result(record: PictureRecord, mechanism: str, rank: float) -> GlobalQueryResultDTO:
    """Map one canonical picture record to the unified result contract."""
    excerpt = record.description or f"Image file {record.filename} in {record.domain}."
    return GlobalQueryResultDTO(
        source="pictures",
        mechanism=mechanism,
        kind="picture",
        rank=rank,
        title=record.filename,
        text=excerpt,
        data=record.as_mapping(),
        content=QueryContentDTO(
            title=record.filename,
            excerpt=excerpt,
            body=record.description,
            location=record.relative_path,
        ),
        source_ref=QuerySourceRefDTO(
            scope="global",
            source_type="pictures",
            domain=record.domain,
            read_command=f"list-pictures --id {record.id} --json",
            path=f"pictures/{record.relative_path}",
            title=record.filename,
            structure=["pictures", *record.relative_path.split("/")],
        ),
    )
