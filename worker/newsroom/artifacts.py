from typing import Dict

from pymysql.connections import Connection

from .extract import ExtractionRecord
from .meetings import _candidate_from_source
from .modeling import classify_artifact


def sync_meeting_artifacts(connection):
    synced = 0

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                si.id AS source_item_id,
                si.title AS source_title,
                si.canonical_url,
                si.item_type,
                si.raw_meta_json,
                si.published_at,
                si.first_seen_at,
                d.id AS document_id,
                d.document_type,
                d.mime_type,
                d.storage_path,
                d.sha256,
                de.title AS extraction_title,
                de.body_text
            FROM source_items si
            LEFT JOIN documents d ON d.source_item_id = si.id
            LEFT JOIN document_extractions de ON de.document_id = d.id
            """
        )
        rows = cursor.fetchall()

    for row in rows:
        extraction = ExtractionRecord(
            document_id=int(row["document_id"]) if row["document_id"] else 0,
            title=row["extraction_title"] or "",
            body_text=row["body_text"] or "",
            structured_json={},
            confidence_score=0.0,
            warnings=[],
        )
        candidate = _candidate_from_source(
            row["source_title"] or "",
            row["item_type"] or row["document_type"] or "",
            row["canonical_url"],
            row["raw_meta_json"],
            row["published_at"],
            extraction,
        )
        meeting_key = candidate["meeting_key"]
        if not meeting_key:
            continue

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM meetings WHERE meeting_key = %s LIMIT 1",
                (meeting_key,),
            )
            meeting_row = cursor.fetchone()

        if not meeting_row:
            continue

        artifact_type, fmt, is_primary, is_amended = classify_artifact(
            row["source_title"],
            row["item_type"] or row["document_type"],
            row["canonical_url"],
            candidate["meta"],
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO meeting_artifacts (
                    meeting_id,
                    source_item_id,
                    document_id,
                    artifact_type,
                    format,
                    title,
                    source_url,
                    posted_at,
                    version_label,
                    is_primary,
                    is_amended,
                    storage_path,
                    mime_type,
                    sha256,
                    extraction_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    artifact_type = VALUES(artifact_type),
                    format = VALUES(format),
                    title = VALUES(title),
                    posted_at = VALUES(posted_at),
                    version_label = VALUES(version_label),
                    is_primary = VALUES(is_primary),
                    is_amended = VALUES(is_amended),
                    storage_path = VALUES(storage_path),
                    mime_type = VALUES(mime_type),
                    sha256 = VALUES(sha256),
                    extraction_status = VALUES(extraction_status)
                """,
                (
                    int(meeting_row["id"]),
                    int(row["source_item_id"]),
                    int(row["document_id"]) if row["document_id"] else None,
                    artifact_type,
                    fmt,
                    candidate["meta"].get("artifact_label") or row["source_title"],
                    row["canonical_url"],
                    row["published_at"] or row["first_seen_at"],
                    "amended" if is_amended else None,
                    1 if is_primary else 0,
                    1 if is_amended else 0,
                    row["storage_path"],
                    row["mime_type"],
                    row["sha256"],
                    "extracted" if row["document_id"] else "missing_document",
                ),
            )
        synced += 1

    return synced
