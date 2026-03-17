import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from pymysql.connections import Connection

from .modeling import canonical_event_title, derive_story_dates, is_calendar_artifact, is_public_story_artifact


@dataclass(frozen=True)
class PublishedCounts:
    stories_published: int
    events_created: int


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:180] or "story"


def _story_slug(connection: Connection, meeting: Dict[str, object], story_type: str) -> str:
    parts = [
        meeting["governing_body"] or "wareham",
        story_type,
        meeting["meeting_date"] or "undated",
    ]
    if meeting.get("meeting_time"):
        parts.append(str(meeting["meeting_time"]).replace(":", "")[:4])

    base_slug = _slugify("-".join(parts))
    slug = base_slug
    suffix = 2

    with connection.cursor() as cursor:
        while True:
            cursor.execute("SELECT id FROM stories WHERE slug = %s LIMIT 1", (slug,))
            if not cursor.fetchone():
                return slug
            slug = "{}-{}".format(base_slug, suffix)
            suffix += 1


def _format_date(date_value: Optional[str]) -> str:
    if not date_value:
        return "an upcoming date"
    return datetime.strptime(date_value, "%Y-%m-%d").strftime("%B %d, %Y")


def _format_time(time_value: Optional[str]) -> str:
    if not time_value:
        return "at a time not listed in the source"
    return datetime.strptime(time_value, "%H:%M:%S").strftime("%I:%M %p").lstrip("0")


