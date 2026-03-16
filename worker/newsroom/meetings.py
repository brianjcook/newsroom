from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from pymysql.connections import Connection

from .extract import ExtractionRecord


DATE_PATTERNS = [
    "%A, %B %d, %Y",
    "%B %d, %Y",
    "%A, %b %d, %Y",
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
    governing_body: Optional[str]
    meeting_type: Optional[str]
    meeting_date: Optional[str]
    meeting_time: Optional[str]
    location_name: Optional[str]
    status: str
    agenda_posted_at: Optional[str]
    minutes_posted_at: Optional[str]
    meeting_key: Optional[str]


def _first_match(pattern: str, text: str) -> Optional[str]:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _parse_date(text: str) -> Optional[str]:
    for token in re.findall(r"(?:[A-Za-z]{3,9},\s+)?[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}", text):
        for fmt in DATE_PATTERNS:
            try:
                return datetime.strptime(token, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def _parse_time(text: str) -> Optional[str]:
    normalized_text = text.replace("a.m.", "AM").replace("p.m.", "PM").replace("a.m", "AM").replace("p.m", "PM")
    match = re.search(r"(\d{1,2}(?::\d{2})?\s*[APap][Mm])", normalized_text)
    if not match:
        return None

    token = match.group(1).upper().replace("  ", " ")
    for fmt in TIME_PATTERNS:
        try:
            return datetime.strptime(token, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    return None


def _normalize_body_name(text: str) -> Optional[str]:
    patterns = [
        r"(Select Board)",
        r"(Board of Selectmen)",
        r"(Planning Board)",
        r"(Conservation Commission)",
        r"(School Committee)",
        r"(Board of Health)",
        r"(Finance Committee)",
        r"(Zoning Board of Appeals)",
        r"(Historical Commission)",
        r"(Community Preservation Committee)",
        r"(Capital Planning Committee)",
        r"(Sewer Commissioners)",
        r"(Water Pollution Control Facility Board)",
        r"(Redevelopment Authority)",
        r"(Municipal Maintenance Department)",
    ]
    for pattern in patterns:
        value = _first_match(pattern, text)
        if value:
            if value.lower() == "board of selectmen":
                return "Select Board"
            return value
    return None


def _parse_location(text: str) -> Optional[str]:
    patterns = [
        r"(Town Hall(?: Auditorium)?)",
        r"(Memorial Town Hall)",
        r"(Room \d+)",
        r"(\d+\s+[A-Za-z]+\s+(?:Road|Rd\.|Street|St\.|Avenue|Ave\.))",
        r"(Online)",
        r"(Zoom)",
    ]
    for pattern in patterns:
        value = _first_match(pattern, text)
        if value:
            return value
    return None


def normalize_meetings(connection: Connection, extractions: List[ExtractionRecord]) -> int:
    normalized_count = 0

    for extraction in extractions:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.source_item_id, COALESCE(si.title, '') AS source_title
                FROM documents d
                INNER JOIN source_items si ON si.id = d.source_item_id
                WHERE d.id = %s
                LIMIT 1
                """,
                (extraction.document_id,),
            )
            document_row = cursor.fetchone()
            if not document_row:
                continue

            source_item_id = int(document_row["source_item_id"])
            source_title = document_row["source_title"]
            combined_text = "\n".join([source_title, extraction.title, extraction.body_text[:6000]])
            governing_body = _normalize_body_name(combined_text)
            meeting_date = _parse_date(combined_text)
            meeting_time = _parse_time(combined_text)
            location_name = _parse_location(combined_text)
            meeting_type = "minutes_recap" if "minute" in combined_text.lower() else "meeting_preview"
            status = "completed" if meeting_type == "minutes_recap" else "scheduled"
            agenda_posted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if meeting_type == "meeting_preview" else None
            minutes_posted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if meeting_type == "minutes_recap" else None
            meeting_key = None
            if governing_body and meeting_date:
                meeting_key = f"{governing_body.lower().replace(' ', '-')}-{meeting_date}"

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
                "UPDATE source_items SET status = %s, updated_at = NOW() WHERE id = %s",
                ("normalized" if governing_body and meeting_date else "needs_review", source_item_id),
            )
            if governing_body and meeting_date:
                normalized_count += 1
            else:
                cursor.execute(
                    """
                    UPDATE source_items
                    SET raw_meta_json = JSON_SET(COALESCE(raw_meta_json, JSON_OBJECT()), '$.diagnostic', %s)
                    WHERE id = %s
                    """,
                    (
                        json.dumps(
                            {
                                "missing_governing_body": governing_body is None,
                                "missing_meeting_date": meeting_date is None,
                                "missing_meeting_time": meeting_time is None,
                            }
                        ),
                        source_item_id,
                    ),
                )

    return normalized_count
