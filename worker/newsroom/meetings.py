from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from pymysql.connections import Connection

from .extract import ExtractionRecord


DATE_PATTERNS = [
    "%B %d, %Y",
    "%b %d, %Y",
    "%m/%d/%Y",
]

TIME_PATTERNS = [
    "%I:%M %p",
    "%I %p",
]


@dataclass(frozen=True)
class MeetingRecord:
    source_item_id: int
    governing_body: str | None
    meeting_type: str | None
    meeting_date: str | None
    meeting_time: str | None
    location_name: str | None
    status: str
    agenda_posted_at: str | None
    minutes_posted_at: str | None
    meeting_key: str | None


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _parse_date(text: str) -> str | None:
    for token in re.findall(r"[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}", text):
        for fmt in DATE_PATTERNS:
            try:
                return datetime.strptime(token, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def _parse_time(text: str) -> str | None:
    match = re.search(r"(\d{1,2}(?::\d{2})?\s*[APap][Mm])", text)
    if not match:
        return None

    token = match.group(1).upper().replace("  ", " ")
    for fmt in TIME_PATTERNS:
        try:
            return datetime.strptime(token, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    return None


def _normalize_body_name(text: str) -> str | None:
    patterns = [
        r"(Select Board)",
        r"(Planning Board)",
        r"(Conservation Commission)",
        r"(School Committee)",
        r"(Board of Health)",
        r"(Finance Committee)",
        r"(Zoning Board of Appeals)",
    ]
    for pattern in patterns:
        value = _first_match(pattern, text)
        if value:
            return value
    return None


def normalize_meetings(connection: Connection, extractions: list[ExtractionRecord]) -> int:
    normalized_count = 0

    for extraction in extractions:
        combined_text = "\n".join([extraction.title, extraction.body_text[:4000]])
        governing_body = _normalize_body_name(combined_text)
        meeting_date = _parse_date(combined_text)
        meeting_time = _parse_time(combined_text)
        location_name = _first_match(r"(Town Hall|Memorial Town Hall|Room \d+|Online|Zoom)", combined_text)
        meeting_type = "minutes_recap" if "minute" in combined_text.lower() else "meeting_preview"
        status = "scheduled"
        agenda_posted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if meeting_type == "meeting_preview" else None
        minutes_posted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if meeting_type == "minutes_recap" else None
        meeting_key = None
        if governing_body and meeting_date:
            meeting_key = f"{governing_body.lower().replace(' ', '-')}-{meeting_date}"

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT source_item_id FROM documents WHERE id = %s LIMIT 1",
                (extraction.document_id,),
            )
            document_row = cursor.fetchone()
            if not document_row:
                continue

            source_item_id = int(document_row["source_item_id"])
            cursor.execute(
                """
                INSERT INTO meetings (
                    source_item_id,
                    governing_body,
                    meeting_type,
                    meeting_date,
                    meeting_time,
                    location_name,
                    status,
                    agenda_posted_at,
                    minutes_posted_at,
                    meeting_key
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    governing_body = VALUES(governing_body),
                    meeting_type = VALUES(meeting_type),
                    meeting_date = VALUES(meeting_date),
                    meeting_time = VALUES(meeting_time),
                    location_name = VALUES(location_name),
                    status = VALUES(status),
                    agenda_posted_at = VALUES(agenda_posted_at),
                    minutes_posted_at = VALUES(minutes_posted_at)
                """,
                (
                    source_item_id,
                    governing_body,
                    meeting_type,
                    meeting_date,
                    meeting_time,
                    location_name,
                    status,
                    agenda_posted_at,
                    minutes_posted_at,
                    meeting_key,
                ),
            )
            cursor.execute(
                "UPDATE source_items SET status = 'normalized', updated_at = NOW() WHERE id = %s",
                (source_item_id,),
            )
            normalized_count += 1

    return normalized_count
