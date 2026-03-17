import html
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from pymysql.connections import Connection

from .modeling import artifact_priority, canonical_event_title, derive_story_dates, is_calendar_artifact, is_public_story_artifact


AGENDA_EXPLAINERS = {
    "comprehensive wastewater management plan": {
        "text": "Wareham's Sewer Department lists the 2025 Comprehensive Wastewater Management Plan as a town planning document tied to long-range wastewater system needs and project planning.",
        "source_url": "https://www.wareham.gov/332/Sewer-Department",
        "label": "Wareham Sewer Department",
    },
}


@dataclass(frozen=True)
class PublishedCounts:
    stories_published: int
    events_created: int


GENERIC_EXTRACTION_TITLES = {
    "agenda",
    "minutes",
    "pdf",
    "packet",
    "html",
    "reference",
}


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


def _parse_story_basis(raw_value) -> Dict[str, object]:
    if not raw_value:
        return {}
    if isinstance(raw_value, dict):
        return raw_value
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _story_content_signature(headline: str, dek: str, summary: str, body_text: str) -> str:
    digest = hashlib.sha256()
    digest.update(headline.encode("utf-8"))
    digest.update(b"\n")
    digest.update((dek or "").encode("utf-8"))
    digest.update(b"\n")
    digest.update((summary or "").encode("utf-8"))
    digest.update(b"\n")
    digest.update((body_text or "").encode("utf-8"))
    return digest.hexdigest()


def _story_basis_json(
    source_item: Dict[str, object],
    extraction: Dict[str, object],
    artifact_type: str,
    artifact_posted_at: Optional[str],
    is_amended: bool,
    content_signature: str,
) -> str:
    return json.dumps(
        {
            "source_item_id": source_item["source_item_id"],
            "extraction_id": extraction["id"],
            "source_url": source_item["canonical_url"],
            "artifact_type": artifact_type,
            "artifact_posted_at": artifact_posted_at,
            "is_amended": bool(is_amended),
            "content_signature": content_signature,
        }
    )


def _story_update_note(
    meeting: Dict[str, object],
    previous_basis: Dict[str, object],
    source_item: Dict[str, object],
    extraction: Dict[str, object],
    artifact_posted_at: Optional[str],
    is_amended: bool,
) -> str:
    if not previous_basis:
        return ""
    if not (
        is_amended
        or previous_basis.get("source_item_id") != source_item["source_item_id"]
        or previous_basis.get("extraction_id") != extraction["id"]
        or previous_basis.get("source_url") != source_item["canonical_url"]
        or previous_basis.get("artifact_posted_at") != artifact_posted_at
    ):
        return ""

    note_label = "Updated agenda" if meeting.get("meeting_type") == "meeting_preview" else "Updated minutes"
    note_date = artifact_posted_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        formatted = datetime.strptime(note_date, "%Y-%m-%d %H:%M:%S").strftime("%B %d, %Y")
    except ValueError:
        formatted = note_date

    if is_amended:
        note_text = "{}: Wareham posted a revised source document for this meeting, and this story was refreshed on {} to reflect the latest public record.".format(
            note_label,
            formatted,
        )
    else:
        note_text = "{}: This story was refreshed on {} after the underlying public meeting record changed.".format(
            note_label,
            formatted,
        )

    return '<p class="story-update"><strong>{}</strong></p>'.format(html.escape(note_text))


