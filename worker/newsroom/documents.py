from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import requests
from pymysql.connections import Connection

from .config import WorkerConfig


@dataclass(frozen=True)
class SourceItemRecord:
    id: int
    canonical_url: str
    title: str
    item_type: str


@dataclass(frozen=True)
class DocumentRecord:
    id: int
    source_item_id: int
    document_url: str
    document_type: str
    mime_type: Optional[str]
    storage_path: str


def pending_source_items(connection: Connection) -> List[SourceItemRecord]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, canonical_url, COALESCE(title, '') AS title, item_type
            FROM source_items
            WHERE status IN ('discovered', 'updated')
            ORDER BY id ASC
            """
        )
        rows = cursor.fetchall()

    return [
        SourceItemRecord(
            id=int(row["id"]),
            canonical_url=row["canonical_url"],
            title=row["title"],
            item_type=row["item_type"],
        )
        for row in rows
    ]


def _extension_from_url(url: str, mime_type: Optional[str]) -> str:
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return ".pdf"
    if path.endswith(".html") or path.endswith(".htm"):
        return ".html"
    if mime_type:
        if "pdf" in mime_type:
            return ".pdf"
        if "html" in mime_type:
            return ".html"
    return ".bin"


def fetch_documents(config: WorkerConfig, connection: Connection, items: List[SourceItemRecord]) -> List[DocumentRecord]:
    Path(config.documents_dir).mkdir(parents=True, exist_ok=True)
    documents = []  # type: List[DocumentRecord]

    for item in items:
        response = requests.get(
            item.canonical_url,
            headers={"User-Agent": config.fetch_user_agent},
            timeout=45,
        )
        response.raise_for_status()

        mime_type = response.headers.get("Content-Type", "").split(";")[0].strip() or None
        file_extension = _extension_from_url(item.canonical_url, mime_type)
        sha256 = hashlib.sha256(response.content).hexdigest()
        relative_path = f"documents/source_item_{item.id}_{sha256[:16]}{file_extension}"
        target_path = Path(config.storage_root) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(response.content)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO documents (
                    source_item_id,
                    document_url,
                    document_type,
                    mime_type,
                    storage_path,
                    sha256,
                    fetched_at,
                    http_status
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                ON DUPLICATE KEY UPDATE
                    document_type = VALUES(document_type),
                    mime_type = VALUES(mime_type),
                    storage_path = VALUES(storage_path),
                    sha256 = VALUES(sha256),
                    fetched_at = VALUES(fetched_at),
                    http_status = VALUES(http_status)
                """,
                (
                    item.id,
                    item.canonical_url,
                    item.item_type,
                    mime_type,
                    relative_path.replace("\\", "/"),
                    sha256,
                    response.status_code,
                ),
            )
            cursor.execute(
                """
                SELECT id, source_item_id, document_url, document_type, mime_type, storage_path
                FROM documents
                WHERE source_item_id = %s AND document_url = %s
                LIMIT 1
                """,
                (item.id, item.canonical_url),
            )
            row = cursor.fetchone()
            cursor.execute(
                "UPDATE source_items SET status = 'fetched', updated_at = NOW() WHERE id = %s",
                (item.id,),
            )

        if row:
            documents.append(
                DocumentRecord(
                    id=int(row["id"]),
                    source_item_id=int(row["source_item_id"]),
                    document_url=row["document_url"],
                    document_type=row["document_type"],
                    mime_type=row["mime_type"],
                    storage_path=row["storage_path"],
                )
            )

    return documents
