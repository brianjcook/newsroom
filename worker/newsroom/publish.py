from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime

from pymysql.connections import Connection


@dataclass(frozen=True)
class PublishedCounts:
    stories_published: int
    events_created: int


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:180] or "story"


def _format_date(date_value: str | None) -> str:
    if not date_value:
        return "an upcoming date"
    return datetime.strptime(date_value, "%Y-%m-%d").strftime("%B %d, %Y")


def _format_time(time_value: str | None) -> str:
    if not time_value:
        return "at a time not listed in the source"
    return datetime.strptime(time_value, "%H:%M:%S").strftime("%I:%M %p").lstrip("0")


def _clean_lines(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        normalized = " ".join(line.split())
        if len(normalized) < 8:
            continue
        lines.append(normalized)
    return lines


def _choose_summary_lines(text: str, limit: int = 3) -> list[str]:
    lines = _clean_lines(text)
    filtered = []
    for line in lines:
        lower = line.lower()
        if "agenda" in lower or "minutes" in lower or "wareham" in lower or "page " in lower:
            if len(line) < 40:
                continue
        filtered.append(line)
        if len(filtered) >= limit:
            break
    return filtered


def _build_story_copy(meeting: dict, source_item: dict, extraction: dict) -> tuple[str, str, str, str, str]:
    body_name = meeting["governing_body"] or "Wareham officials"
    meeting_date = _format_date(meeting["meeting_date"])
    meeting_time = _format_time(meeting["meeting_time"])
    location = meeting["location_name"] or "a location not listed in the source"
    story_type = meeting["meeting_type"] or "meeting_preview"
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
                m.source_item_id,
                m.governing_body,
                m.meeting_type,
                m.meeting_date,
                m.meeting_time,
                m.location_name,
                si.canonical_url,
                si.title AS source_title,
                de.id AS extraction_id,
                de.body_text,
                de.title AS extraction_title
            FROM meetings m
            INNER JOIN source_items si ON si.id = m.source_item_id
            INNER JOIN documents d ON d.source_item_id = m.source_item_id
            INNER JOIN document_extractions de ON de.document_id = d.id
            LEFT JOIN stories s ON s.meeting_id = m.id
            WHERE s.id IS NULL
            ORDER BY m.id ASC, de.id DESC
            """
        )
        rows = cursor.fetchall()

    seen_meetings: set[int] = set()
    for row in rows:
        meeting_id = int(row["meeting_id"])
        if meeting_id in seen_meetings:
            continue
        seen_meetings.add(meeting_id)

        meeting = {
            "id": meeting_id,
            "governing_body": row["governing_body"],
            "meeting_type": row["meeting_type"],
            "meeting_date": row["meeting_date"].strftime("%Y-%m-%d") if row["meeting_date"] else None,
            "meeting_time": row["meeting_time"].strftime("%H:%M:%S") if row["meeting_time"] else None,
            "location_name": row["location_name"],
        }
        source_item = {
            "source_item_id": int(row["source_item_id"]),
            "canonical_url": row["canonical_url"],
            "source_title": row["source_title"] or "",
        }
        extraction = {
            "id": int(row["extraction_id"]),
            "title": row["extraction_title"] or "",
            "body_text": row["body_text"] or "",
        }

        headline, dek, summary, body_html, body_text = _build_story_copy(meeting, source_item, extraction)
        slug = _slugify(
            f"{meeting['governing_body'] or 'wareham'}-{meeting['meeting_type'] or 'story'}-{meeting['meeting_date'] or 'undated'}"
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM stories WHERE slug = %s LIMIT 1", (slug,))
            existing_story = cursor.fetchone()
            if existing_story:
                continue
            cursor.execute(
                """
                INSERT INTO stories (
                    meeting_id,
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
                    source_basis_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'straight_civic', 'published', NOW(), %s)
                """,
                (
                    meeting["id"],
                    meeting["meeting_type"] or "meeting_preview",
                    slug,
                    headline,
                    dek,
                    summary,
                    body_html,
                    body_text,
                    json.dumps(
                        {
                            "source_item_id": source_item["source_item_id"],
                            "extraction_id": extraction["id"],
                            "source_url": source_item["canonical_url"],
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
                m.governing_body,
                m.meeting_date,
                m.meeting_time,
                m.location_name,
                si.canonical_url
            FROM meetings m
            INNER JOIN source_items si ON si.id = m.source_item_id
            LEFT JOIN calendar_events ce ON ce.meeting_id = m.id
            WHERE ce.id IS NULL AND m.meeting_date IS NOT NULL
            ORDER BY m.meeting_date ASC, m.id ASC
            """
        )
        meeting_rows = cursor.fetchall()

    for row in meeting_rows:
        body_name = row["governing_body"] or "Official Meeting"
        meeting_date = row["meeting_date"].strftime("%Y-%m-%d")
        meeting_time = row["meeting_time"].strftime("%H:%M:%S") if row["meeting_time"] else "00:00:00"
        starts_at = f"{meeting_date} {meeting_time}"
        title = f"{body_name} Meeting"

        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM calendar_events WHERE meeting_id = %s LIMIT 1", (int(row["id"]),))
            existing_event = cursor.fetchone()
            if existing_event:
                continue
            cursor.execute(
                """
                INSERT INTO calendar_events (
                    meeting_id,
                    title,
                    starts_at,
                    location_name,
                    body_name,
                    source_url,
                    status,
                    description
                ) VALUES (%s, %s, %s, %s, %s, %s, 'scheduled', %s)
                """,
                (
                    int(row["id"]),
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
