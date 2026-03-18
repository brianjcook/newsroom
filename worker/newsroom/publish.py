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
    stories_updated: int
    events_created: int
    events_updated: int


GENERIC_EXTRACTION_TITLES = {
    "agenda",
    "minutes",
    "pdf",
    "packet",
    "html",
    "reference",
}


EDITORIAL_SIGNAL_RULES = [
    ("safe harbor marina", 95, "land_use"),
    ("redevelop", 42, "land_use"),
    ("school choice", 82, "policy"),
    ("policy review", 76, "policy"),
    ("discriminatory harassment", 52, "policy"),
    ("stormwater", 40, "infrastructure"),
    ("possible vote", 50, "formal_action"),
    ("vote", 35, "formal_action"),
    ("public hearing", 45, "public_hearing"),
    ("hearing", 20, "public_hearing"),
    ("budget", 35, "budget"),
    ("appropriation", 35, "budget"),
    ("contract", 28, "contract"),
    ("bid", 24, "contract"),
    ("zoning", 38, "land_use"),
    ("special permit", 38, "land_use"),
    ("site plan", 32, "land_use"),
    ("wastewater", 42, "infrastructure"),
    ("sewer", 34, "infrastructure"),
    ("water", 22, "infrastructure"),
    ("road", 18, "infrastructure"),
    ("capital", 24, "budget"),
    ("town meeting", 28, "town_meeting"),
    ("article", 18, "town_meeting"),
    ("bylaw", 30, "policy"),
    ("policy", 28, "policy"),
    ("appoint", 20, "appointment"),
    ("tobacco violation", 72, "permit"),
    ("violation", 28, "permit"),
    ("title 5", 40, "policy"),
    ("variance request", 34, "permit"),
    ("license", 22, "permit"),
    ("permit", 20, "permit"),
    ("future of the committee", 34, "policy"),
    ("next steps", 18, "policy"),
    ("accept", 14, "formal_action"),
    ("approve", 14, "formal_action"),
    ("adopt", 22, "policy"),
    ("deny", 18, "formal_action"),
]


CATEGORY_EXPLANATIONS = {
    "formal_action": "it could lead to a formal decision or vote",
    "public_hearing": "it opens the issue to formal public comment",
    "budget": "it could affect town spending or budget priorities",
    "contract": "it could shape a contract, bid, or procurement decision",
    "land_use": "it could affect land use, zoning, or development review",
    "infrastructure": "it could affect local infrastructure or utility planning",
    "town_meeting": "it could shape what reaches Town Meeting",
    "policy": "it could change local rules, policy, or procedure",
    "appointment": "it could change town appointments or representation",
    "permit": "it could affect a local license or permit decision",
}

TRUNCATED_ENDINGS = (
    " the",
    " a",
    " an",
    " of",
    " and",
    " to",
    " for",
    " from",
    " with",
    " on",
    " at",
    " in",
    " by",
    " regarding",
)


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


def _agenda_highlights(extraction: Dict[str, object]) -> List[str]:
    structured = _agenda_details(extraction)
    highlights = structured.get("agenda_highlights") or []
    if not isinstance(highlights, list):
        return []
    return [" ".join(str(item).split()) for item in highlights if " ".join(str(item).split())]


def _story_basis_json(
    source_item: Dict[str, object],
    extraction: Dict[str, object],
    artifact_type: str,
    artifact_posted_at: Optional[str],
    is_amended: bool,
    content_signature: str,
) -> str:
    highlights = _agenda_highlights(extraction)
    return json.dumps(
        {
            "source_item_id": source_item["source_item_id"],
            "extraction_id": extraction["id"],
            "source_url": source_item["canonical_url"],
            "artifact_type": artifact_type,
            "artifact_posted_at": artifact_posted_at,
            "is_amended": bool(is_amended),
            "content_signature": content_signature,
            "agenda_highlights": highlights[:8],
        }
    )


def _change_item_label(text: str) -> str:
    phrase = _focus_summary_phrase(text)
    if phrase:
        return phrase
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) > 120:
        cleaned = cleaned[:117].rstrip(" ,;:-") + "..."
    return cleaned


