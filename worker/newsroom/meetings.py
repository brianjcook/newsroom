import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from pymysql.connections import Connection

from .extract import ExtractionRecord
from .modeling import (
    classify_artifact,
    classify_body_type,
    derive_meeting_status,
    normalize_body_name,
    parse_source_meta,
    should_enrich_meeting_from_artifact,
    should_normalize_artifact,
    slugify,
)


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
    normalized_text = (
        text.replace("a.m.", "AM")
        .replace("p.m.", "PM")
        .replace("A.M.", "AM")
        .replace("P.M.", "PM")
        .replace("a.m", "AM")
        .replace("p.m", "PM")
        .replace("A.M", "AM")
        .replace("P.M", "PM")
    )
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


def _derive_meeting_title(governing_body, meeting_type, meeting_date):
    if not governing_body:
        return None
    label = "Minutes" if meeting_type == "minutes_recap" else "Meeting"
    if meeting_date:
        return "{} {} {}".format(governing_body, label, meeting_date)
    return "{} {}".format(governing_body, label)


def _coalesce(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _meeting_type_for_artifact(artifact_type: str) -> str:
    if artifact_type == "minutes":
        return "minutes_recap"
    return "meeting_preview"


def _meeting_key(governing_body: Optional[str], meeting_date: Optional[str]) -> Optional[str]:
    if governing_body and meeting_date:
        return "{}-{}".format(slugify(governing_body), meeting_date)
    return None


def _candidate_from_source(
    source_title: str,
    item_type: str,
    canonical_url: str,
    raw_meta_json: Optional[str],
    published_at,
    extraction: ExtractionRecord,
) -> Dict[str, object]:
    meta = parse_source_meta(raw_meta_json)
    structured = extraction.structured_json or {}
    source_meta = structured.get("source_meta") if isinstance(structured, dict) else {}
    if isinstance(source_meta, dict):
        merged_meta = dict(meta)
        merged_meta.update(source_meta)
        meta = merged_meta
    combined_text = "\n".join(
        [
            source_title or "",
            str(meta.get("entry_title") or ""),
            str(meta.get("wrapper_time_text") or ""),
            str(structured.get("meeting_location_line") or ""),
            extraction.title,
            extraction.body_text[:6000],
        ]
    )
    artifact_type, _, is_primary, _ = classify_artifact(source_title, item_type, canonical_url, meta)
    governing_body = _coalesce(
        normalize_body_name(str(meta.get("governing_body") or "")),
        normalize_body_name(str(meta.get("entry_title") or "")),
        normalize_body_name(combined_text),
        str(meta.get("governing_body") or None),
    )
    meeting_date = _coalesce(
        meta.get("meeting_date"),
        _parse_date(combined_text),
    )
    meeting_time = _coalesce(_parse_time(str(meta.get("wrapper_time_text") or "")), _parse_time(combined_text))
    location_name = _coalesce(
        structured.get("meeting_location_line"),
        _parse_location(combined_text),
    )
    meeting_type = _meeting_type_for_artifact(artifact_type)
    status = derive_meeting_status(" ".join([source_title or "", str(meta.get("entry_title") or ""), combined_text[:500]]))

    if status == "cancelled" and artifact_type != "minutes":
        meeting_type = "meeting_preview"

    posted_at = None
    if published_at:
        try:
            posted_at = published_at.strftime("%Y-%m-%d %H:%M:%S")
        except AttributeError:
            posted_at = str(published_at)
    posted_at = _coalesce(meta.get("posted_at"), posted_at)

    return {
        "meta": meta,
        "artifact_type": artifact_type,
        "is_primary": is_primary,
        "governing_body": governing_body,
        "meeting_date": meeting_date,
        "meeting_time": meeting_time,
        "location_name": location_name,
        "meeting_type": meeting_type,
        "status": status,
        "posted_at": posted_at,
        "meeting_key": _coalesce(meta.get("meeting_key"), _meeting_key(governing_body, meeting_date)),
        "meeting_title": _derive_meeting_title(governing_body, meeting_type, meeting_date),
    }


def _governing_body_id(connection, name):
    if not name:
        return None

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM municipalities WHERE slug = %s LIMIT 1",
            ("wareham-ma",),
        )
        municipality = cursor.fetchone()
        if not municipality:
            return None

        normalized_name = normalize_body_name(name) or name
        slug = "wareham-{}".format(slugify(normalized_name))
        cursor.execute(
            """
            INSERT INTO governing_bodies (
                municipality_id,
                name,
                normalized_name,
                body_type,
                slug,
                agenda_center_name,
                is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                normalized_name = VALUES(normalized_name),
                body_type = VALUES(body_type),
                agenda_center_name = VALUES(agenda_center_name)
            """,
            (
                int(municipality["id"]),
                normalized_name,
                normalized_name,
                classify_body_type(normalized_name),
                slug,
                normalized_name,
            ),
        )
        cursor.execute(
            "SELECT id FROM governing_bodies WHERE slug = %s LIMIT 1",
            (slug,),
        )
        row = cursor.fetchone()
        return int(row["id"]) if row else None


