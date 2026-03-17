import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worker.newsroom.artifacts import sync_meeting_artifacts  # noqa: E402
from worker.newsroom.config import load_config  # noqa: E402
from worker.newsroom.db import connect  # noqa: E402
from worker.newsroom.documents import DocumentRecord  # noqa: E402
from worker.newsroom.extract import extract_documents  # noqa: E402
from worker.newsroom.meetings import normalize_meetings  # noqa: E402
from worker.newsroom.publish import publish_stories_and_events  # noqa: E402


def _load_documents(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, source_item_id, document_url, document_type, mime_type, storage_path
            FROM documents
            ORDER BY id ASC
            """
        )
        rows = cursor.fetchall()
    return [
        DocumentRecord(
            id=int(row["id"]),
            source_item_id=int(row["source_item_id"]),
            document_url=row["document_url"],
            document_type=row["document_type"],
            mime_type=row["mime_type"],
            storage_path=row["storage_path"],
        )
        for row in rows
    ]


def main() -> int:
    config = load_config()
    with connect(config.database) as connection:
        documents = _load_documents(connection)
        extractions = extract_documents(config, connection, documents)
        meetings_normalized = normalize_meetings(connection, extractions)
        artifacts_synced = sync_meeting_artifacts(connection)
        published = publish_stories_and_events(connection)
        print(
            json.dumps(
                {
                    "documents": len(documents),
                    "extractions_created": len(extractions),
                    "meetings_normalized": meetings_normalized,
                    "artifacts_synced": artifacts_synced,
                    "stories_published": published.stories_published,
                    "stories_updated": published.stories_updated,
                    "events_created": published.events_created,
                    "events_updated": published.events_updated,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