def _db_time_string(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M:%S")
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
    return str(value)


def _clean_lines(text: str) -> List[str]:
    lines = []
    for line in text.splitlines():
        normalized = " ".join(line.split())
        if len(normalized) < 8:
            continue
        lines.append(normalized)
    return lines


def _choose_summary_lines(text: str, limit: int = 3) -> List[str]:
    lines = _clean_lines(text)
    filtered = []
    for line in lines:
        lower = line.lower()
        if "agenda center" in lower or "previous versions" in lower or "packet" in lower:
            continue
        if "agenda" in lower or "minutes" in lower or "wareham" in lower or "page " in lower:
            if len(line) < 40:
                continue
        filtered.append(line)
        if len(filtered) >= limit:
            break
    return filtered


def _build_story_copy(meeting: Dict[str, object], source_item: Dict[str, object], extraction: Dict[str, object], story_type: str) -> Tuple[str, str, str, str, str]:
    body_name = meeting["governing_body"] or "Wareham officials"
    meeting_date = _format_date(meeting["meeting_date"])
    meeting_time = _format_time(meeting["meeting_time"])
    location = meeting["location_name"] or "a location not listed in the source"
    source_url = source_item["canonical_url"]
    source_label = "posted minutes" if story_type == "minutes_recap" else "posted agenda"

    if story_type == "minutes_recap":
        headline = f"Wareham {body_name} minutes posted for {meeting_date}"
        dek = f"Posted minutes show what the {body_name} recorded for its {meeting_date} meeting."
        intro = (
            f"<p>Minutes for the Wareham {html.escape(body_name)} meeting dated {html.escape(meeting_date)} "
            f"have been posted on the town website, according to the linked source document.</p>"
        )
        kicker = (
            f"<p>The document is being treated as a public-record recap. Readers should consult the "
            f"<a href=\"{html.escape(source_url)}\">posted minutes</a> for the full record and exact wording.</p>"
        )
    else:
        headline = f"Wareham {body_name} meeting scheduled for {meeting_date}"
        dek = f"The {body_name} is scheduled to meet {meeting_date} {meeting_time} at {location}."
        intro = (
            f"<p>The Wareham {html.escape(body_name)} is scheduled to meet on {html.escape(meeting_date)} "
            f"{html.escape(meeting_time)} at {html.escape(location)}, according to the posted agenda.</p>"
        )
        kicker = (
            f"<p>The public can review the full <a href=\"{html.escape(source_url)}\">posted agenda</a> "
            f"for the complete list of items, attachments, and procedural details.</p>"
        )

    summary_lines = _choose_summary_lines(extraction["body_text"])
    if summary_lines:
        middle = "".join(
            f"<p>{html.escape(line)}</p>"
            for line in summary_lines
        )
        summary = " ".join(summary_lines[:2])
    else:
        middle = (
            f"<p>The source document was available, but this automated pass did not extract a strong meeting summary. "
            f"Readers should refer directly to the town's {html.escape(source_label)}.</p>"
        )
        summary = f"Wareham posted a {source_label} for the {body_name} meeting dated {meeting_date}."

    body_html = intro + middle + kicker
    body_text = re.sub(r"<[^>]+>", "", body_html)
    return headline, dek, summary[:1000], body_html, body_text


def publish_stories_and_events(connection: Connection) -> PublishedCounts:
    stories_published = 0
    events_created = 0

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                m.id AS meeting_id,
                m.governing_body_id,
                m.governing_body,
                m.meeting_type,
                m.meeting_date,
                m.meeting_time,
                m.location_name,
                m.status,
                m.agenda_posted_at,
                m.minutes_posted_at,
                ma.artifact_type,
                ma.posted_at AS artifact_posted_at,
                ma.source_item_id,
                si.canonical_url,
                si.title AS source_title,
                de.id AS extraction_id,
                de.body_text,
                de.title AS extraction_title
            FROM meetings m
            INNER JOIN meeting_artifacts ma ON ma.meeting_id = m.id
            INNER JOIN source_items si ON si.id = ma.source_item_id
            LEFT JOIN document_extractions de ON de.document_id = ma.document_id
            WHERE ma.is_primary = 1
            ORDER BY m.id ASC, ma.id ASC
            """
        )
        rows = cursor.fetchall()

    seen_story_keys = set()  # type: Set[Tuple[int, str]]
    for row in rows:
        meeting_id = int(row["meeting_id"])
        artifact_type = row["artifact_type"] or ""
        if not is_public_story_artifact(artifact_type):
            continue
        story_type = "minutes_recap" if artifact_type == "minutes" else "meeting_preview"
        story_key = (meeting_id, story_type)
        if story_key in seen_story_keys:
            continue
        seen_story_keys.add(story_key)

        meeting = {
            "id": meeting_id,
            "governing_body_id": row["governing_body_id"],
            "governing_body": row["governing_body"],
            "meeting_type": row["meeting_type"],
            "meeting_date": row["meeting_date"].strftime("%Y-%m-%d") if row["meeting_date"] else None,
            "meeting_time": _db_time_string(row["meeting_time"]),
            "location_name": row["location_name"],
            "agenda_posted_at": row["agenda_posted_at"].strftime("%Y-%m-%d %H:%M:%S") if row["agenda_posted_at"] else None,
            "minutes_posted_at": row["minutes_posted_at"].strftime("%Y-%m-%d %H:%M:%S") if row["minutes_posted_at"] else None,
            "status": row["status"],
        }
        source_item = {
            "source_item_id": int(row["source_item_id"]),
            "canonical_url": row["canonical_url"],
            "source_title": row["source_title"] or "",
        }
        extraction = {
            "id": int(row["extraction_id"]) if row["extraction_id"] else 0,
            "title": row["extraction_title"] or "",
            "body_text": row["body_text"] or "",
        }

        if not meeting["governing_body"] or not meeting["meeting_date"]:
            continue
        if story_type == "meeting_preview" and meeting["status"] == "cancelled":
            continue

        artifact_posted_at = row["artifact_posted_at"].strftime("%Y-%m-%d %H:%M:%S") if row["artifact_posted_at"] else None
        headline, dek, summary, body_html, body_text = _build_story_copy(meeting, source_item, extraction, story_type)
        published_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        display_date, sort_date = derive_story_dates(
            story_type,
            meeting["meeting_date"],
            meeting["meeting_time"],
            artifact_posted_at,
            published_at,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM stories WHERE meeting_id = %s AND story_type = %s LIMIT 1",
                (meeting["id"], story_type),
            )
            existing_story = cursor.fetchone()
            if existing_story:
                continue
        slug = _story_slug(connection, meeting, story_type)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stories (
                    meeting_id,
                    governing_body_id,
                    story_type,
                    slug,
                    headline,
                    dek,
                    summary,
                    body_html,
                    body_text,
                    tone_profile,
                    publish_status,
                    published_at,
                    display_date,
                    sort_date,
                    source_basis_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'straight_civic', 'published', %s, %s, %s, %s)
                """,
                (
                    meeting["id"],
                    meeting["governing_body_id"],
                    story_type,
                    slug,
                    headline,
                    dek,
                    summary,
                    body_html,
                    body_text,
                    published_at,
                    display_date,
                    sort_date,
                    json.dumps(
                        {
                            "source_item_id": source_item["source_item_id"],
                            "extraction_id": extraction["id"],
                            "source_url": source_item["canonical_url"],
                            "artifact_type": artifact_type,
                        }
                    ),
                ),
            )
            story_id = int(cursor.lastrowid)
            cursor.execute(
                """
                INSERT INTO story_citations (
                    story_id,
                    citation_number,
                    label,
                    source_url,
                    note_text
                ) VALUES (%s, 1, %s, %s, %s)
                """,
                (
                    story_id,
                    "Source document",
                    source_item["canonical_url"],
                    source_item["source_title"] or extraction["title"] or "Wareham source document",
                ),
            )
            cursor.execute(
                "UPDATE source_items SET status = 'published', updated_at = NOW() WHERE id = %s",
                (source_item["source_item_id"],),
            )
        stories_published += 1

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                m.id,
                m.governing_body_id,
                m.governing_body,
                m.meeting_date,
                m.meeting_time,
                m.location_name,
                m.status,
                ma.artifact_type,
                si.canonical_url
            FROM meetings m
            INNER JOIN meeting_artifacts ma ON ma.meeting_id = m.id
            INNER JOIN source_items si ON si.id = ma.source_item_id
            LEFT JOIN calendar_events ce ON ce.meeting_id = m.id
            WHERE ce.id IS NULL
              AND m.meeting_date IS NOT NULL
              AND ma.is_primary = 1
            ORDER BY m.meeting_date ASC, m.id ASC
            """
        )
        meeting_rows = cursor.fetchall()

    for row in meeting_rows:
        body_name = row["governing_body"]
        if not body_name:
            continue
        if row["status"] == "cancelled":
            continue
        if not is_calendar_artifact(row["artifact_type"] or ""):
            continue
        meeting_date = row["meeting_date"].strftime("%Y-%m-%d")
        meeting_time = _db_time_string(row["meeting_time"]) if row["meeting_time"] else "00:00:00"
        starts_at = f"{meeting_date} {meeting_time}"
        title = canonical_event_title(body_name)

        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM calendar_events WHERE meeting_id = %s LIMIT 1", (int(row["id"]),))
            existing_event = cursor.fetchone()
            if existing_event:
                continue
            cursor.execute(
                """
                INSERT INTO calendar_events (
                    meeting_id,
                    governing_body_id,
                    title,
                    starts_at,
                    location_name,
                    body_name,
                    source_url,
                    status,
                    description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'scheduled', %s)
                """,
                (
                    int(row["id"]),
                    row["governing_body_id"],
                    title,
                    starts_at,
                    row["location_name"],
                    body_name,
                    row["canonical_url"],
                    f"Official Wareham meeting listing for the {body_name}.",
                ),
            )
        events_created += 1

    return PublishedCounts(stories_published=stories_published, events_created=events_created)