def normalize_meetings(connection: Connection, extractions: List[ExtractionRecord]) -> int:
    normalized_count = 0

    for extraction in extractions:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    d.source_item_id,
                    COALESCE(si.title, '') AS source_title,
                    COALESCE(si.item_type, '') AS item_type,
                    si.canonical_url,
                    si.raw_meta_json,
                    si.published_at
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
            candidate = _candidate_from_source(
                source_title,
                document_row["item_type"],
                document_row["canonical_url"],
                document_row["raw_meta_json"],
                document_row["published_at"],
                extraction,
            )
            governing_body = candidate["governing_body"]
            meeting_date = candidate["meeting_date"]
            meeting_time = candidate["meeting_time"]
            location_name = candidate["location_name"]
            meeting_type = candidate["meeting_type"]
            status = candidate["status"]
            agenda_posted_at = candidate["posted_at"] if candidate["artifact_type"] == "agenda" else None
            minutes_posted_at = candidate["posted_at"] if candidate["artifact_type"] == "minutes" else None
            governing_body_id = _governing_body_id(connection, governing_body)
            meeting_title = candidate["meeting_title"]
            meeting_key = candidate["meeting_key"]

            if not meeting_key and not candidate["is_primary"]:
                cursor.execute(
                    "UPDATE source_items SET status = %s, updated_at = NOW() WHERE id = %s",
                    ("ignored", source_item_id),
                )
                continue

            if not should_normalize_artifact(candidate["artifact_type"], candidate["is_primary"]) and not should_enrich_meeting_from_artifact(candidate["artifact_type"]):
                cursor.execute(
                    "UPDATE source_items SET status = %s, updated_at = NOW() WHERE id = %s",
                    ("ignored", source_item_id),
                )
                continue

            promote_fields = 1 if should_normalize_artifact(candidate["artifact_type"], candidate["is_primary"]) else 0

            cursor.execute(
                """
                INSERT INTO meetings (
                    source_item_id,
                    governing_body_id,
                    governing_body,
                    title,
                    normalized_title,
                    meeting_type,
                    meeting_date,
                    meeting_time,
                    location_name,
                    status,
                    agenda_posted_at,
                    minutes_posted_at,
                    meeting_key
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    source_item_id = IF(%s = 1, VALUES(source_item_id), source_item_id),
                    governing_body_id = VALUES(governing_body_id),
                    governing_body = VALUES(governing_body),
                    title = VALUES(title),
                    normalized_title = VALUES(normalized_title),
                    meeting_type = IF(%s = 1, VALUES(meeting_type), meeting_type),
                    meeting_date = VALUES(meeting_date),
                    meeting_time = IF(%s = 1, COALESCE(VALUES(meeting_time), meeting_time), COALESCE(meeting_time, VALUES(meeting_time))),
                    location_name = IF(%s = 1, COALESCE(VALUES(location_name), location_name), COALESCE(location_name, VALUES(location_name))),
                    status = IF(%s = 1, VALUES(status), status),
                    agenda_posted_at = IF(%s = 1, COALESCE(VALUES(agenda_posted_at), agenda_posted_at), COALESCE(agenda_posted_at, VALUES(agenda_posted_at))),
                    minutes_posted_at = IF(%s = 1, COALESCE(VALUES(minutes_posted_at), minutes_posted_at), COALESCE(minutes_posted_at, VALUES(minutes_posted_at)))
                """,
                (
                    source_item_id,
                    governing_body_id,
                    governing_body,
                    meeting_title,
                    slugify(meeting_title or meeting_key or source_title) if (meeting_title or meeting_key or source_title) else None,
                    meeting_type,
                    meeting_date,
                    meeting_time,
                    location_name,
                    status,
                    agenda_posted_at,
                    minutes_posted_at,
                    meeting_key,
                    1 if candidate["is_primary"] else 0,
                    promote_fields,
                    promote_fields,
                    promote_fields,
                    promote_fields,
                    promote_fields,
                    promote_fields,
                ),
            )
            status_value = "normalized" if should_normalize_artifact(candidate["artifact_type"], candidate["is_primary"]) and meeting_key else "ignored"
            cursor.execute(
                "UPDATE source_items SET status = %s, updated_at = NOW() WHERE id = %s",
                (status_value if meeting_key else "needs_review", source_item_id),
            )
            if meeting_key and should_normalize_artifact(candidate["artifact_type"], candidate["is_primary"]):
                normalized_count += 1
            elif not meeting_key:
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
                                "artifact_type": candidate["artifact_type"],
                            }
                        ),
                        source_item_id,
                    ),
                )

    return normalized_count
