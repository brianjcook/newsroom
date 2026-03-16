from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import load_config
from .db import connect
from .sources import discover_wareham_agenda_center, upsert_source_items


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


def _finish_run(connection, run_id: int, status: str, items_discovered: int, warnings: list[str], errors: list[str]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE generation_runs
            SET finished_at = %s,
                run_status = %s,
                items_discovered = %s,
                warnings_json = %s,
                errors_json = %s
            WHERE id = %s
            """,
            (
                _timestamp(),
                status,
                items_discovered,
                json.dumps(warnings),
                json.dumps(errors),
                run_id,
            ),
        )


def run_daily() -> dict[str, object]:
    config = load_config()
    warnings: list[str] = []
    errors: list[str] = []

    with connect(config.database) as connection:
        run_id = _begin_run(connection)
        discovered_count = 0

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM sources WHERE slug = %s AND is_active = 1 LIMIT 1",
                    ("wareham-agenda-center",),
                )
                source = cursor.fetchone()

            if not source:
                raise RuntimeError("Source 'wareham-agenda-center' is not seeded.")

            if config.source_discovery_enabled:
                items = discover_wareham_agenda_center(config)
                discovered_count = upsert_source_items(connection, int(source["id"]), items)
            else:
                warnings.append("Source discovery disabled by configuration.")

            _finish_run(connection, run_id, "completed", discovered_count, warnings, errors)
            return {
                "run_id": run_id,
                "status": "completed",
                "items_discovered": discovered_count,
                "warnings": warnings,
                "errors": errors,
            }
        except Exception as exc:
            errors.append(str(exc))
            _finish_run(connection, run_id, "failed", discovered_count, warnings, errors)
            raise