def _change_summary(previous_basis: Dict[str, object], extraction: Dict[str, object]) -> str:
    previous_highlights = previous_basis.get("agenda_highlights") or []
    if not isinstance(previous_highlights, list):
        previous_highlights = []
    previous_clean = [" ".join(str(item).split()) for item in previous_highlights if " ".join(str(item).split())]
    current_clean = _agenda_highlights(extraction)

    if not previous_clean and not current_clean:
        return ""

    previous_set = set(previous_clean)
    current_set = set(current_clean)
    added = [item for item in current_clean if item not in previous_set]
    removed = [item for item in previous_clean if item not in current_set]

    change_bits = []
    if added:
        change_bits.append("New agenda items include {}".format("; ".join(_change_item_label(item) for item in added[:2])))
    if removed:
        change_bits.append("Items no longer listed include {}".format("; ".join(_change_item_label(item) for item in removed[:2])))
    if not change_bits and current_clean != previous_clean:
        change_bits.append("The order or emphasis of agenda items changed")

    return ". ".join(change_bits[:2]).strip(". ")


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

    change_summary = _change_summary(previous_basis, extraction)

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
    if change_summary:
        note_text = "{} {}.".format(note_text, change_summary)

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


def _normalize_item_text(text: str) -> str:
    return " ".join(str(text or "").replace("\xa0", " ").split())


def _looks_truncated(text: str) -> bool:
    normalized = _normalize_item_text(text)
    if len(normalized) < 18:
        return True
    lowered = normalized.lower().rstrip(" .;,:-")
    if lowered.endswith(TRUNCATED_ENDINGS):
        return True
    if normalized.count("(") > normalized.count(")"):
        return True
    if normalized.count('"') % 2 == 1:
        return True
    return False


def _strip_agenda_lead_in(text: str) -> str:
    normalized = _normalize_item_text(text)
    patterns = [
        r"^\d{1,2}:\d{2}\s*(a\.m\.|p\.m\.)\s*",
        r"^discussion and possible vote regarding\s+",
        r"^discussion and possible vote on\s+",
        r"^discussion and possible vote to\s+",
        r"^discussion regarding\s+",
        r"^discussion on\s+",
        r"^possible vote regarding\s+",
        r"^possible vote on\s+",
        r"^possible vote to\s+",
        r"^public hearings?(?:\s*\([^)]*\))?\s*[:\-]?\s*",
        r"^continued public hearings?(?:\s*\([^)]*\))?\s*[:\-]?\s*",
    ]
    for pattern in patterns:
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)
    return normalized.strip(" .;:-")


