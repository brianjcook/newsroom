import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worker.newsroom.config import load_config  # noqa: E402
from worker.newsroom.db import connect  # noqa: E402
from worker.newsroom.documents import SourceItemRecord, fetch_documents  # noqa: E402


def _load_source_items(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, canonical_url, COALESCE(title, '') AS title, item_type, raw_meta_json
            FROM source_items
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
            raw_meta_json=row["raw_meta_json"],
        )
        for row in rows
    ]


def main() -> int:
    config = load_config()
    with connect(config.database) as connection:
        items = _load_source_items(connection)
        documents = fetch_documents(config, connection, items)
        print(
            json.dumps(
                {
                    "source_items": len(items),
                    "documents_fetched": len(documents),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