def _sync_story_citations(
    connection: Connection,
    story_id: int,
    source_item: Dict[str, object],
    extraction: Dict[str, object],
    explainers: List[Dict[str, str]],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM story_citations WHERE story_id = %s", (story_id,))
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
        citation_number = 2
        for explainer in explainers:
            cursor.execute(
                """
                INSERT INTO story_citations (
                    story_id,
                    citation_number,
                    label,
                    source_url,
                    note_text
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    story_id,
                    citation_number,
                    explainer["label"],
                    explainer["source_url"],
                    explainer["text"],
                ),
            )
            citation_number += 1


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


def _agenda_details(extraction: Dict[str, object]) -> Dict[str, object]:
    structured = extraction.get("structured_json") or {}
    if isinstance(structured, str):
        try:
            structured = json.loads(structured)
        except ValueError:
            structured = {}
    return structured if isinstance(structured, dict) else {}


def _agenda_highlight_blocks(extraction: Dict[str, object]) -> Tuple[str, List[Dict[str, str]]]:
    structured = _agenda_details(extraction)
    highlights = structured.get("agenda_highlights") or []
    if not isinstance(highlights, list):
        return "", []

    bullets = []
    explainers = []
    for raw_item in highlights[:6]:
        item = " ".join(str(raw_item).split())
        if not item:
            continue
        bullet = "<li>{}</li>".format(html.escape(item))
        lowered = item.lower()
        for key, explainer in AGENDA_EXPLAINERS.items():
            if key in lowered:
                bullet = "<li>{} <span class=\"story-note\">{}</span></li>".format(
                    html.escape(item),
                    html.escape(explainer["text"]),
                )
                explainers.append(explainer)
                break
        bullets.append(bullet)

    if not bullets:
        return "", []

    return "<h3>What is on the agenda</h3><ul>{}</ul>".format("".join(bullets)), explainers


def _story_structured_quality(extraction: Dict[str, object]) -> Dict[str, object]:
    structured = _agenda_details(extraction)
    warnings = extraction.get("warnings_json") or []
    if isinstance(warnings, str):
        try:
            warnings = json.loads(warnings)
        except ValueError:
            warnings = [warnings]
    if not isinstance(warnings, list):
        warnings = []

    title = " ".join(str(extraction.get("title") or "").split()).lower()
    body_text = str(extraction.get("body_text") or "")
    highlights = structured.get("agenda_highlights") or []
    sections = structured.get("agenda_sections") or []
    confidence = extraction.get("confidence_score")
    try:
        confidence_value = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_value = None

    return {
        "confidence": confidence_value,
        "warnings": warnings,
        "title": title,
        "body_length": len(body_text.strip()),
        "has_highlights": isinstance(highlights, list) and len(highlights) > 0,
        "has_sections": isinstance(sections, list) and len(sections) > 0,
    }


def _should_publish_story(meeting: Dict[str, object], extraction: Dict[str, object], story_type: str) -> bool:
    if story_type == "meeting_preview" and meeting["status"] in ("cancelled", "postponed", "continued"):
        return False

    quality = _story_structured_quality(extraction)
    confidence = quality["confidence"]
    title = quality["title"]
    warnings = [str(item).lower() for item in quality["warnings"]]

    if story_type == "meeting_preview":
        if "empty text" in " ".join(warnings):
            return False
        if title in GENERIC_EXTRACTION_TITLES and not quality["has_highlights"] and not quality["has_sections"]:
            return False
        if confidence is not None and confidence < 0.55 and not quality["has_highlights"]:
            return False
        if quality["body_length"] < 250 and not quality["has_highlights"]:
            return False
        if not meeting.get("meeting_time") and not meeting.get("location_name") and not quality["has_highlights"]:
            return False

    if story_type == "minutes_recap":
        if confidence is not None and confidence < 0.45 and quality["body_length"] < 250:
            return False

    return True


def _remote_access_block(extraction: Dict[str, object]) -> str:
    structured = _agenda_details(extraction)
    source_meta = structured.get("source_meta") if isinstance(structured, dict) else {}
    if not isinstance(source_meta, dict):
        return ""

    join_url = source_meta.get("remote_join_url")
    webinar_id = source_meta.get("remote_webinar_id")
    passcode = source_meta.get("remote_passcode")
    if not join_url and not webinar_id and not passcode:
        return ""

    details = []
    if join_url:
        details.append('Join link: <a href="{0}">{0}</a>'.format(html.escape(str(join_url))))
    if webinar_id:
        details.append("Webinar ID: {}".format(html.escape(str(webinar_id))))
    if passcode:
        details.append("Passcode: {}".format(html.escape(str(passcode))))

    return "<p><strong>Remote access:</strong> {}</p>".format(" | ".join(details))


def _build_story_copy(meeting: Dict[str, object], source_item: Dict[str, object], extraction: Dict[str, object], story_type: str) -> Tuple[str, str, str, str, str, List[Dict[str, str]]]:
    body_name = meeting["governing_body"] or "Wareham officials"
    meeting_date = _format_date(meeting["meeting_date"])
    meeting_time = _format_time(meeting["meeting_time"])
    location = meeting["location_name"] or "a location not listed in the source"
    source_url = source_item["canonical_url"]
    source_label = "posted minutes" if story_type == "minutes_recap" else "posted agenda"
    agenda_block = ""
    remote_block = ""
    explainers = []  # type: List[Dict[str, str]]

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
        agenda_block, explainers = _agenda_highlight_blocks(extraction)
        remote_block = _remote_access_block(extraction)
        kicker = (
            f"<p>The public can review the full <a href=\"{html.escape(source_url)}\">posted agenda</a> "
            f"for the complete list of items, attachments, and procedural details.</p>"
        )

    summary_lines = _choose_summary_lines(extraction["body_text"])
    if story_type == "meeting_preview" and agenda_block:
        middle = ""
        summary = dek
    elif summary_lines:
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

    body_html = intro + remote_block + agenda_block + middle + kicker
    body_text = re.sub(r"<[^>]+>", "", body_html)
    return headline, dek, summary[:1000], body_html, body_text, explainers


def _select_best_meeting_artifacts(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    selected = {}
    for row in rows:
        meeting_id = int(row["meeting_id"])
        artifact_type = row["artifact_type"] or ""
        if not is_public_story_artifact(artifact_type):
            continue

        story_type = "minutes_recap" if artifact_type == "minutes" else "meeting_preview"
        key = (meeting_id, story_type)
        title_blob = " ".join([str(row.get("source_title") or ""), str(row.get("extraction_title") or "")]).lower()
        has_text = bool((row.get("body_text") or "").strip())
        if ("cancelled" in title_blob or "canceled" in title_blob) and story_type == "meeting_preview":
            has_text = False

        score = artifact_priority(
            artifact_type,
            row.get("artifact_format") or "",
            bool(row.get("is_amended")),
            has_text,
        )
        if row.get("artifact_posted_at"):
            score += 5

        current = selected.get(key)
        if current is None or score > current["_score"]:
            row_copy = dict(row)
            row_copy["_score"] = score
            selected[key] = row_copy

    return [selected[key] for key in sorted(selected.keys())]


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
                ma.format AS artifact_format,
                ma.posted_at AS artifact_posted_at,
                ma.is_amended,
                ma.source_item_id,
                d.document_url AS resolved_document_url,
                si.canonical_url,
                si.title AS source_title,
                de.id AS extraction_id,
                de.body_text,
                de.title AS extraction_title,
                de.structured_json,
                de.confidence_score,
                de.warnings_json
            FROM meetings m
            INNER JOIN meeting_artifacts ma ON ma.meeting_id = m.id
            INNER JOIN source_items si ON si.id = ma.source_item_id
            LEFT JOIN documents d ON d.id = ma.document_id
            LEFT JOIN document_extractions de ON de.document_id = ma.document_id
            WHERE ma.is_primary = 1
            ORDER BY m.id ASC, ma.id ASC
            """
        )
        rows = cursor.fetchall()

    for row in _select_best_meeting_artifacts(rows):
        meeting_id = int(row["meeting_id"])
        artifact_type = row["artifact_type"] or ""
        story_type = "minutes_recap" if artifact_type == "minutes" else "meeting_preview"

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
            "canonical_url": row["resolved_document_url"] or row["canonical_url"],
            "source_title": row["source_title"] or "",
        }
        extraction = {
            "id": int(row["extraction_id"]) if row["extraction_id"] else 0,
            "title": row["extraction_title"] or "",
            "body_text": row["body_text"] or "",
            "structured_json": row["structured_json"],
            "confidence_score": row["confidence_score"],
            "warnings_json": row["warnings_json"],
        }

        if not meeting["governing_body"] or not meeting["meeting_date"]:
            continue

        artifact_posted_at = row["artifact_posted_at"].strftime("%Y-%m-%d %H:%M:%S") if row["artifact_posted_at"] else None
        headline, dek, summary, body_html, body_text, explainers = _build_story_copy(meeting, source_item, extraction, story_type)
        content_signature = _story_content_signature(headline, dek, summary, body_text)
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
                "SELECT id, slug, published_at, publish_status, source_basis_json FROM stories WHERE meeting_id = %s AND story_type = %s LIMIT 1",
                (meeting["id"], story_type),
            )
            existing_story = cursor.fetchone()
        previous_basis = _parse_story_basis(existing_story["source_basis_json"]) if existing_story else {}
        basis_json = _story_basis_json(
            source_item,
            extraction,
            artifact_type,
            artifact_posted_at,
            bool(row.get("is_amended")),
            content_signature,
        )

        if not _should_publish_story(meeting, extraction, story_type):
            if existing_story:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE stories
                        SET publish_status = 'suppressed',
                            source_basis_json = %s
                        WHERE id = %s
                        """,
                        (
                            basis_json,
                            int(existing_story["id"]),
                        ),
                    )
            continue

        if existing_story:
            previous_signature = previous_basis.get("content_signature")
            basis_matches = (
                previous_basis.get("source_item_id") == source_item["source_item_id"]
                and previous_basis.get("extraction_id") == extraction["id"]
                and previous_basis.get("source_url") == source_item["canonical_url"]
                and previous_basis.get("artifact_type") == artifact_type
            )
            if (
                previous_signature == content_signature
                and basis_matches
                and existing_story.get("publish_status") == "published"
            ):
                continue

        story_id = None
        if existing_story:
            story_id = int(existing_story["id"])
            existing_published_at = existing_story["published_at"].strftime("%Y-%m-%d %H:%M:%S") if existing_story.get("published_at") else published_at
            story_body_html = body_html
            story_body_text = body_text
            if previous_basis.get("content_signature") != content_signature:
                update_note = _story_update_note(
                    meeting,
                    previous_basis,
                    source_item,
                    extraction,
                    artifact_posted_at,
                    bool(row.get("is_amended")),
                )
                if update_note:
                    story_body_html = update_note + story_body_html
                    story_body_text = re.sub(r"<[^>]+>", "", story_body_html)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE stories
                    SET governing_body_id = %s,
                        headline = %s,
                        dek = %s,
                        summary = %s,
                        body_html = %s,
                        body_text = %s,
                        publish_status = 'published',
                        published_at = %s,
                        display_date = %s,
                        sort_date = %s,
                        source_basis_json = %s
                    WHERE id = %s
                    """,
                    (
                        meeting["governing_body_id"],
                        headline,
                        dek,
                        summary,
                        story_body_html,
                        story_body_text,
                        existing_published_at,
                        display_date,
                        sort_date,
                        basis_json,
                        story_id,
                    ),
                )
        else:
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
                        basis_json,
                    ),
                )
                story_id = int(cursor.lastrowid)

        if story_id is None:
            continue

        _sync_story_citations(connection, story_id, source_item, extraction, explainers)
        with connection.cursor() as cursor:
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
                ma.format AS artifact_format,
                ma.is_amended,
                si.canonical_url
            FROM meetings m
            INNER JOIN meeting_artifacts ma ON ma.meeting_id = m.id
            INNER JOIN source_items si ON si.id = ma.source_item_id
            WHERE m.meeting_date IS NOT NULL
              AND ma.is_primary = 1
            ORDER BY m.meeting_date ASC, m.id ASC
            """
        )
        meeting_rows = cursor.fetchall()

    for row in meeting_rows:
        body_name = row["governing_body"]
        if not body_name:
            continue
        meeting_date = row["meeting_date"].strftime("%Y-%m-%d")
        meeting_time = _db_time_string(row["meeting_time"]) if row["meeting_time"] else "00:00:00"
        starts_at = f"{meeting_date} {meeting_time}"
        title = canonical_event_title(body_name)
        valid_calendar_item = True
        if row["status"] == "cancelled":
            valid_calendar_item = False
        if row["status"] in ("postponed", "continued"):
            valid_calendar_item = False
        if not is_calendar_artifact(row["artifact_type"] or ""):
            valid_calendar_item = False
        if row["is_amended"] and (row["artifact_format"] or "") == "html":
            valid_calendar_item = False

        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM calendar_events WHERE meeting_id = %s LIMIT 1", (int(row["id"]),))
            existing_event = cursor.fetchone()

        if not valid_calendar_item:
            if existing_event:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM calendar_events WHERE id = %s", (int(existing_event["id"]),))
            continue

        with connection.cursor() as cursor:
            if existing_event:
                cursor.execute(
                    """
                    UPDATE calendar_events
                    SET governing_body_id = %s,
                        title = %s,
                        starts_at = %s,
                        location_name = %s,
                        body_name = %s,
                        source_url = %s,
                        status = 'scheduled',
                        description = %s
                    WHERE id = %s
                    """,
                    (
                        row["governing_body_id"],
                        title,
                        starts_at,
                        row["location_name"],
                        body_name,
                        row["canonical_url"],
                        f"Official Wareham meeting listing for the {body_name}.",
                        int(existing_event["id"]),
                    ),
                )
            else:
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