def _headline_phrase(text: str) -> str:
    cleaned = _strip_agenda_lead_in(text)
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if "future of the committee" in lowered:
        return "Committee's Future"
    if lowered == "next steps":
        return "Next Steps"
    if "safe harbor marina" in lowered and "redevelop" in lowered:
        return "Safe Harbor Marina Redevelopment"
    if "river hawk" in lowered and "stormwater" in lowered:
        return "River Hawk Stormwater Upgrades"
    if "school choice" in lowered:
        return "School Choice Vote"
    if "policy review" in lowered:
        return "Policy Review"
    if "title 5" in lowered:
        return "Title 5 Regulations"
    cleaned = re.sub(r"^wareham\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(continued\s+)?public hearings?:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(continued\s+)?hearing[s]?:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^request for determination of applicability \(rda\)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^notice of intents? \(noi\)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^abbreviated notice of resource area delineation requests? \(anrad\)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bthe finalization of\b", "finalizing", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bto recommend action on\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d{1,2}:\d{2}\s*[ap]\.?m\.?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*vote\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(possible vote\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\barticles for the spring annual town meeting\b",
        "Spring Annual Town Meeting articles",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\barticles for the spring annual town\b",
        "Spring Annual Town Meeting articles",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\brecommend action on articles for the ([a-z ]+?) town\b",
        lambda match: "{} Town Meeting articles".format(match.group(1).strip().title()),
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bregarding\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bpolicy review\s*-\s*", "Policy Review: ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    return cleaned[:120].rstrip(" ,;:-")


def _headline_action(text: str) -> str:
    lowered = _normalize_item_text(text).lower()
    if "public hearing" in lowered or "hearing" in lowered:
        return "to Hear"
    if "violation" in lowered:
        return "to Discuss"
    if "discussion" in lowered:
        return "to Discuss"
    if "consideration" in lowered or "future of the committee" in lowered or "next steps" in lowered:
        return "to Discuss"
    if "presentation" in lowered:
        return "to Review"
    if "appoint" in lowered or "appointment" in lowered:
        return "to Consider"
    if "vote" in lowered or "consider" in lowered:
        return "to Consider"
    return "to Meet and Consider"


def _trim_trailing_detail(text: str) -> str:
    trimmed = text.strip(" ,.;:-")
    split_patterns = [
        r"\s+[;-]\s+",
        r"\s+\((?=map|lot|dep|continued|vote|public hearing)",
        r",\s+(?=located at|at\s+\d+|wareham, ma|wareham ma)",
        r"\s+(?=for property located at\b)",
        r"\s+(?=located at\b)",
        r"\s+(?=under order of conditions\b)",
        r"\s+(?=under the wetlands protection act\b)",
        r"\s+(?=pursuant to\b)",
        r"\s+(?=file no\.)",
        r"\s+(?=dep file no\.)",
    ]
    for pattern in split_patterns:
        parts = re.split(pattern, trimmed, maxsplit=1, flags=re.IGNORECASE)
        if parts and parts[0]:
            trimmed = parts[0].strip(" ,.;:-")
    return trimmed


def _normalize_focus_phrase(text: str) -> str:
    cleaned = _strip_agenda_lead_in(text)
    if not cleaned:
        return ""

    lowered = cleaned.lower()
    special_patterns = [
        (r"safe harbor marina.*redevelop", "Safe Harbor Marina redevelopment"),
        (r"river hawk.*stormwater", "River Hawk stormwater work"),
        (r"school choice", "school choice vote"),
        (r"policy review", "policy review"),
        (r"comprehensive wastewater management plan|cwmp", "Comprehensive Wastewater Management Plan"),
        (r"open space and recreation plan", "Open Space and Recreation Plan"),
        (r"municipal maintenance", "municipal maintenance abatements"),
    ]
    for pattern, replacement in special_patterns:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            return replacement

    tobacco_match = re.search(r"tobacco violations?\s+(?:for|at)\s+(.+)", cleaned, flags=re.IGNORECASE)
    if tobacco_match:
        subject = _trim_trailing_detail(tobacco_match.group(1))
        return "tobacco violations at {}".format(subject) if subject else "tobacco violations"

    variance_match = re.search(r"variance requests?\s+(?:for|at)\s+(.+)", cleaned, flags=re.IGNORECASE)
    if variance_match:
        subject = _trim_trailing_detail(variance_match.group(1))
        return "variance request for {}".format(subject) if subject else "variance request"

    cleaned = re.sub(r"^continued\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(public hearing|public hearings|hearing|hearings)\s*:?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^notice of intents? \(noi\)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^request for determination of applicability \(rda\)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^abbreviated notice of resource area delineation requests? \(anrad\)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^discussion and possible vote (regarding|on|to)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^discussion (regarding|on)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^possible vote (regarding|on|to)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^review of\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^report of\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^update on\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bto recommend action on\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\barticles for the spring annual town meeting\b", "Spring Town Meeting articles", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\barticles for the spring annual town\b", "Spring Town Meeting articles", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bregarding\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bpolicy review\s*-\s*", "policy review on ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    cleaned = _trim_trailing_detail(cleaned)

    if not cleaned:
        return ""

    if len(cleaned) > 96:
        shortened = re.split(r",\s+|\s+and\s+|\s+for\s+", cleaned, maxsplit=1, flags=re.IGNORECASE)[0].strip(" ,.;:-")
        if len(shortened) >= 24:
            cleaned = shortened

    if cleaned and cleaned[0].isupper():
        return cleaned
    return cleaned[:1].lower() + cleaned[1:] if cleaned else ""


def _focus_summary_phrase(text: str) -> str:
    phrase = _normalize_focus_phrase(text)
    if phrase:
        return phrase
    return _headline_phrase(text)


def _sentence_case(value: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    return text[0].upper() + text[1:]


def _display_location(value: str) -> str:
    location = " ".join(str(value or "").split())
    if not location:
        return ""
    if location.upper() == location:
        location = location.title()
        location = re.sub(r"\bMa\b", "MA", location)
        location = re.sub(r"\bRm\b\.?", "Rm.", location)
        location = re.sub(r"\bFy(\d+)\b", r"FY\1", location)
    return location


def _looks_garbled(text: str) -> bool:
    normalized = _normalize_item_text(text)
    if not normalized:
        return True
    if re.match(r"^[a-z]:\s", normalized, flags=re.IGNORECASE):
        return True
    if normalized.startswith("PK\x03\x04") or "\x00" in normalized:
        return True

    printable = sum(1 for char in normalized if char.isprintable())
    if printable / float(max(len(normalized), 1)) < 0.95:
        return True

    letters = [char for char in normalized if char.isalpha()]
    if letters:
        upper_ratio = sum(1 for char in letters if char.isupper()) / float(len(letters))
        if upper_ratio > 0.88 and len(normalized.split()) > 3:
            return True

    return False


def _is_low_value_focus_line(text: str) -> bool:
    lowered = _normalize_item_text(text).lower()
    if not lowered:
        return True
    if re.search(
        r"\b(superintendent[’']?s report|director of finance|financial report|grants report|school committee report)\b",
        lowered,
        flags=re.IGNORECASE,
    ):
        if not any(
            token in lowered
            for token in (
                "policy review",
                "school choice",
                "tobacco violation",
                "variance request",
                "safe harbor marina",
                "stormwater",
                "wastewater",
                "public hearing",
            )
        ):
            return True
    if any(
        token in lowered
        for token in (
            "call to order",
            "roll call",
            "adjournment",
            "signing of documents approved",
            "any other business",
            "good news",
            "public participation",
            "announcements",
            "consent agenda",
            "review and approve minutes",
        )
    ):
        return True
    return False


def _summary_phrase_list(items: List[str], limit: int = 2) -> List[str]:
    normalized_items = [_normalize_item_text(item) for item in items]
    if sum(1 for item in normalized_items if "tobacco violation" in item.lower()) >= 2:
        phrases = ["Tobacco Violations"]
        for item in normalized_items:
            phrase = _focus_summary_phrase(item)
            if not phrase or _looks_garbled(phrase) or _is_low_value_focus_line(phrase) or "tobacco violation" in phrase.lower():
                continue
            phrases.append(phrase)
            if len(phrases) >= limit:
                break
        return phrases[:limit]

    phrases = []  # type: List[str]
    seen = set()
    for item in normalized_items:
        phrase = _focus_summary_phrase(item)
        if not phrase or _looks_garbled(phrase) or _is_low_value_focus_line(phrase):
            continue
        if phrase in seen:
            continue
        seen.add(phrase)
        phrases.append(phrase)
        if len(phrases) >= limit:
            break
    return phrases


def _sentence_from_phrases(prefix: str, phrases: List[str]) -> str:
    if not phrases:
        return ""
    if len(phrases) == 1:
        return "{} {}.".format(prefix, phrases[0])
    return "{} {} and {}.".format(prefix, phrases[0], phrases[1])


def _headline_focus_phrase(focus_items: List[Dict[str, object]]) -> str:
    texts = [_normalize_item_text(str(item.get("text") or "")) for item in focus_items[:3]]
    violation_count = sum(1 for text in texts if "tobacco violation" in text.lower())
    if violation_count >= 2:
        return "Tobacco Violations"
    if sum(1 for text in texts if "variance request" in text.lower()) >= 2:
        return "Variance Requests"
    if texts:
        return _headline_phrase(texts[0])
    return ""


def _preview_headline(body_name: str, meeting_date: str, focus_items: List[Dict[str, object]]) -> str:
    if not focus_items:
        return f"{body_name} to Meet {meeting_date}"

    first = _headline_focus_phrase(focus_items)
    if first:
        return f"{body_name} {_headline_action(str(focus_items[0]['text']))} {first}"
    return f"{body_name} to Meet {meeting_date}"


def _preview_dek(body_name: str, meeting_date: str, meeting_time: str, location: str, focus_items: List[Dict[str, object]]) -> str:
    if meeting_time and meeting_time != "at a time not listed in the source":
        return f"{body_name} will meet {meeting_date} at {meeting_time}."
    return f"{body_name} will meet {meeting_date}."


def _preview_intro(body_name: str, meeting_date: str, meeting_time: str, location: str, focus_items: List[Dict[str, object]]) -> str:
    if not focus_items:
        return (
            f"<p>The Wareham {html.escape(body_name)} is scheduled to meet on {html.escape(meeting_date)} "
            f"{html.escape(meeting_time)} at {html.escape(location)}, according to the posted agenda.</p>"
        )

    first = _focus_summary_phrase(str(focus_items[0]["text"]))
    second = _focus_summary_phrase(str(focus_items[1]["text"])) if len(focus_items) > 1 else ""
    if first and second:
        return (
            f"<p>The Wareham {html.escape(body_name)} will meet on {html.escape(meeting_date)} at "
            f"{html.escape(meeting_time)} at {html.escape(location)}. The posted agenda centers on "
            f"{html.escape(first)} and {html.escape(second)}.</p>"
            f"<p>{html.escape(_focus_sentence(focus_items[0]))}</p>"
        )
    if first:
        return (
            f"<p>The Wareham {html.escape(body_name)} will meet on {html.escape(meeting_date)} at "
            f"{html.escape(meeting_time)} at {html.escape(location)}. The posted agenda puts "
            f"{html.escape(first)} near the top of the meeting.</p>"
            f"<p>{html.escape(_focus_sentence(focus_items[0]))}</p>"
        )
    return (
        f"<p>The Wareham {html.escape(body_name)} is scheduled to meet on {html.escape(meeting_date)} "
        f"{html.escape(meeting_time)} at {html.escape(location)}, according to the posted agenda.</p>"
    )


def _choose_summary_lines(text: str, limit: int = 3) -> List[str]:
    lines = _clean_lines(text)
    filtered = []
    for line in lines:
        lower = line.lower()
        if _looks_garbled(line):
            continue
        if "agenda center" in lower or "previous versions" in lower or "packet" in lower:
            continue
        if "agenda" in lower or "minutes" in lower or "wareham" in lower or "page " in lower:
            if len(line) < 40:
                continue
        if _looks_truncated(line):
            continue
        filtered.append(line)
        if len(filtered) >= limit:
            break
    return filtered


def _split_generic_agenda_body(text: str) -> List[str]:
    body_text = str(text or "")
    if body_text.count("\n") < 4:
        body_text = re.sub(r"\s+([IVXLCDM]+[\.\)])\s+", r"\n\1 ", body_text)
        body_text = re.sub(r"\s+(\d+[\.\)])\s+", r"\n\1 ", body_text)
        body_text = re.sub(r"\s+([a-z][\.\)])\s+", r"\n\1 ", body_text)
        body_text = re.sub(r"\s+([A-Z][A-Z /&'-]{6,}:)\s+", r"\n\1 ", body_text)
    return [segment for segment in body_text.splitlines() if segment.strip()]


def _is_heading_token_line(text: str) -> bool:
    normalized = _normalize_item_text(text)
    if not normalized:
        return True
    words = normalized.split()
    if len(words) <= 4 and all(word[:1].isupper() for word in words if word):
        letters = [char for char in normalized if char.isalpha()]
        if letters and sum(1 for char in letters if char.isupper()) / float(len(letters)) > 0.8:
            return True
    return False


def _clean_generic_agenda_line(text: str) -> str:
    line = _normalize_item_text(text)
    if not line or len(line) < 6:
        return ""

    line = re.sub(r"^[ivxlcdm]+[\.\)]\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"^\d+[\.\)]\s*", "", line)
    line = re.sub(r"^[a-z][\.\)]\s*", "", line, flags=re.IGNORECASE)
    line = _normalize_item_text(line)
    lowered = line.lower()

    if not line or len(line) < 8:
        return ""
    if len(line.split()) < 3:
        return ""
    if "http://" in lowered or "https://" in lowered:
        return ""
    if _looks_garbled(line) or _looks_truncated(line):
        return ""
    if _is_heading_token_line(line):
        return ""

    if any(
        lowered.startswith(token)
        for token in (
            "town of wareham",
            "meeting agenda",
            "day & date",
            "date and time",
            "date:",
            "time:",
            "place:",
            "location:",
            "zoom meeting information",
            "zoom link",
            "join zoom meeting",
            "meeting id:",
            "passcode:",
            "call to order",
            "roll call",
            "approval of minutes",
            "adjournment",
            "meeting",
            "committee",
            "council",
            "next scheduled meeting date",
            "any other business",
            "public comment",
        )
    ):
        return ""

    letters = [char for char in line if char.isalpha()]
    if len(letters) < 6:
        return ""
    upper_ratio = sum(1 for char in letters if char.isupper()) / float(len(letters)) if letters else 0.0
    if upper_ratio > 0.85:
        return ""
    weird_chars = sum(1 for char in line if not (char.isalnum() or char.isspace() or char in ".,:;!?&'\"/-()"))
    if weird_chars > 1:
        return ""
    if len(line) > 180 and ":" not in line and ";" not in line:
        return ""
    return line.strip(" ,.;:-")


def _generic_agenda_lines(extraction: Dict[str, object], limit: int = 5) -> List[str]:
    lines = []
    for raw_line in _split_generic_agenda_body(extraction.get("body_text") or ""):
        line = _clean_generic_agenda_line(raw_line)
        if not line:
            continue
        if line not in lines:
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _score_editorial_line(text: str, context: str = "") -> Tuple[int, List[str]]:
    lowered = " ".join([context, text]).lower()
    score = 0
    categories = []  # type: List[str]

    for needle, weight, category in EDITORIAL_SIGNAL_RULES:
        if needle in lowered:
            score += weight
            categories.append(category)

    if len(text) > 80:
        score += 4
    if "discussion" in lowered:
        score += 10
    if "presentation" in lowered:
        score += 8
    if "approved" in lowered or "adopted" in lowered or "denied" in lowered:
        score += 12
        categories.append("formal_action")

    deduped = []
    for category in categories:
        if category not in deduped:
            deduped.append(category)
    return score, deduped


def _focus_reason(categories: List[str]) -> str:
    phrases = [CATEGORY_EXPLANATIONS[category] for category in categories if category in CATEGORY_EXPLANATIONS]
    if not phrases:
        return ""
    if len(phrases) == 1:
        return phrases[0]
    return "{} and {}".format(", ".join(phrases[:-1]), phrases[-1])


def _with_article(phrase: str) -> str:
    text = " ".join(str(phrase or "").split())
    if not text:
        return ""
    if re.match(r"^(the|a|an)\b", text, flags=re.IGNORECASE):
        return text
    return "the {}".format(text)


def _focus_sentence(item: Dict[str, object]) -> str:
    phrase = _focus_summary_phrase(str(item.get("text") or "")) or str(item.get("text") or "")
    raw_text = _normalize_item_text(str(item.get("text") or ""))
    lowered = raw_text.lower()
    categories = list(item.get("reasons") or [])

    if "permit" in categories and "tobacco violation" in lowered:
        return "The board is expected to review tobacco violations tied to local retailers."
    if "permit" in categories and "variance request" in lowered:
        return "The board is expected to take up {}.".format(_with_article(phrase))
    if "public_hearing" in categories:
        if "safe harbor marina" in lowered:
            return "A public hearing is scheduled on Safe Harbor Marina redevelopment plans."
        if "stormwater" in lowered:
            return "A public hearing is scheduled on stormwater-related work tied to the project."
        return "A public hearing is scheduled on {}.".format(_with_article(phrase))
    if "land_use" in categories:
        if "safe harbor marina" in lowered:
            return "Commissioners are set to review the Safe Harbor Marina redevelopment proposal."
        if "river hawk" in lowered and "stormwater" in lowered:
            return "Commissioners are also expected to review River Hawk stormwater work."
        return "The agenda includes {} as a development-related item.".format(_with_article(phrase))
    if "budget" in categories:
        return "Members are set to review {} as part of the meeting's fiscal agenda.".format(_with_article(phrase))
    if "contract" in categories:
        return "The agenda includes {}, which could shape a contract or procurement decision.".format(_with_article(phrase))
    if "town_meeting" in categories:
        return "Members are expected to discuss {} ahead of Town Meeting.".format(_with_article(phrase))
    if "policy" in categories:
        if "future of the committee" in lowered:
            return "Members are set to discuss the future of the committee and where its work goes next."
        if lowered == "next steps":
            return "Members are also expected to discuss the committee's next steps."
        if "policy review" in lowered:
            return "Committee members are set to review school policy proposals."
        if "school choice" in lowered:
            return "The committee is also expected to revisit the district's school choice position."
        return "The agenda includes {} as a policy item.".format(_with_article(phrase))
    if "appointment" in categories:
        return "Members are expected to consider {}.".format(_with_article(phrase))
    if "permit" in categories:
        return "Members are expected to review {}.".format(_with_article(phrase))
    if "formal_action" in categories:
        return "Members could take formal action on {}.".format(_with_article(phrase))
    if "infrastructure" in categories:
        if "wastewater" in lowered or "cwmp" in lowered:
            return "The agenda includes discussion of the Comprehensive Wastewater Management Plan."
        if "open space and recreation plan" in lowered:
            return "Members are expected to discuss the Open Space and Recreation Plan."
        return "The agenda includes {} as an infrastructure-related item.".format(_with_article(phrase))
    return "{} is among the main items listed on the agenda.".format(_sentence_case(phrase))


def _agenda_focus_items(extraction: Dict[str, object], limit: int = 4) -> List[Dict[str, object]]:
    structured = _agenda_details(extraction)
    sections = structured.get("agenda_sections") or []
    focus = []  # type: List[Dict[str, object]]

    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_title = " ".join(str(section.get("title") or "").split())
            for raw_item in section.get("items") or []:
                item = " ".join(str(raw_item).split())
                if not item:
                    continue
                if _is_low_value_focus_line(item):
                    continue
                if _looks_truncated(item):
                    continue
                score, reasons = _score_editorial_line(item, section_title)
                if score <= 0:
                    continue
                focus.append(
                    {
                        "text": item,
                        "score": score,
                        "section": section_title,
                        "reasons": reasons,
                    }
                )

    if not focus:
        for item in _agenda_highlights(extraction):
            if _is_low_value_focus_line(item):
                continue
            if _looks_truncated(item):
                continue
            score, reasons = _score_editorial_line(item)
            if score <= 0:
                continue
            focus.append({"text": item, "score": score, "section": "", "reasons": reasons})

    focus.sort(key=lambda entry: (-int(entry["score"]), str(entry["text"])))
    deduped = []
    seen = set()
    for item in focus:
        display_key = (_focus_summary_phrase(str(item["text"])) or str(item["text"])).lower()
        if display_key in seen:
            continue
        seen.add(display_key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _minutes_focus_items(extraction: Dict[str, object], limit: int = 4) -> List[Dict[str, object]]:
    focus = []  # type: List[Dict[str, object]]
    for line in _clean_lines(str(extraction.get("body_text") or "")):
        if _is_low_value_focus_line(line):
            continue
        if _looks_truncated(line):
            continue
        score, reasons = _score_editorial_line(line)
        lowered = line.lower()
        if "approved" in lowered or "denied" in lowered or "adopted" in lowered or "voted" in lowered:
            score += 20
        if score <= 0:
            continue
        focus.append({"text": line, "score": score, "reasons": reasons})

    focus.sort(key=lambda entry: (-int(entry["score"]), str(entry["text"])))
    deduped = []
    seen = set()
    for item in focus:
        display_key = (_focus_summary_phrase(str(item["text"])) or str(item["text"])).lower()
        if display_key in seen:
            continue
        seen.add(display_key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _focus_list_block(items: List[Dict[str, object]], heading: str) -> str:
    if not items:
        return ""

    bullets = []
    for item in items:
        text = html.escape(_focus_sentence(item))
        reason = _focus_reason(list(item.get("reasons") or []))
        if reason:
            bullets.append("<li>{} <span class=\"story-note\">Why it matters: {}.</span></li>".format(text, html.escape(reason)))
        else:
            bullets.append("<li>{}</li>".format(text))
    return "<h3>{}</h3><ul>{}</ul>".format(html.escape(heading), "".join(bullets))


def _focus_summary(items: List[Dict[str, object]]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return _focus_summary_phrase(str(items[0]["text"])) or str(items[0]["text"])
    first = _focus_summary_phrase(str(items[0]["text"])) or str(items[0]["text"])
    second = _focus_summary_phrase(str(items[1]["text"])) or str(items[1]["text"])
    return "{} and {}".format(first, second)


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
    sections = structured.get("agenda_sections") or []
    highlights = structured.get("agenda_highlights") or []

    agenda_items = []  # type: List[str]
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            for raw_item in section.get("items") or []:
                item = " ".join(str(raw_item).split())
                if not item or _looks_truncated(item):
                    continue
                if item not in agenda_items:
                    agenda_items.append(item)
                if len(agenda_items) >= 8:
                    break
            if len(agenda_items) >= 8:
                break

    if not agenda_items and isinstance(highlights, list):
        for raw_item in highlights[:8]:
            item = " ".join(str(raw_item).split())
            if not item or _looks_truncated(item):
                continue
            agenda_items.append(item)

    if not agenda_items:
        return "", []

    bullets = []
    explainers = []
    for item in agenda_items[:8]:
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
    location = _display_location(str(meeting["location_name"] or "")) or "a location not listed in the source"
    source_url = source_item["canonical_url"]
    source_label = "posted minutes" if story_type == "minutes_recap" else "posted agenda"
    agenda_block = ""
    focus_block = ""
    remote_block = ""
    explainers = []  # type: List[Dict[str, str]]
    focus_items = []  # type: List[Dict[str, object]]

    if story_type == "minutes_recap":
        focus_items = _minutes_focus_items(extraction)
        headline = f"Wareham {body_name} minutes posted for {meeting_date}"
        if focus_items:
            dek = f"The minutes highlight action on {_focus_summary(focus_items)}."
            focus_block = _focus_list_block(focus_items, "What stands out in the minutes")
            summary = _sentence_from_phrases(
                "The posted minutes highlight",
                _summary_phrase_list([str(item["text"]) for item in focus_items]),
            ) or dek
        else:
            dek = f"Posted minutes show what the {body_name} recorded for its {meeting_date} meeting."
            summary = dek
        intro = (
            f"<p>Minutes for the Wareham {html.escape(body_name)} meeting dated {html.escape(meeting_date)} "
            f"have been posted on the town website, according to the linked source document.</p>"
        )
        kicker = (
            f"<p>The document is being treated as a public-record recap. Readers should consult the "
            f"<a href=\"{html.escape(source_url)}\">posted minutes</a> for the full record and exact wording.</p>"
        )
    else:
        focus_items = _agenda_focus_items(extraction)
        headline = _preview_headline(body_name, meeting_date, focus_items)
        dek = _preview_dek(body_name, meeting_date, meeting_time, location, focus_items)
        if focus_items:
            focus_block = _focus_list_block(focus_items, "What matters most on the agenda")
            summary = _sentence_from_phrases(
                "The posted agenda centers on",
                _summary_phrase_list([str(item["text"]) for item in focus_items]),
            ) or dek
        else:
            summary = _sentence_from_phrases(
                "The posted agenda includes",
                _summary_phrase_list(_agenda_highlights(extraction)),
            ) or dek
        intro = _preview_intro(body_name, meeting_date, meeting_time, location, focus_items)
        agenda_block, explainers = _agenda_highlight_blocks(extraction)
        if not agenda_block:
            generic_items = _generic_agenda_lines(extraction)
            if generic_items:
                agenda_block = "<h3>What is on the agenda</h3><ul>{}</ul>".format(
                    "".join("<li>{}</li>".format(html.escape(item)) for item in generic_items)
                )
                if summary == dek:
                    summary = _sentence_from_phrases("The posted agenda includes", generic_items[:2]) or dek
        remote_block = _remote_access_block(extraction)
        kicker = (
            f"<p>The public can review the full <a href=\"{html.escape(source_url)}\">posted agenda</a> "
            f"for the complete list of items, attachments, and procedural details.</p>"
        )

    summary_lines = _choose_summary_lines(extraction["body_text"])
    if focus_items:
        middle = ""
    elif story_type == "meeting_preview" and agenda_block:
        middle = ""
    elif summary_lines:
        middle = "".join(
            f"<p>{html.escape(line)}</p>"
            for line in summary_lines
        )
        if story_type == "minutes_recap" or not summary:
            summary = " ".join(summary_lines[:2])
    else:
        middle = (
            f"<p>The source document was available, but this automated pass did not extract a strong meeting summary. "
            f"Readers should refer directly to the town's {html.escape(source_label)}.</p>"
        )
        if story_type == "meeting_preview":
            summary = dek
        else:
            summary = f"Wareham posted {source_label} for the {body_name} meeting dated {meeting_date}."

    body_html = intro + remote_block + focus_block + agenda_block + middle + kicker
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
    stories_updated = 0
    events_created = 0
    events_updated = 0

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
            LEFT JOIN (
                SELECT de1.*
                FROM document_extractions de1
                INNER JOIN (
                    SELECT document_id, MAX(id) AS max_id
                    FROM document_extractions
                    GROUP BY document_id
                ) latest_extraction ON latest_extraction.max_id = de1.id
            ) de ON de.document_id = ma.document_id
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
        if existing_story:
            stories_updated += 1
        else:
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
                events_updated += 1
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

    return PublishedCounts(
        stories_published=stories_published,
        stories_updated=stories_updated,
        events_created=events_created,
        events_updated=events_updated,
    )
