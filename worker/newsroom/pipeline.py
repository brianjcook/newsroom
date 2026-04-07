import json
from datetime import datetime, timezone
from typing import Dict, List

from .community_calendar import sync_community_calendar
from .config import load_config
from .artifacts import sync_meeting_artifacts
from .db import connect
from .documents import fetch_documents, pending_source_items
from .extract import extract_documents
from .meetings import normalize_meetings
from .publish import publish_stories_and_events
from .sources import (
    discover_buzzards_bay_coalition_news,
    discover_discover_wareham_events,
    discover_wareham_agenda_center,
    discover_wareham_police_logs,
    upsert_source_items,
)


SOURCE_DISCOVERERS = {
    "wareham_agenda_center": discover_wareham_agenda_center,
    "wareham_police_logs": discover_wareham_police_logs,
    "buzzards_bay_coalition_news": discover_buzzards_bay_coalition_news,
    "discover_wareham_events": discover_discover_wareham_events,
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _begin_run(connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO generation_runs (started_at, run_status)
            VALUES (%s, 'running')
            """,
            (_timestamp(),),
        )
        return int(cursor.lastrowid)


def _finish_run(
    connection,
    run_id: int,
    status: str,
    items_discovered: int,
    documents_fetched: int,
    extractions_created: int,
    meetings_normalized: int,
    stories_published: int,
    stories_updated: int,
    events_created: int,
    events_updated: int,
    warnings: List[str],
    errors: List[str],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE generation_runs
            SET finished_at = %s,
                run_status = %s,
                items_discovered = %s,
                documents_fetched = %s,
                extractions_created = %s,
                meetings_normalized = %s,
                stories_published = %s,
                stories_updated = %s,
                events_created = %s,
                events_updated = %s,
                warnings_json = %s,
                errors_json = %s
            WHERE id = %s
            """,
            (
                _timestamp(),
                status,
                items_discovered,
                documents_fetched,
                extractions_created,
                meetings_normalized,
                stories_published,
                stories_updated,
                events_created,
                events_updated,
                json.dumps(warnings),
                json.dumps(errors),
                run_id,
            ),
        )


def run_daily() -> Dict[str, object]:
    config = load_config()
    warnings = []  # type: List[str]
    errors = []  # type: List[str]

    with connect(config.database) as connection:
        run_id = _begin_run(connection)
        discovered_count = 0
        documents_fetched = 0
        extractions_created = 0
        meetings_normalized = 0
        stories_published = 0
        stories_updated = 0
        events_created = 0
        events_updated = 0
        artifacts_synced = 0
        community_events_synced = 0

        try:
            if config.source_discovery_enabled:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, slug, parser_key
                        FROM sources
                        WHERE is_active = 1
                        ORDER BY id ASC
                        """
                    )
                    sources = cursor.fetchall()

                for source in sources:
                    discoverer = SOURCE_DISCOVERERS.get(str(source["parser_key"]))
                    if not discoverer:
                        warnings.append(
                            "No discoverer is registered for parser_key '{}'.".format(source["parser_key"])
                        )
                        continue
                    items = discoverer(config)
                    discovered_count += upsert_source_items(connection, int(source["id"]), items)

                community_events_synced = sync_community_calendar(config, connection)
            else:
                warnings.append("Source discovery disabled by configuration.")

            source_items = pending_source_items(connection)
            if source_items:
                documents = fetch_documents(config, connection, source_items)
                documents_fetched = len(documents)
                extractions = extract_documents(config, connection, documents)
                extractions_created = len(extractions)
                meetings_normalized = normalize_meetings(connection, extractions)
                artifacts_synced = sync_meeting_artifacts(connection)
            else:
                warnings.append("No pending source items were available for fetch/extract.")

            published = publish_stories_and_events(connection)
            stories_published = published.stories_published
            stories_updated = published.stories_updated
            events_created = published.events_created
            events_updated = published.events_updated

            _finish_run(
                connection,
                run_id,
                "completed",
                discovered_count,
                documents_fetched,
                extractions_created,
                meetings_normalized,
                stories_published,
                stories_updated,
                events_created,
                events_updated,
                warnings,
                errors,
            )
            return {
                "run_id": run_id,
                "status": "completed",
                "items_discovered": discovered_count,
                "documents_fetched": documents_fetched,
                "extractions_created": extractions_created,
                "meetings_normalized": meetings_normalized,
                "stories_published": stories_published,
                "stories_updated": stories_updated,
                "events_created": events_created,
                "events_updated": events_updated,
                "warnings": warnings,
                "errors": errors,
                "artifacts_synced": artifacts_synced,
                "community_events_synced": community_events_synced,
            }
        except Exception as exc:
            errors.append(str(exc))
            _finish_run(
                connection,
                run_id,
                "failed",
                discovered_count,
                documents_fetched,
                extractions_created,
                meetings_normalized,
                stories_published,
                stories_updated,
                events_created,
                events_updated,
                warnings,
                errors,
            )
            raise
