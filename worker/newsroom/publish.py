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
    ("town meeting articles", 70, "town_meeting"),
    ("budget article", 55, "budget"),
    ("fy 27 budget", 60, "budget"),
    ("school budget", 46, "budget"),
    ("enterprise budget", 46, "budget"),
    ("emergency medical services budget", 46, "budget"),
    ("course update", 24, "policy"),
    ("winter schedule", 22, "policy"),
    ("golf cart fleet", 28, "infrastructure"),
    ("tractor situation", 26, "infrastructure"),
    ("equipment status", 18, "infrastructure"),
    ("proposed alterations", 32, "land_use"),
    ("historic district expansion", 26, "policy"),
    ("fearing tavern", 34, "land_use"),
    ("restoration", 22, "land_use"),
    ("mcc fy26 grant decision report", 62, "policy"),
    ("community input survey", 48, "policy"),
    ("grant recipient reception", 28, "policy"),
    ("town owned property", 52, "land_use"),
    ("affordable housing", 34, "policy"),
    ("801 main street", 42, "budget"),
    ("committed funds", 30, "budget"),
    ("final warrant articles", 58, "town_meeting"),
    ("draft zoning bylaw recodification memorandum", 60, "policy"),
    ("policy issues identified", 44, "policy"),
    ("rescind article 40", 62, "policy"),
    ("merge with open space", 46, "policy"),
    ("trail improvements", 34, "infrastructure"),
    ("new web site", 24, "policy"),
    ("articles for town meeting", 58, "town_meeting"),
    ("sewer bill insert", 34, "policy"),
    ("back of sewer bills information", 28, "policy"),
    ("dissolve the cmwrrdd", 72, "policy"),
    ("selection of attorney", 42, "appointment"),
    ("environmental pollution policy", 38, "policy"),
    ("trex project", 64, "infrastructure"),
    ("paint and swap", 44, "policy"),
    ("shed purchase", 36, "contract"),
    ("volunteer status", 32, "policy"),
    ("metal collection", 28, "policy"),
    ("early education learning center", 20, "land_use"),
    ("early education head start", 20, "land_use"),
    ("school choice", 82, "policy"),
    ("policy review", 76, "policy"),
    ("policies to be reviewed", 76, "policy"),
    ("district calendar", 52, "policy"),
    ("course selection", 48, "policy"),
    ("course of studies", 48, "policy"),
    ("mid-cycle review of goals", 42, "policy"),
    ("substitute pay", 36, "policy"),
    ("class trip", 34, "formal_action"),
    ("security cameras in schools", 40, "policy"),
    ("security visitors in school buildings", 40, "policy"),
    ("emergency closings", 34, "policy"),
    ("emergency health procedures", 34, "policy"),
    ("emergency plans", 34, "policy"),
    ("bullying prevention", 36, "policy"),
    ("bus transportation", 34, "policy"),
    ("transportation emergency", 32, "policy"),
    ("bill and payroll warrants", 34, "formal_action"),
    ("payroll and bill warrants", 34, "formal_action"),
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

SHORT_MEANINGFUL_PHRASES = {
    "next steps",
}

PUBLISHER_RENDER_VERSION = "2026-03-19-render-v6-hearings-style"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:180] or "story"


def _story_slug(connection: Connection, meeting: Dict[str, object], story_type: str, existing_story_id: Optional[int] = None) -> str:
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
            row = cursor.fetchone()
            if not row or (existing_story_id and int(row["id"]) == int(existing_story_id)):
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


def _oxford_join(items: List[str]) -> str:
    cleaned = [" ".join(str(item or "").split()) for item in items if " ".join(str(item or "").split())]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return "{} and {}".format(cleaned[0], cleaned[1])
    return "{}, and {}".format(", ".join(cleaned[:-1]), cleaned[-1])


def _story_content_signature(headline: str, dek: str, summary: str, body_text: str) -> str:
    digest = hashlib.sha256()
    digest.update(PUBLISHER_RENDER_VERSION.encode("utf-8"))
    digest.update(b"\n")
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


def _normalized_change_items(items: List[str]) -> List[str]:
    normalized = []
    seen = set()
    for item in items:
        cleaned = _clean_agenda_display_item(item)
        if not cleaned or _is_low_value_agenda_line(cleaned):
            continue
        label = _change_item_label(cleaned)
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def _story_basis_json(
    source_item: Dict[str, object],
    extraction: Dict[str, object],
    artifact_type: str,
    artifact_posted_at: Optional[str],
    is_amended: bool,
    content_signature: str,
) -> str:
    highlights = _normalized_change_items(_agenda_highlights(extraction))
    return json.dumps(
        {
            "source_item_id": source_item["source_item_id"],
            "extraction_id": extraction["id"],
            "source_url": source_item["canonical_url"],
            "artifact_type": artifact_type,
            "artifact_posted_at": artifact_posted_at,
            "is_amended": bool(is_amended),
            "render_version": PUBLISHER_RENDER_VERSION,
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
    previous_clean = _normalized_change_items([" ".join(str(item).split()) for item in previous_highlights if " ".join(str(item).split())])
    current_clean = _normalized_change_items(_agenda_highlights(extraction))

    if not previous_clean and not current_clean:
        return ""

    previous_label_list = [_change_item_label(item).lower() for item in previous_clean]
    current_label_list = [_change_item_label(item).lower() for item in current_clean]
    previous_labels = set(previous_label_list)
    current_labels = set(current_label_list)
    added = [item for item in current_clean if _change_item_label(item).lower() not in previous_labels]
    removed = [item for item in previous_clean if _change_item_label(item).lower() not in current_labels]

    change_bits = []
    if added:
        change_bits.append("New agenda items include {}".format("; ".join(_change_item_label(item) for item in added[:2])))
    if removed:
        change_bits.append("Items no longer listed include {}".format("; ".join(_change_item_label(item) for item in removed[:2])))
    if not change_bits and current_label_list != previous_label_list:
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
    normalized = " ".join(str(text or "").replace("\xa0", " ").split())
    repairs = [
        (r"\bClas s\b", "Class"),
        (r"\bSc hool\b", "School"),
        (r"\bDiscrimin atory\b", "Discriminatory"),
        (r"\bH arassment\b", "Harassment"),
        (r"\bSele ction\b", "Selection"),
        (r"\bA pprove\b", "Approve"),
        (r"\bFinanc ia l\b", "Financial"),
        (r"\bL icenses\b", "Licenses"),
        (r"\bu pdate\b", "update"),
        (r"\bMid\s*-\s*Cycle\b", "Mid-Cycle"),
        (r"\b5\s*-\s*year\b", "5-year"),
        (r"\bWarrant articles\s+to\b", "Warrant articles to"),
        (r"\bar\s*\?\s*cles\b", "articles"),
        (r"\bmee\s*\?\s*ng\b", "meeting"),
        (r"\s+[?¿]\s*ANR\s*[?¿]\s+", " ANR "),
        (r"\bR eview\b", "Review"),
        (r"\bPurchase S\b", "Purchases"),
        (r"\bVII I\b", "VIII"),
        (r"\bSECRETARY\s[’']\sS\b", "Secretary's"),
        (r"\b202\s+5\b", "2025"),
        (r"\b202\s+6\b", "2026"),
        (r"\bLICENSES AND PERMITS\b", "Licenses and Permits"),
    ]
    for pattern, replacement in repairs:
        normalized = re.sub(pattern, replacement, normalized)
    normalized = re.sub(r"\s*-\s*", " - ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _clean_agenda_display_item(text: str) -> str:
    cleaned = _normalize_item_text(text).replace("\uf0b7", " - ")
    if not cleaned:
        return ""
    cleaned = re.sub(r"^\((Reappointment)\):\s*", r"\1: ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^APPOINTMENTS:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\s*[-\u2013\u2014]?\s*Any other (?:new )?business not (?:reasonably )?antici\w+.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s+[A-Z][A-Za-z.\s]+\s*,?\s*Chair Wareham Historical Commission.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bWCTV Bldg\b", "WCTV Building", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bMain St\.?(?=\s|\)|,|$)", "Main Street", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bHistoric District Expansion-Study Committee\b", "Historic District Expansion Study", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bOld Company Store Property\b", "Old Company Store property", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bProposed alterations\b", "proposed alterations", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^Wareham Historical Society:\s*Fearing Tavern$", "Wareham Historical Society: Fearing Tavern restoration", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r":\s*[\-\u2013\u2014]\s*(As-Built Sign Off)\b", r" - \1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bTropical Smoothie-(\d)", r"Tropical Smoothie - \1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bZone\s*-\s*(\d{2}-\d{2})\b", r"Zone-\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+any new business.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+next meeting date.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+sandy slavin,\s*chair.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^AGENDA\s*\(Amended\)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^Secretary['’]s Report\s*-\s*Minutes of the Meeting of .+$", "Minutes approval", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^REVIEW AND DISCUSSION OF JANUARY MINUTES: VOTE TO ACCEPT MINUTES OF JANUARY 2026$", "Minutes approval", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^STATUS AND UPDATE ON TREX PROJECT:\s*", "Trex project: ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"RECENT AND CLOSURES", "recent closures", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"SNOW REMOVAL PROBLEMS AND SAFETY", "snow removal problems and safety", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^LOCATION OF [\"“”']*GRANTED[\"“”']* PAINT AND SWAP SHEDS$", "Paint and swap shed locations", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^UPCOMING SHED PURCHASES?$", "Upcoming shed purchases", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^SIZE,\s*REQUIREMENTS AND COST:\s*UPCOMING GRANT APPLICATION.*$", "Upcoming grant application size, requirements, and cost", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^RECOGNITION BY SELECT BOARD VIII \.\s*VOLUNTEER STATUS AND CONCERNS$", "Select Board recognition and volunteer status concerns", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")


def _is_low_value_agenda_line(text: str) -> bool:
    lowered = _clean_agenda_display_item(text).lower().strip(" .;:-")
    if not lowered:
        return True
    if re.search(r"\bappoint\s+(him|her|them)\b", lowered, flags=re.IGNORECASE) and not re.search(
        r"\b(board of appeals|board|committee|commission|authority|council|trust|trustees)\b",
        lowered,
        flags=re.IGNORECASE,
    ):
        return True
    if re.match(r"^(?:[ivxlcdm]+\.\s*)?(?:continued\s+)?public hearings?$", lowered, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\s*,\s*\d{4}", lowered):
        return True
    if re.match(r"^\d{1,2}:\d{2}\s*(a\.m\.|p\.m\.|am|pm)\b", lowered, flags=re.IGNORECASE):
        return True
    if re.match(r"^\d{1,2}:\d{2}\s*(a\.m\.|p\.m\.|am|pm)\b", lowered, flags=re.IGNORECASE):
        return True
    low_value_prefixes = (
        "agenda",
        "approve the ",
        "approval of prior meeting minutes",
        "approval of meeting minutes",
        "minutes approval",
        "approve minutes",
        "review and approve minutes",
        "any other business",
        "any other new business",
        "next meeting",
        "adjourn",
        "public hearings",
        "continued public hearings",
    )
    return lowered.startswith(low_value_prefixes)


def _looks_truncated(text: str) -> bool:
    normalized = _normalize_item_text(text)
    if normalized.lower() in SHORT_MEANINGFUL_PHRASES:
        return False
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
        r"^(new|old)\s+business:\s*",
        r"^secretary['’]s report\s*-\s*",
        r"^status and update on\s+",
        r"^read and review\s+",
        r"^review and discussion of\s+",
        r"^location of\s+",
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


def _normalize_appointment_target(text: str) -> str:
    target = _normalize_item_text(text)
    if not target:
        return ""
    target = re.sub(r"^(the\s+)?wareham\s+", "", target, flags=re.IGNORECASE)
    target = re.sub(r"^(the\s+)", "", target, flags=re.IGNORECASE)
    target = re.sub(
        r"\s+(?:and\s+possible(?:ly)?\s+vote.*|for\s+a\s+term.*|term\s+to\s+expire.*|effective\s+.*|with\s+a\s+term.*)$",
        "",
        target,
        flags=re.IGNORECASE,
    )
    target = re.sub(r"\s+", " ", target).strip(" ,.;:-")
    if not target:
        return ""
    lowered = target.lower()
    if lowered in ("member", "committee", "board", "commission", "authority", "council", "trust"):
        return ""
    return target.title()


def _normalize_candidate_name(text: str) -> str:
    name = _normalize_item_text(text)
    if not name:
        return ""
    name = re.sub(r"\s+", " ", name).strip(" ,.;:-")
    return name.title()


def _appointment_sentence(target: str, candidate: str = "", kind: str = "") -> str:
    if candidate and kind == "application":
        return "Members are expected to consider {} application to the {}.".format(
            _possessive_name(candidate),
            target,
        )
    if candidate:
        return "Members are expected to consider appointing {} to the {}.".format(candidate, target)
    return "Members are expected to consider an appointment to the {}.".format(target)


def _parse_appointment_item(text: str) -> Dict[str, str]:
    cleaned = _normalize_item_text(_strip_agenda_lead_in(text))
    if not cleaned:
        return {}

    lowered = cleaned.lower()
    if not any(token in lowered for token in ("appoint", "appointment", "application of", "reappoint", "reappointment", "interview")):
        return {}

    if "appointments/reappointments/interviews" in lowered or "appointments reappointments interviews" in lowered:
        return {
            "summary": "board and committee appointments",
            "headline": "Board and Committee Appointments",
            "sentence": "Members are expected to review board and committee appointments.",
        }

    target_patterns = [
        r"application of\s+(?P<candidate>[A-Za-z][A-Za-z.'-]+(?:\s+[A-Za-z][A-Za-z.'-]+)+?)\s+as\s+(?:an?\s+)?(?:member|alternate member|associate member|representative)\s+of\s+(?:the\s+)?(?P<target>[A-Za-z][A-Za-z0-9&'/ .-]+?(?:board of appeals|board|committee|commission|authority|council|trust|trustees))\b",
        r"application of\s+(?P<candidate>[A-Za-z][A-Za-z.'-]+(?:\s+[A-Za-z][A-Za-z.'-]+)+?)\s+to\s+(?:the\s+)?(?P<target>[A-Za-z][A-Za-z0-9&'/ .-]+?(?:board of appeals|board|committee|commission|authority|council|trust|trustees))\b",
        r"(?:appoint|reappoint)\s+(?P<candidate>[A-Za-z][A-Za-z.'-]+(?:\s+[A-Za-z][A-Za-z.'-]+)+?)\s+to\s+(?:the\s+)?(?P<target>[A-Za-z][A-Za-z0-9&'/ .-]+?(?:board of appeals|board|committee|commission|authority|council|trust|trustees))\b",
        r"to\s+fill\s+(?:one\s+)?position\s+for\s+(?:the\s+)?(?P<target>[A-Za-z][A-Za-z0-9&'/ .-]+?(?:board of appeals|board|committee|commission|authority|council|trust|trustees))\b",
        r"representative\s+to\s+(?:the\s+)?(?P<target>[A-Za-z][A-Za-z0-9&'/ .-]+?(?:board of appeals|board|committee|commission|authority|council|trust|trustees))\b",
    ]

    for pattern in target_patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if not match:
            continue
        target = _normalize_appointment_target(match.groupdict().get("target") or "")
        candidate = _normalize_candidate_name(match.groupdict().get("candidate") or "")
        if not target:
            continue
        kind = "application" if "application of" in lowered else "appointment"
        return {
            "target": target,
            "candidate": candidate,
            "summary": "{} appointment".format(target),
            "headline": "{} Appointment".format(target),
            "sentence": _appointment_sentence(target, candidate, kind),
        }

    if "planning board" in lowered and "appoint" in lowered:
        return {
            "target": "Planning Board",
            "summary": "planning board appointment",
            "headline": "Planning Board Appointment",
            "sentence": "Members are expected to consider a Planning Board appointment.",
        }
    if "capital planning" in lowered and ("appoint" in lowered or "member" in lowered):
        return {
            "target": "Capital Planning Committee",
            "summary": "capital planning committee appointment",
            "headline": "Capital Planning Committee Appointment",
            "sentence": "Members are expected to consider an appointment to the Capital Planning Committee.",
        }
    if "finance committee" in lowered and ("appoint" in lowered or "application of" in lowered):
        return {
            "target": "Finance Committee",
            "summary": "finance committee appointment",
            "headline": "Finance Committee Appointment",
            "sentence": "Members are expected to consider an appointment to the Finance Committee.",
        }

    return {}


def _headline_phrase(text: str) -> str:
    cleaned = _strip_agenda_lead_in(text)
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    appointment = _parse_appointment_item(cleaned)
    if appointment.get("headline"):
        return str(appointment["headline"])
    if "capital planning member appointment" in lowered:
        return "Capital Planning Committee Appointment"
    if "public hearings" in lowered and len(cleaned) <= 40:
        return ""
    if re.match(r"^[ivxlcdm]+\.\s*public hearings?\.?$", lowered, flags=re.IGNORECASE):
        return ""
    if lowered.strip(" .;:-\u2013\u2014") == "discussion and possible vote":
        return ""
    zoning_summary = _zoning_case_summary(cleaned)
    if zoning_summary.get("headline"):
        return str(zoning_summary["headline"])
    if "vote on town meeting articles" in lowered:
        return "Town Meeting Articles Vote"
    if "fy 27 budget" in lowered or "budget article" in lowered:
        return "Town Meeting Budget Articles"
    if "oml violation" in lowered:
        return "OML Violation Response"
    if "department heads" in lowered and "budget" in lowered:
        return "FY2027 Budget Presentations"
    if "parkwood beach" in lowered:
        return "Parkwood Beach"
    if "truck restrictions" in lowered and "plymouth ave" in lowered:
        return "Plymouth Avenue Truck Restrictions"
    if "littleton housing project" in lowered:
        return "Littleton Housing Project Addresses"
    if "relocate bus stop" in lowered:
        return "Indian Neck Road Bus Stop Relocation"
    if "off site parking" in lowered:
        return "Off-Site Parking Petition"
    if "maple springs road" in lowered and "anr" in lowered:
        return "Maple Springs Road ANR"
    if "238 & 240 sandwich road" in lowered and "site plan review" in lowered:
        return "Sandwich Road Site Plan Review"
    if ("3031 cran hwy" in lowered or "3031 cranberry hwy" in lowered) and "site plan review" in lowered:
        return "3031 Cran Hwy. Site Plan Review"
    if "citizen petition" in lowered and "zoning bylaw article 9" in lowered:
        return "Zoning Bylaw Citizen Petition"
    if "comcast draft renewal license" in lowered:
        return "Comcast Draft Renewal License"
    if "discussion with cable attorney" in lowered:
        return "Cable Counsel Update"
    if "fy 27 capital plan" in lowered or "fy27 capital plan" in lowered:
        return "FY2027 Capital Plan"
    if "community events reconfiguration" in lowered:
        return "Community Events Reconfiguration Bylaw"
    if "purchase, exchange, lease or value of real property" in lowered:
        return "Potential Real Estate Transaction"
    if "ridecircuit" in lowered:
        return "Ride Circuit Presentation"
    if "storefront renovation grant program" in lowered:
        return "Storefront Renovation Grant Program"
    if "downtown dollars program" in lowered:
        return "Downtown Dollars Program"
    if "redwood phase 3 window replacement" in lowered:
        return "Redwood Phase 3 Window Project"
    if "high leverage asset preservation program" in lowered or "hilap" in lowered:
        return "HILAP Funding Application"
    if "bulletin board" in lowered and "public display policy" in lowered:
        return "Public Display Policy"
    if "memorial day" in lowered and "veterans day" in lowered:
        return "Memorial Day and Veterans Day Planning"
    if "state of emergency" in lowered:
        return "Emergency Declaration Authority"
    if "appointments/reappointments/interviews" in lowered or "appointments reappointments interviews" in lowered:
        return "Board and Committee Appointments"
    if "interview, discussion and possible vote to appoint" in lowered:
        return "Board and Committee Appointments"
    if "representative to the capital planning committee" in lowered:
        return "Capital Planning Appointment"
    if "to fill one position for the wareham finance committee" in lowered:
        return "New Member Appointment"
    if "spring town meeting articles" in lowered and "grant agreements" in lowered:
        return "Spring Town Meeting Funding Articles"
    if (
        "town meeting article" in lowered
        and any(token in lowered for token in ("grant agreement", "cranberry manor", "beaverdam", "sawyer property", "little harbor golf"))
    ):
        return "Spring Town Meeting Funding Articles"
    if "include 2026 annual spring town meeting articles" in lowered or "spring town meeting articles" in lowered:
        return "Spring Town Meeting Articles"
    if "move" in lowered and "october town meeting" in lowered:
        return "Town Meeting Timing Debate"
    if "contracts" in lowered and "discussion" in lowered and "vote" in lowered:
        return "Contract Votes"
    if "acceptance of meeting minutes" in lowered:
        return "Meeting Minutes Approval"
    if "fy2026 budget" in lowered or ("fee accountant" in lowered and "budget" in lowered):
        return "FY2026 Budget Review"
    if "planning director" in lowered and "amend existing contracts" in lowered:
        return "Planning Director Contract Authority"
    if "boston red sox official 2026 yearbook" in lowered:
        return "Red Sox Yearbook Advertising"
    if "transfer of recording/transcribing minutes" in lowered:
        return "Minutes and Agenda Clerk Transfer"
    if "wpcf director report" in lowered:
        return "WPCF Director Report"
    if "sewer commission business" in lowered:
        return "Sewer Commission Business"
    if "friends of the wareham council on aging" in lowered and "donation" in lowered:
        return "Council on Aging Donation"
    if "grant agreement" in lowered:
        return "Existing Grant Agreements"
    if "accept a donation" in lowered and "council on aging" in lowered:
        return "Council on Aging Donation"
    if "aarp friendly community" in lowered:
        return "AARP Friendly Community Update"
    if "status of new applicants" in lowered:
        return "New Applicant Review"
    if "open meeting law" in lowered:
        return "Open Meeting Law Discussion"
    if "waterline update" in lowered:
        return "Waterline Update"
    if "loan forgiveness" in lowered and "clean water trust" in lowered:
        return "Clean Water Trust Loan Forgiveness"
    if "capital stabilization fund" in lowered:
        return "Capital Stabilization Transfer"
    if "review and compare fy2025 final budgets" in lowered:
        return "FY2026 Budget Review"
    if "licenses, markers and monuments" in lowered:
        return "Licenses, Markers, and Monuments"
    if "cemetery grasses purchase" in lowered:
        return "Cemetery Grass Purchase"
    if "executive director" in lowered and "cd" in lowered and "rate" in lowered:
        return "CD Rate Review"
    if "dissolution of current committee" in lowered:
        return "Bylaw Committee Reorganization"
    if "interview and possible vote to appoint" in lowered or "consider application of" in lowered:
        return "Board Appointments"
    if "licenses and permits" in lowered:
        return "Licenses and Permits"
    if "spring special town meeting warrant" in lowered:
        return "Spring Special Town Meeting Articles"
    if "scheduling of february public hearing" in lowered:
        return "Bylaw Hearing Schedule"
    if "public hearing on by-law changes" in lowered or "possible public hearing on tuesday" in lowered:
        return "Bylaw Hearing Schedule"
    if "7th member" in lowered and ("capital planning" in lowered or "carey" in lowered):
        return "Capital Planning Member Appointment"
    if "updated 5 year capital plan" in lowered or "updated 5-year capital plan" in lowered:
        return "Updated Five-Year Capital Plan"
    if "impact on capital plan" in lowered and "approved" in lowered:
        return "Capital Plan Impacts"
    if "licenses" in lowered and "markers" in lowered and "monuments" in lowered:
        return "Licenses, Markers, and Monuments"
    if "application of brenda eckstrom" in lowered or "application of bernard pigeon" in lowered:
        return "New Member Appointment"
    if "comprehensive wastewater management plan" in lowered or "cwmp" in lowered:
        return "Comprehensive Wastewater Management Plan"
    if "policies to be reviewed" in lowered or "policy review" in lowered:
        return "Policy Review"
    if "district calendar" in lowered:
        return "District Calendar 2026-2027"
    if "course selection" in lowered:
        return "High School Course Selection"
    if "course of studies" in lowered:
        return "Course of Studies Changes"
    if "mid-cycle review of goals" in lowered:
        return "Mid-Cycle Review of Goals"
    if "substitute pay" in lowered:
        return "Substitute Pay Discussion"
    if "class trip" in lowered:
        return "Class of 2026 Class Trip"
    if "security cameras in schools" in lowered or "security visitors in school buildings" in lowered:
        return "School Safety Policies"
    if "emergency closings" in lowered or "emergency health procedures" in lowered or "emergency plans" in lowered:
        return "Emergency Policies"
    if "bus transportation" in lowered or "transportation emergency" in lowered:
        return "Transportation Policies"
    if "bill and payroll warrants" in lowered or "payroll and bill warrants" in lowered:
        return "Bill and Payroll Warrants"
    if "appoint town counsel" in lowered:
        return "Town Counsel Appointment"
    if "cdbg fy26 grant" in lowered:
        return "CDBG FY26 Grant Application"
    if "senior tax work-off program" in lowered:
        return "Senior Tax Work-off Program"
    if "municipal maintenance" in lowered and "abatement" in lowered:
        return "FY2026 Curbside Abatements"
    if "open space and recreation plan" in lowered:
        return "Open Space and Recreation Plan"
    if "pour farm tavern" in lowered and "entertainment license" in lowered:
        return "Pour Farm Tavern Entertainment License"
    if "proposed alterations" in lowered and "main street" in lowered:
        return "59 Main Street Alterations"
    if "historic district expansion" in lowered:
        return "Historic District Expansion Study"
    if "fearing tavern" in lowered:
        return "Fearing Tavern Restoration"
    if "mcc fy26 grant decision report" in lowered:
        return "FY2026 Grant Decision Report"
    if "town owned property" in lowered and "affordable housing" in lowered:
        return "Town-Owned Property for Affordable Housing"
    if "what cpa funds" in lowered or ("801 main street" in lowered and "funding" in lowered):
        return "WHAT/CPA Funding"
    if "budget update" in lowered and "sandy" in lowered:
        return "Budget Update"
    if "mid-cycle review of goals" in lowered or "mid cycle review of goals" in lowered:
        return "Mid-Cycle Review of Goals"
    if "the superintendent 8:00 p.m." in lowered and "mid" in lowered:
        return "Mid-Cycle Review of Goals"
    if "801 main street" in lowered and "committed funds" in lowered:
        return "801 Main Street Funding Status"
    if "final warrant articles" in lowered:
        return "Final Warrant Articles"
    if "draft zoning bylaw recodification memorandum" in lowered:
        return "Zoning Bylaw Recodification Issues"
    if "policy issues identified in draft zoning" in lowered:
        return "Zoning Bylaw Policy Issues"
    if "rescind article 40" in lowered:
        return "Rescinding Article 40"
    if "review warrant articles to be filed with select board" in lowered:
        return "Warrant Articles for Select Board"
    if "list of deletions" in lowered and "list of additions" in lowered:
        return "Town Bylaw Additions and Deletions"
    if "earth removal regulations" in lowered:
        return "Earth Removal Regulations"
    if "5-year capital plan" in lowered:
        return "Five-Year Capital Plan"
    if "review and approved 5" in lowered and "capital plan" in lowered:
        return "Five-Year Capital Plan"
    if "capital items" in lowered and "fall town meeting" in lowered:
        return "Fall Town Meeting Capital Items"
    if "merge with open space" in lowered:
        return "Open Space Merger Recommendation"
    if "trail improvements" in lowered:
        return "Trail Improvements"
    if "new web site" in lowered:
        return "Website Corrections"
    if "articles for town meeting" in lowered:
        return "Town Meeting Articles"
    if "sewer bill insert" in lowered:
        return "Sewer Bill Insert"
    if "dissolve the cmwrrdd" in lowered:
        return "Dissolving the CMWRRDD"
    if "selection of attorney" in lowered:
        return "Attorney Selection"
    if "monthly financial report" in lowered:
        return "Monthly Financial Report"
    if "community input survey" in lowered:
        return "Community Input Survey"
    if "grant recipient reception" in lowered:
        return "Grant Recipient Reception Plans"
    if "trex project" in lowered:
        return "Trex Project Update"
    if "paint and swap shed" in lowered:
        return "Paint and Swap Shed Locations"
    if "upcoming shed purchases" in lowered:
        return "Shed Purchases"
    if "volunteer status" in lowered:
        return "Volunteer Status Concerns"
    if "early education learning center" in lowered:
        return "Early Education Learning Center"
    if "early education head start" in lowered:
        return "Early Education Head Start"
    if "course update" in lowered:
        return "Course Update"
    if "golf cart fleet" in lowered:
        return "Golf Cart Fleet Needs"
    if "tractor situation" in lowered:
        return "Tractor Situation"
    if "bryant farm management plan" in lowered:
        return "Bryant Farm Management Plan"
    if "merge open space and minot forest committees" in lowered:
        return "Open Space-Minot Forest Committee Merger"
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
    if "site plan review" in lowered or "policy review" in lowered:
        return "to Review"
    if "violation" in lowered:
        return "to Discuss"
    if "status and update" in lowered or "future of the committee" in lowered:
        return "to Discuss"
    if "discussion" in lowered:
        return "to Discuss"
    if "consideration" in lowered or "future of the committee" in lowered or "next steps" in lowered:
        return "to Discuss"
    if "presentation" in lowered:
        return "to Review"
    if "acceptance" in lowered:
        return "to Consider"
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


def _zoning_case_summary(text: str) -> Dict[str, str]:
    cleaned = _normalize_item_text(text)
    if not cleaned:
        return {}
    cleaned = cleaned.replace("\u2013", " - ").replace("\u2014", " - ")

    lowered = cleaned.lower()
    if not any(
        token in lowered
        for token in (
            "special permit",
            "variance",
            "site plan review",
            "comprehensive permit",
            "minor modification",
            "record correction",
            "appeal",
            "as-built sign off",
            "sign off",
        )
    ):
        return {}

    core = re.sub(r"^\d{2}-\d{2}\s*/?\s*", "", cleaned)
    core = re.sub(r"\bzone-\d{2}-\d{2}\b", "", core, flags=re.IGNORECASE)
    core = re.sub(r"\s+", " ", core).strip(" ,.;:-")

    action_patterns = [
        (r"\bcomprehensive permit\b", "Comprehensive Permit", "comprehensive permit request"),
        (r"\bsite plan review\b", "Site Plan Review", "site plan review"),
        (r"\bminor modification\b", "Minor Modification", "minor modification request"),
        (r"\brecord correction\b", "Record Correction", "record correction request"),
        (r"\bappeal\b", "Appeal", "appeal"),
        (r"\bas-built sign off\b", "As-Built Sign Off", "as-built sign-off request"),
        (r"\bspecial permit and/or a variance\b", "Permit Request", "special permit and variance request"),
        (r"\bspecial permit and a variance\b", "Permit Request", "special permit and variance request"),
        (r"\bspecial permit or variance\b", "Permit Request", "special permit or variance request"),
        (r"\bspecial permit / variance\(s\)\b", "Permit Request", "special permit and variance request"),
        (r"\bvariance\(s\)\b", "Variance Request", "variance request"),
        (r"\bvariance\b", "Variance Request", "variance request"),
        (r"\bspecial permit\b", "Special Permit", "special permit request"),
    ]

    match_obj = None
    action_title = ""
    action_phrase = ""
    for pattern, title, phrase in action_patterns:
        match = re.search(pattern, core, flags=re.IGNORECASE)
        if match:
            match_obj = match
            action_title = title
            action_phrase = phrase
            break

    if not match_obj:
        return {}

    subject = core[: match_obj.start()].strip(" ,.;:-/")
    tail = core[match_obj.end() :].strip(" ,.;:-/")
    tail = re.sub(
        r"^(?:/|and/or)?\s*(?:special permit|site plan review|spr|sp|variance(?:\(s\))?|special permit and/or a variance)\s*[-:/]?\s*",
        "",
        tail,
        flags=re.IGNORECASE,
    )
    subject = re.sub(r"^[^A-Za-z0-9]+", "", subject)
    tail = re.sub(r"^[^A-Za-z0-9]+", "", tail)
    address = tail
    if not address:
        address_match = re.search(
            r"\b\d+[A-Za-z0-9\s.'-]+(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Highway|Hwy\.?|Lane|Ln\.?|Boulevard|Blvd\.?|Way)\b",
            core,
            flags=re.IGNORECASE,
        )
        if address_match:
            address = address_match.group(0).strip(" ,.;:-")

    if address:
        address = address.title()
    address = re.sub(r"\bAve\b\.?$", "Ave.", address, flags=re.IGNORECASE)
    address = re.sub(r"\bBlvd\b\.?$", "Blvd.", address, flags=re.IGNORECASE)
    address = re.sub(r"\bHwy\b\.?$", "Hwy.", address, flags=re.IGNORECASE)

    headline = ""
    summary = ""
    sentence = ""
    sentence_phrase = action_phrase
    if action_phrase == "site plan review":
        sentence_phrase = "site plan proposal"
    elif action_phrase == "special permit request":
        sentence_phrase = "special permit request"
    elif action_phrase == "special permit and variance request":
        sentence_phrase = "special permit and variance request"
    elif action_phrase == "special permit or variance request":
        sentence_phrase = "special permit or variance request"
    if address:
        headline = "{} {}".format(address, action_title)
        summary = "{} at {}".format(action_phrase, address)
        sentence = "The board is set to review {} at {}.".format(_with_article(sentence_phrase), address)
    elif subject:
        headline = "{} {}".format(subject, action_title)
        summary = "{} involving {}".format(action_phrase, subject)
        sentence = "The board is set to review {} involving {}.".format(_with_article(sentence_phrase), subject)

    return {
        "headline": headline.strip(" ,.;:-"),
        "summary": summary.strip(" ,.;:-"),
        "sentence": sentence.strip(" ,.;:-"),
    }


def _normalize_focus_phrase(text: str) -> str:
    cleaned = _strip_agenda_lead_in(text)
    if not cleaned:
        return ""

    lowered = cleaned.lower()
    appointment = _parse_appointment_item(cleaned)
    if appointment.get("summary"):
        return str(appointment["summary"])
    if "capital planning member appointment" in lowered:
        return "capital planning committee appointment"
    if "public hearings" in lowered and len(cleaned) <= 40:
        return ""
    if re.match(r"^[ivxlcdm]+\.\s*public hearings?\.?$", lowered, flags=re.IGNORECASE):
        return ""
    if lowered.strip(" .;:-\u2013\u2014") == "discussion and possible vote":
        return ""
    if lowered.strip(" .;:-") == "variance request":
        return "variance request"
    if "maple springs road" in lowered and "anr" in lowered:
        return "Maple Springs Road ANR"
    if "238 & 240 sandwich road" in lowered and "site plan review" in lowered:
        return "Sandwich Road site plan review"
    if ("3031 cran hwy" in lowered or "3031 cranberry hwy" in lowered) and "site plan review" in lowered:
        return "3031 Cran Hwy. site plan review"
    if "citizen petition" in lowered and "zoning bylaw article 9" in lowered:
        return "zoning bylaw citizen petition"
    zoning_summary = _zoning_case_summary(cleaned)
    if zoning_summary.get("summary"):
        return str(zoning_summary["summary"])
    special_patterns = [
        (r"vote on town meeting articles", "Town Meeting articles vote"),
        (r"(fy 27 budget|budget article|school budget|enterprise budget|emergency medical services budget)", "Town Meeting budget articles"),
        (r"oml violation", "OML violation response"),
        (r"department heads.*budget", "FY2027 budget presentations"),
        (r"parkwood beach", "Parkwood Beach"),
        (r"plymouth ave.*truck restrictions", "Plymouth Avenue truck restrictions"),
        (r"littleton housing project", "Littleton Housing Project addresses"),
        (r"relocate bus stop.*indian neck road", "Indian Neck Road bus stop relocation"),
        (r"off site parking", "off-site parking petition"),
        (r"238\s*&\s*240 sandwich road.*site plan review", "Sandwich Road site plan review"),
        (r"3031 cran(?:berry)? hwy.*site plan review", "3031 Cran Hwy. site plan review"),
        (r"citizen petition.*zoning bylaw article 9", "zoning bylaw citizen petition"),
        (r"comcast draft renewal license", "Comcast draft renewal license"),
        (r"discussion with cable attorney", "cable counsel update"),
        (r"fy\s*27 capital plan|fy27 capital plan", "FY2027 capital plan"),
        (r"community events reconfiguration", "community events reconfiguration bylaw"),
        (r"purchase,\s*exchange,\s*lease or value of real property", "potential real estate transaction"),
        (r"ridecircuit", "Ride Circuit presentation"),
        (r"storefront renovation grant program", "storefront renovation grant program"),
        (r"downtown dollars program", "Downtown Dollars program"),
        (r"redwood phase 3 window replacement", "Redwood Phase 3 window project"),
        (r"high leverage asset preservation program|hilap", "HILAP funding application"),
        (r"bulletin board.*public display policy", "public display policy"),
        (r"memorial day.*veterans day", "Memorial Day and Veterans Day planning"),
        (r"state of emergency", "emergency declaration authority"),
        (r"appointments/?reappointments/?interviews", "board and committee appointments"),
        (r"interview,\s*discussion and possible vote to appoint", "board and committee appointments"),
        (r"representative to the capital planning committee", "capital planning committee appointment"),
        (r"to fill one position for the wareham finance committee", "new member appointment"),
        (r"spring town meeting articles.*grant agreements", "spring Town Meeting funding articles"),
        (r"town meeting article.*(grant agreement|cranberry manor|beaverdam|sawyer property|little harbor golf)", "Spring Town Meeting funding articles"),
        (r"include 2026 annual spring town meeting articles|spring town meeting articles", "Spring Town Meeting articles"),
        (r"october town meeting", "Town Meeting timing debate"),
        (r"contracts.*discussion.*vote", "contract votes"),
        (r"acceptance of meeting minutes", "meeting minutes approval"),
        (r"fy2026 budget|fee accountant.*budget", "FY2026 budget review"),
        (r"planning director.*amend existing contracts", "Planning Director contract authority"),
        (r"boston red sox official 2026 yearbook", "Red Sox Yearbook advertising"),
        (r"transfer of recording/transcribing minutes", "minutes and agenda clerk transfer"),
        (r"wpcf director report", "WPCF Director report"),
        (r"sewer commission business", "sewer commission business"),
        (r"friends of the wareham council on aging.*donation", "Council on Aging donation"),
        (r"grant agreement", "existing grant agreements"),
        (r"accept a donation.*council on aging", "Council on Aging donation"),
        (r"aarp friendly community", "AARP Friendly Community update"),
        (r"status of new applicants", "new applicant review"),
        (r"open meeting law", "open meeting law discussion"),
        (r"waterline update", "Waterline update"),
        (r"loan forgiveness.*clean water trust|clean water trust.*loan forgiveness", "Clean Water Trust loan forgiveness"),
        (r"capital stabilization fund", "capital stabilization transfer"),
        (r"review and compare fy2025 final budgets", "FY2026 budget review"),
        (r"licenses,\s*markers and monuments", "licenses, markers, and monuments"),
        (r"cemetery grasses purchase", "cemetery grass purchase"),
        (r"executive director.*cd.*rate", "CD rate review"),
        (r"dissolution of current committee", "bylaw committee reorganization"),
        (r"interview and possible vote to appoint|consider application of", "board appointments"),
        (r"licenses and permits", "licenses and permits"),
        (r"spring special town meeting warrant", "Spring Special Town Meeting articles"),
        (r"scheduling of february public hearing", "bylaw hearing schedule"),
        (r"public hearing on by-?law changes|possible public hearing on tuesday", "bylaw hearing schedule"),
        (r"7th member.*(capital planning|carey)", "Capital Planning Committee appointment"),
        (r"updated 5[\s-]*year capital plan", "Updated five-year capital plan"),
        (r"impact on capital plan.*approved", "capital plan impacts"),
        (r"licenses.*markers.*monuments", "licenses, markers, and monuments"),
        (r"application of brenda eckstrom|application of bernard pigeon", "new member appointment"),
        (r"policies to be reviewed|policy review", "policy review"),
        (r"district calendar", "district calendar vote"),
        (r"course selection", "high school course selection"),
        (r"course of studies", "course of studies changes"),
        (r"mid-cycle review of goals", "mid-cycle review of goals"),
        (r"substitute pay", "substitute pay discussion"),
        (r"class trip", "Class of 2026 class trip"),
        (r"security cameras in schools|security visitors in school buildings", "school safety policies"),
        (r"emergency closings|emergency health procedures|emergency plans", "emergency policies"),
        (r"bus transportation|transportation emergency", "transportation policies"),
        (r"bill and payroll warrants|payroll and bill warrants", "bill and payroll warrants"),
        (r"appoint town counsel", "Town Counsel appointment"),
        (r"cdbg fy26 grant", "CDBG FY26 grant application"),
        (r"senior tax work-off program", "Senior Tax Work-off Program"),
        (r"municipal maintenance.*abatement", "FY2026 curbside abatements"),
        (r"pour farm tavern.*entertainment license", "Pour Farm Tavern entertainment license"),
        (r"59 main street.*proposed alterations", "59 Main Street alterations"),
        (r"historic district expansion", "Historic District expansion study"),
        (r"fearing tavern.*restoration", "Fearing Tavern restoration"),
        (r"mcc fy26 grant decision report", "FY2026 grant decision report"),
        (r"town owned property.*affordable housing", "town-owned property for affordable housing"),
        (r"what cpa funds|801 main street.*funding", "WHAT/CPA funding"),
        (r"budget update.*sandy", "budget update"),
        (r"mid-?cycle review of goals", "Mid-Cycle Review of Goals"),
        (r"the superintendent.*mid", "Mid-Cycle Review of Goals"),
        (r"801 main street.*committed funds|committed funds.*801 main street", "801 Main Street funding status"),
        (r"final warrant articles", "final warrant articles"),
        (r"review warrant articles to be filed with select board", "warrant articles for Select Board"),
        (r"list of deletions.*list of additions", "town bylaw additions and deletions"),
        (r"earth removal regulations", "Earth Removal Regulations"),
        (r"5-year capital plan", "five-year capital plan"),
        (r"review and approved 5.*capital plan", "five-year capital plan"),
        (r"capital items.*fall town meeting", "Fall Town Meeting capital items"),
        (r"draft zoning bylaw recodification memorandum", "draft zoning bylaw recodification issues"),
        (r"policy issues identified in draft zoning", "zoning bylaw policy issues"),
        (r"rescind article 40", "rescinding Article 40"),
        (r"merge with open space", "merging with Open Space"),
        (r"trail improvements", "trail improvements"),
        (r"new web site", "website corrections"),
        (r"articles for town meeting", "Town Meeting articles"),
        (r"sewer bill insert", "sewer bill insert"),
        (r"dissolve the cmwrrdd", "dissolving the CMWRRDD"),
        (r"selection of attorney", "attorney selection"),
        (r"monthly financial report", "monthly financial report"),
        (r"community input survey", "community input survey"),
        (r"grant recipient reception", "grant recipient reception plans"),
        (r"trex project", "Trex project update"),
        (r"paint and swap shed", "paint and swap shed locations"),
        (r"upcoming shed purchases", "shed purchases"),
        (r"volunteer status", "volunteer status concerns"),
        (r"early education learning center", "Early Education Learning Center"),
        (r"early education head start", "Early Education Head Start"),
        (r"course update", "course update"),
        (r"golf cart fleet", "golf cart fleet needs"),
        (r"tractor situation", "tractor situation"),
        (r"winter schedule", "winter schedule"),
        (r"bryant farm management plan", "Bryant Farm management plan"),
        (r"merge open space and minot forest committees", "merging the Open Space and Minot Forest committees"),
        (r"future of the committee", "the committee's future"),
        (r"next steps", "next steps"),
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

    if "1b emma lane" in lowered:
        return "1B Emma Lane public hearing"

    tobacco_match = re.search(r"tobacco violations?\s+(?:for|at)\s+(.+)", cleaned, flags=re.IGNORECASE)
    if tobacco_match:
        subject = _trim_trailing_detail(tobacco_match.group(1))
        return "tobacco violations at {}".format(subject) if subject else "tobacco violations"
    trailing_tobacco_match = re.search(r"(.+?)\s+tobacco violations?$", cleaned, flags=re.IGNORECASE)
    if trailing_tobacco_match:
        subject = _trim_trailing_detail(trailing_tobacco_match.group(1))
        return "tobacco violations at {}".format(subject) if subject else "tobacco violations"

    variance_match = re.search(r"variance requests?\s+(?:for|at)\s+(.+)", cleaned, flags=re.IGNORECASE)
    if variance_match:
        subject = _trim_trailing_detail(variance_match.group(1))
        if subject.lower() == "request":
            subject = ""
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

    if normalized.count("?") >= 2:
        return True

    return False


def _is_low_value_focus_line(text: str) -> bool:
    lowered = _normalize_item_text(text).lower()
    if not lowered:
        return True
    if lowered in ("appointments", "appointment", "reappointment", "(reappointment)", "reappointments", "interviews"):
        return True
    if re.search(r"meeting\s+minutes", lowered, flags=re.IGNORECASE):
        return True
    if re.search(r"\bappoint\s+(him|her|them)\b", lowered, flags=re.IGNORECASE) and not re.search(
        r"\b(board of appeals|board|committee|commission|authority|council|trust|trustees)\b",
        lowered,
        flags=re.IGNORECASE,
    ):
        return True
    if " anr " in " {} ".format(lowered) and "?" in lowered:
        return True
    if re.match(r"^(the\s+)?\d{1,2}(?:-\d{1,2})?\.?$", lowered):
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
            "review and discussion of november minutes",
            "review and discussion of january minutes",
            "vote to accept minutes",
            "minutes approval",
            "minutes of the meeting of",
            "meeting minutes",
            "secretary's report - minutes of the meeting of",
            "secretary’s report-minutes of the meeting of",
            "approval of prior meeting minutes",
            "approve the ",
            "reorganization: nomination and vote for chair",
            "reorganization: nomination and vote for clerk",
            "call to order",
            "roll call",
            "adjournment",
            "pledge of allegiance",
            "resident's comments",
            "signing of documents approved",
            "any other business",
            "any other town business",
            "any other town or school business",
            "good news",
            "public participation",
            "announcements",
            "consent agenda",
            "liaison /initiative",
            "board’s comment",
            "board's comment",
            "town administrator’s report",
            "town administrator's report",
            "nwea report",
            "principal reports",
            "important upcoming events",
            "appointments, interviews, and reappointments",
            "public hearings",
            "continued public hearings",
            "iv. public hearings",
            "workshop - permits - certificates of compliance",
            "workshop permits certificates of compliance",
            "certificates of compliance",
            "zoning re - write presentation",
            "zoning re write presentation",
            "business unknown until the previous 48 hours",
            "election of officers",
            "motion to adjourn",
            "discussion and vote",
            "discussion & possible vote",
            "resident's comments limited to 2 minutes",
            "resident’s comments limited to 2 minutes",
            "acceptance of meeting minutes",
            "approval of january",
            "approval of february",
            "approval of december",
            "review and approval of september",
            "review and approval of october",
            "any other council of aging business",
            "please note that the committee may act",
            "unanticipated items received in the last 48 hours",
            "review and approve minutes",
            "approve minutes",
            "capital planning worksheets",
        )
    ):
        return True
    if "or special permit" in lowered and "variance request" in lowered:
        return True
    if lowered.strip(" .;:-") == "discussion and possible vote":
        return True
    return False


def _summary_phrase_list(items: List[str], limit: int = 2) -> List[str]:
    normalized_items = [_normalize_item_text(item) for item in items]
    scan_limit = max(limit, 4)
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
        if re.search(r"\b\d{1,2}:\d{2}\s*(a\.m\.|p\.m\.|am|pm)\b", phrase, flags=re.IGNORECASE):
            continue
        if phrase in seen:
            continue
        seen.add(phrase)
        phrases.append(phrase)
        if len(phrases) >= scan_limit:
            break

    generic_appointment_phrases = {"board appointments", "board and committee appointments", "new member appointment"}
    specific_appointment_targets = []
    for phrase in phrases:
        lowered_phrase = phrase.lower()
        if lowered_phrase.endswith(" appointment") and lowered_phrase not in generic_appointment_phrases:
            target = re.sub(r"\s+appointment$", "", phrase, flags=re.IGNORECASE).strip()
            if target and target not in specific_appointment_targets:
                specific_appointment_targets.append(target)

    filtered_phrases = []
    for phrase in phrases:
        lowered_phrase = phrase.lower()
        if lowered_phrase in generic_appointment_phrases and specific_appointment_targets:
            continue
        filtered_phrases.append(phrase)

    if len(specific_appointment_targets) >= 2:
        normalized_targets = []
        for target in specific_appointment_targets[:2]:
            normalized = _normalize_appointment_target(target)
            normalized_targets.append(normalized or target)
        return ["{} appointments".format(_oxford_join(normalized_targets))]
    if filtered_phrases:
        return filtered_phrases[:limit]
    return phrases


def _is_hearing_focus_text(text: str) -> bool:
    lowered = _normalize_item_text(text).lower()
    if not lowered:
        return False
    return any(
        token in lowered
        for token in (
            "public hearing",
            "special permit",
            "variance request",
            "permit request",
            "site plan review",
            "comprehensive permit",
            "safe harbor marina",
            "stormwater",
            "noi",
            "rda",
        )
    )


def _sentence_from_phrases(prefix: str, phrases: List[str]) -> str:
    if not phrases:
        return ""
    joined = _oxford_join(phrases)
    return "{} {}.".format(prefix, joined) if joined else ""


def _preview_summary(body_name: str, focus_items: List[Dict[str, object]], dek: str) -> str:
    phrases = _summary_phrase_list([str(item["text"]) for item in focus_items])
    if not phrases:
        return dek

    lowered_body = _normalize_item_text(body_name).lower()
    hearing_count = sum(1 for item in focus_items[:3] if _is_hearing_focus_text(str(item.get("text") or "")))
    if lowered_body in ("planning board", "zoning board of appeals", "conservation commission") and hearing_count >= 1:
        if lowered_body == "planning board":
            return _sentence_from_phrases("Public hearings and development reviews are expected to focus on", phrases) or dek
        return _sentence_from_phrases("Public hearings are expected to focus on", phrases) or dek
    if lowered_body == "school committee":
        return _sentence_from_phrases("The committee is expected to focus on", phrases) or dek
    if lowered_body in ("planning board", "zoning board of appeals", "finance committee"):
        return _sentence_from_phrases("The board is expected to focus on", phrases) or dek
    if lowered_body in ("conservation commission", "historical commission", "historic district commission"):
        return _sentence_from_phrases("The commission is expected to focus on", phrases) or dek
    if lowered_body.endswith("committee") or lowered_body.endswith("council"):
        return _sentence_from_phrases("The meeting is expected to focus on", phrases) or dek
    return _sentence_from_phrases("The agenda is expected to focus on", phrases) or dek


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


def _preview_headline_phrase(body_name: str, focus_items: List[Dict[str, object]]) -> str:
    phrase = _headline_focus_phrase(focus_items)
    if not phrase:
        return ""

    lowered_body = _normalize_item_text(body_name).lower()
    lowered_phrase = phrase.lower()
    first_text = _normalize_item_text(str(focus_items[0].get("text") or "")).lower() if focus_items else ""

    if lowered_body == "school committee" and lowered_phrase == "policy review":
        return "School Policy Changes"
    if lowered_body == "school committee" and lowered_phrase == "mid-cycle review of goals":
        return "Mid-Cycle Goals"
    if lowered_body == "conservation commission" and "safe harbor marina" in lowered_phrase:
        return "Safe Harbor Marina Redevelopment"
    if lowered_body == "planning board":
        if "238 & 240 sandwich road" in first_text and "site plan review" in first_text:
            return "Sandwich Road Site Plan"
        if ("3031 cran hwy" in first_text or "3031 cranberry hwy" in first_text) and "site plan review" in first_text:
            return "3031 Cran Hwy. Site Plan"
        if "citizen petition" in first_text and "zoning bylaw article 9" in first_text:
            return "Zoning Bylaw Citizen Petition"
        if "site plan review" in lowered_phrase:
            return phrase.replace("Site Plan Review", "Site Plan").strip()
    if lowered_body == "zoning board of appeals":
        zoning_summary = _zoning_case_summary(first_text)
        if zoning_summary.get("headline"):
            return str(zoning_summary["headline"])
    return phrase


def _preview_headline_action(body_name: str, focus_item_text: str, phrase: str) -> str:
    action = _headline_action(focus_item_text)

    lowered_body = _normalize_item_text(body_name).lower()
    lowered_phrase = _normalize_item_text(phrase).lower()
    review_bodies = (
        "school committee",
        "historical commission",
        "historic district commission",
        "planning board",
        "cable advisory committee",
        "bylaw review committee",
        "capital planning committee",
        "cultural council",
        "board of library trustees",
        "wareham housing authority",
        "appointing authority",
    )
    discuss_bodies = (
        "community events committee",
        "redevelopment authority",
        "council on aging",
        "wareham veterans council",
        "sewer commissioners",
        "community preservation committee",
        "select board",
        "cemetery commissioners",
        "minot forest committee",
        "open space committee",
        "affordable housing trust",
    )

    if lowered_body in review_bodies and action in ("to Meet and Consider", "to Consider"):
        return "to Review"
    if lowered_body == "little harbor golf course advisory committee":
        return "to Discuss"
    if lowered_body in discuss_bodies and action in ("to Meet and Consider", "to Consider"):
        return "to Discuss"
    if action != "to Meet and Consider":
        return action

    if any(
        token in lowered_phrase
        for token in (
            "policy",
            "plan",
            "study",
            "report",
            "budget",
            "warrant",
            "article",
            "petition",
            "restoration",
            "alterations",
            "license",
            "funding status",
            "site plan",
            "permit request",
            "insert",
        )
    ):
        return "to Review"

    if any(token in lowered_phrase for token in ("future", "update", "needs", "situation", "survey")):
        return "to Discuss"

    return action


def _headline_phrase_for_action(phrase: str, action: str) -> str:
    cleaned = phrase.strip()
    if action == "to Review":
        cleaned = re.sub(r"^Review\s+", "", cleaned, flags=re.IGNORECASE)
        if re.search(r"\bReview$", cleaned, flags=re.IGNORECASE) and cleaned.lower() not in ("policy review",):
            cleaned = re.sub(r"\s+Review$", "", cleaned, flags=re.IGNORECASE)
    elif action == "to Discuss":
        if re.search(r"\bDiscussion$", cleaned, flags=re.IGNORECASE):
            cleaned = re.sub(r"\s+Discussion$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,.;:-")


def _preview_headline(body_name: str, meeting_date: str, focus_items: List[Dict[str, object]]) -> str:
    if not focus_items:
        return f"{body_name} to Meet {meeting_date}"

    first = _preview_headline_phrase(body_name, focus_items)
    if first:
        lowered_body = _normalize_item_text(body_name).lower()
        if lowered_body == "zoning board of appeals":
            return f"{body_name} to Hear {first}"
        if lowered_body == "conservation commission" and "safe harbor marina" in first.lower():
            return f"{body_name} to Hear {first}"
        action = _preview_headline_action(body_name, str(focus_items[0]['text']), first)
        headline_phrase = _headline_phrase_for_action(first, action)
        return f"{body_name} {action} {headline_phrase}"
    return f"{body_name} to Meet {meeting_date}"


def _preview_dek(body_name: str, meeting_date: str, meeting_time: str, location: str, focus_items: List[Dict[str, object]]) -> str:
    if meeting_time and meeting_time != "at a time not listed in the source":
        return f"{body_name} will meet {meeting_date} at {meeting_time}."
    return f"{body_name} will meet {meeting_date}."


def _preview_intro(
    body_name: str,
    meeting_date: str,
    meeting_time: str,
    location: str,
    focus_items: List[Dict[str, object]],
    summary_sentence: str = "",
) -> str:
    if not focus_items:
        return (
            f"<p>The Wareham {html.escape(body_name)} is scheduled to meet on {html.escape(meeting_date)} "
            f"{html.escape(meeting_time)} at {html.escape(location)}, according to the posted agenda.</p>"
        )

    if summary_sentence:
        return (
            f"<p>The Wareham {html.escape(body_name)} will meet on {html.escape(meeting_date)} at "
            f"{html.escape(meeting_time)} at {html.escape(location)}. {html.escape(summary_sentence)}</p>"
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
    body_text = re.sub(r"\s+(Discussion and possible vote(?: to| on)?\b)", r"\n\1", body_text, flags=re.IGNORECASE)
    body_text = re.sub(r"\s+(Review and Approve\b)", r"\n\1", body_text, flags=re.IGNORECASE)
    body_text = re.sub(r"\s+(Financial Update\b)", r"\n\1", body_text, flags=re.IGNORECASE)
    body_text = re.sub(r"\s+(Executive Director[â€™']s Report\b)", r"\n\1", body_text, flags=re.IGNORECASE)
    body_text = re.sub(r"\s+(Update on\b)", r"\n\1", body_text, flags=re.IGNORECASE)
    body_text = re.sub(r"\s+(Discussion-\b)", r"\n\1", body_text, flags=re.IGNORECASE)
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
            "topic:",
            "meeting id:",
            "passcode:",
            "dial by your location",
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
    if lowered.startswith("the board chairman reasonably anticipates"):
        return ""
    if "is inviting you to a scheduled zoom meeting" in lowered:
        return ""
    if "members of the public are encouraged" in lowered:
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
    return _oxford_join(phrases)


def _possessive_name(name: str) -> str:
    cleaned = " ".join(str(name or "").split())
    if not cleaned:
        return ""
    return "{}'".format(cleaned) if cleaned.endswith("s") else "{}'s".format(cleaned)


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
    zoning_summary = _zoning_case_summary(raw_text)
    appointment = _parse_appointment_item(raw_text)

    if "appointment" in categories and appointment.get("sentence"):
        return str(appointment["sentence"])

    if "permit" in categories and "tobacco violation" in lowered:
        if "onset village market" in lowered:
            return "The board is expected to review a tobacco-violation case involving Onset Village Market."
        if "sullivan" in lowered:
            return "The board is expected to review a tobacco-violation case involving Sullivan's Liquors."
        return "The board is expected to review tobacco violations tied to local retailers."
    if "permit" in categories and "variance request" in lowered:
        if phrase == "variance request" or phrase.lower().endswith("at request") or phrase.lower().endswith("for request"):
            return "The board is expected to take up a variance request."
        return "The board is expected to take up {}.".format(_with_article(phrase))
    if "public_hearing" in categories:
        if "1b emma lane" in lowered:
            return "A public hearing is scheduled on housing-code violations at 1B Emma Lane."
        if zoning_summary.get("sentence"):
            return str(zoning_summary["sentence"]).replace("The board is set to review", "A public hearing is scheduled on")
        if "safe harbor marina" in lowered:
            return "A public hearing is scheduled on Safe Harbor Marina redevelopment plans."
        if "stormwater" in lowered:
            return "A public hearing is scheduled on stormwater-related work tied to the project."
        return "A public hearing is scheduled on {}.".format(_with_article(phrase))
    if "land_use" in categories:
        if zoning_summary.get("sentence"):
            return str(zoning_summary["sentence"])
        if "238 & 240 sandwich road" in lowered and "site plan review" in lowered:
            return "The board is expected to review a site plan proposal at 238 and 240 Sandwich Road."
        if ("3031 cran hwy" in lowered or "3031 cranberry hwy" in lowered) and "site plan review" in lowered:
            return "The board is expected to review a site plan proposal at 3031 Cranberry Highway."
        if "citizen petition" in lowered and "zoning bylaw article 9" in lowered:
            return "The board is also expected to review a citizen petition to amend the zoning bylaw's off-site parking rules."
        if "fearing tavern" in lowered:
            return "Members are expected to discuss restoration work at Fearing Tavern."
        if "early education learning center" in lowered:
            return "Members are expected to discuss the Early Education Learning Center property in East Wareham."
        if "early education head start" in lowered:
            return "Members are expected to discuss the Early Education Head Start property."
        if "proposed alterations" in lowered:
            return "Commissioners are set to review proposed exterior alterations at 59 Main Street."
        if "safe harbor marina" in lowered:
            return "Commissioners are set to review the Safe Harbor Marina redevelopment proposal."
        if "river hawk" in lowered and "stormwater" in lowered:
            return "Commissioners are also expected to review River Hawk stormwater work."
        return "The agenda includes {} as a development-related item.".format(_with_article(phrase))
    if "budget" in categories:
        if "801 main street" in lowered and "funding" in lowered:
            return "Trust members are expected to review funding status for 801 Main Street."
        if "budget update" in lowered:
            return "Members are expected to review a budget update."
        if "fy 27 capital plan" in lowered or "fy27 capital plan" in lowered:
            return "Members are set to review the FY2027 capital plan article."
        return "Members are set to review {} as part of the meeting's fiscal agenda.".format(_with_article(phrase))
    if "contract" in categories:
        return "The agenda includes {}, which could shape a contract or procurement decision.".format(_with_article(phrase))
    if "town_meeting" in categories:
        if "appoint town counsel" in lowered:
            return "Members are expected to consider appointing Town Counsel."
        if "municipal maintenance" in lowered and "abatement" in lowered:
            return "Members are expected to review FY2026 curbside abatements from the Municipal Maintenance Department."
        if "pour farm tavern" in lowered and "entertainment license" in lowered:
            return "Members are expected to revisit the Pour Farm Tavern entertainment-license request."
        if "vote on town meeting articles" in lowered:
            return "Members are expected to vote on which articles to recommend for Town Meeting."
        if "budget" in lowered:
            return "Members are set to review budget articles headed toward Town Meeting."
        return "Members are expected to discuss {} ahead of Town Meeting.".format(_with_article(phrase))
    if "formal_action" in categories:
        if "bill and payroll warrants" in lowered or "payroll and bill warrants" in lowered:
            return "Committee members could vote on bill and payroll warrants."
        if "spring town meeting articles" in lowered:
            return "Members are expected to discuss articles headed to the Spring Town Meeting."
        if "redwood phase 3 window replacement" in lowered:
            return "Members could vote on a bid for the Redwood Phase 3 window project."
        if "bryant farm management plan" in lowered:
            return "Members are expected to consider the Bryant Farm management plan."
        if "oml violation" in lowered:
            return "Members could take formal action on how to respond to the OML violation finding."
        return "Members could take formal action on {}.".format(_with_article(phrase))
    if "policy" in categories:
        if "community events reconfiguration" in lowered:
            return "Members are expected to discuss a proposed bylaw reworking the town's community-events structure."
        if "spring town meeting funding articles" in lowered:
            return "Members are expected to review community-preservation funding requests headed to the Spring Town Meeting."
        if "town meeting timing debate" in lowered or "october town meeting" in lowered:
            return "Members are expected to discuss whether the article should move to the October Town Meeting."
        if "bylaw committee reorganization" in lowered:
            return "Members are expected to discuss reorganizing the Bylaw Review Committee."
        if "aarp friendly community update" in lowered:
            return "Members are expected to discuss Wareham's AARP Friendly Community effort."
        if "storefront renovation grant program" in lowered:
            return "Members are expected to discuss the new Storefront Renovation Grant Program."
        if "downtown dollars program" in lowered:
            return "Members are expected to review the Downtown Dollars program."
        if "planning director contract authority" in lowered:
            return "Members are expected to consider expanding the Planning Director's contract authority."
        if "red sox yearbook advertising" in lowered:
            return "Members are expected to discuss a proposed Wareham economic-development placement in the Red Sox yearbook."
        if "spring special town meeting articles" in lowered:
            return "Members are expected to review proposed articles for the Spring Special Town Meeting."
        if "bylaw hearing schedule" in lowered:
            return "Members are expected to discuss the schedule for the next bylaw public hearing."
        if "public display policy" in lowered:
            return "Trustees are expected to review the library's public display policy."
        if "minutes and agenda clerk transfer" in lowered:
            return "Members are expected to discuss shifting minute-taking and agenda duties to the board clerk."
        if "existing grant agreements" in lowered:
            return "Members are also expected to review the status of existing grant agreements."
        if "state of emergency" in lowered:
            return "Members are expected to discuss whether to delegate emergency declaration authority to the Town Administrator."
        if "board and committee appointments" in lowered:
            return "Members are expected to review board and committee appointments."
        if "capital planning appointment" in lowered or "capital planning committee appointment" in lowered:
            return "Members are expected to review an appointment to the Capital Planning Committee."
        if "licenses and permits" in lowered:
            return "Members are expected to review licenses and permit items."
        if "council on aging donation" in lowered:
            return "Members are expected to consider a donation for the Council on Aging."
        if "historic district expansion" in lowered:
            return "Members are expected to discuss the Historic District expansion study."
        if "comcast draft renewal license" in lowered:
            return "Members are expected to review Comcast's draft cable-license renewal."
        if "discussion with cable attorney" in lowered:
            return "Members are also expected to discuss the renewal process with cable counsel."
        if "course update" in lowered:
            return "Members are expected to review a course update from management."
        if "winter schedule" in lowered:
            return "Members are also expected to discuss the winter schedule and related plans."
        if "future of the committee" in lowered:
            return "Members are set to discuss the future of the committee and where its work goes next."
        if lowered == "next steps":
            return "Members are also expected to discuss the committee's next steps."
        if "policy review" in lowered:
            return "Committee members are set to review school policy proposals."
        if "school choice" in lowered:
            return "The committee is also expected to revisit the district's school choice position."
        if "district calendar" in lowered:
            return "Committee members are expected to revisit the district calendar for 2026-2027."
        if "course selection" in lowered:
            return "Committee members are expected to review high school course-selection plans for 2026-2027."
        if "course of studies" in lowered:
            return "Committee members are expected to review proposed changes to the course of studies."
        if "mid-cycle review of goals" in lowered:
            return "Committee members are expected to review the district's mid-cycle goals update."
        if "substitute pay" in lowered:
            return "Committee members are expected to discuss substitute pay."
        if "class trip" in lowered:
            return "Committee members could vote on the Class of 2026 trip plans."
        if "security cameras in schools" in lowered or "security visitors in school buildings" in lowered:
            return "Committee members are expected to review school safety policy changes."
        if "emergency closings" in lowered or "emergency health procedures" in lowered or "emergency plans" in lowered:
            return "Committee members are expected to review emergency-response policies."
        if "bus transportation" in lowered or "transportation emergency" in lowered:
            return "Committee members are expected to review transportation policies."
        if "department heads" in lowered and "budget" in lowered:
            return "Members are expected to hear FY2027 budget presentations from department heads."
        if "off site parking" in lowered:
            return "Members are expected to discuss the off-site parking citizen petition."
        if "application of brenda eckstrom" in lowered or "application of bernard pigeon" in lowered:
            return "Members are expected to consider appointments to the Finance Committee."
        if "parkwood beach" in lowered:
            return "Members are expected to discuss the Parkwood Beach issue."
        if "littleton housing project" in lowered:
            return "Members are expected to discuss addressing plans tied to the Littleton Housing Project."
        if "truck restrictions" in lowered and "plymouth ave" in lowered:
            return "Members are expected to discuss truck restrictions on Plymouth Avenue."
        if "relocate bus stop" in lowered:
            return "Members are expected to discuss relocating the bus stop at Indian Neck Road."
        return "The agenda includes {} as a policy item.".format(_with_article(phrase))
    if "appointment" in categories:
        return "Members are expected to consider {}.".format(_with_article(phrase))
    if "permit" in categories:
        return "Members are expected to review {}.".format(_with_article(phrase))
    if "infrastructure" in categories:
        if "fy2026 budget review" in lowered:
            return "Members are expected to review the FY2026 budget with the housing authority's fee accountant."
        if "hilap" in lowered or "high leverage asset preservation program" in lowered:
            return "Members are expected to consider a HILAP funding application tied to housing repairs."
        if "ridecircuit" in lowered:
            return "Members are expected to hear a presentation from Ride Circuit."
        if "potential real estate transaction" in lowered:
            return "Members are expected to discuss a possible real-estate matter."
        if "contract votes" in lowered:
            return "Members are expected to review contract items that could come to a vote."
        if "clean water trust loan forgiveness" in lowered:
            return "Members are expected to discuss possible Clean Water Trust loan forgiveness."
        if "capital stabilization transfer" in lowered:
            return "Members are expected to discuss a transfer into capital stabilization."
        if "cd rate review" in lowered:
            return "Members are expected to review certificate-of-deposit rates and related investment planning."
        if "capital planning member appointment" in lowered or "capital planning committee appointment" in lowered:
            return "Members are expected to discuss appointing a new at-large member to Capital Planning."
        if "updated five-year capital plan" in lowered:
            return "Members are expected to review an updated five-year capital plan."
        if "capital plan impacts" in lowered:
            return "Members are expected to discuss how pending articles could affect the capital plan."
        if "licenses, markers, and monuments" in lowered:
            return "Members are expected to review license, marker, and monument requests."
        if "cemetery grass purchase" in lowered:
            return "Members are expected to review a purchase for cemetery grass."
        if "tractor situation" in lowered:
            return "Members are expected to revisit the tractor situation at the course."
        if "golf cart fleet" in lowered:
            return "Members are expected to discuss golf cart fleet needs for 2026."
        if "equipment status" in lowered:
            return "Members are also expected to review current equipment status."
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
                phrase = _focus_summary_phrase(item)
                if phrase and _is_low_value_focus_line(phrase):
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

    if not focus:
        for item in _generic_agenda_lines(extraction, limit=8):
            if _is_low_value_focus_line(item):
                continue
            if _looks_truncated(item):
                continue
            score, reasons = _score_editorial_line(item)
            if score <= 0:
                continue
            focus.append({"text": item, "score": score, "section": "", "reasons": reasons})

    focus.sort(key=lambda entry: (-int(entry["score"]), str(entry["text"])))
    focus_display_keys = [
        (_focus_summary_phrase(str(item["text"])) or str(item["text"])).lower()
        for item in focus
    ]
    generic_appointment_phrases = {"board appointments", "board and committee appointments", "new member appointment"}
    has_specific_appointment = any(
        key.endswith(" appointment") and key not in generic_appointment_phrases
        for key in focus_display_keys
    )
    strong_hearing_keys = [
        key for key in focus_display_keys
        if any(
            token in key
            for token in (
                "permit request",
                "site plan review",
                "variance request",
                "special permit",
                "comprehensive permit",
                "safe harbor marina redevelopment",
                "river hawk stormwater work",
                "public hearing",
            )
        )
    ]
    deduped = []
    seen = set()
    for item in focus:
        display_key = (_focus_summary_phrase(str(item["text"])) or str(item["text"])).lower()
        if has_specific_appointment and display_key in generic_appointment_phrases:
            continue
        if len(strong_hearing_keys) >= 2 and display_key in (
            "maple springs road anr",
            "draft zoning bylaw recodification issues",
            "zoning bylaw policy issues",
            "zoning bylaw citizen petition",
        ):
            continue
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
            bullets.append("<li>{}<span class=\"story-note story-note--why\">Why it matters: {}.</span></li>".format(text, html.escape(reason)))
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
                item = _clean_agenda_display_item(raw_item)
                if not item or _looks_truncated(item) or _is_low_value_agenda_line(item) or item.lower().strip(" .;:-\u2013\u2014") == "discussion and possible vote":
                    continue
                if item not in agenda_items:
                    agenda_items.append(item)
                if len(agenda_items) >= 8:
                    break
            if len(agenda_items) >= 8:
                break

    if not agenda_items and isinstance(highlights, list):
        for raw_item in highlights[:8]:
            item = _clean_agenda_display_item(raw_item)
            if not item or _looks_truncated(item) or _is_low_value_agenda_line(item) or item.lower().strip(" .;:-\u2013\u2014") == "discussion and possible vote":
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
    phones = source_meta.get("remote_phone_numbers") if isinstance(source_meta.get("remote_phone_numbers"), list) else []
    phones = [str(phone).strip() for phone in phones if str(phone).strip()]
    if not join_url and not webinar_id and not phones:
        return ""

    details = []
    if join_url:
        details.append('Join via Zoom: <a href="{0}">{0}</a>'.format(html.escape(str(join_url))))
    if webinar_id:
        details.append("Meeting ID: {}".format(html.escape(str(webinar_id))))
    if passcode and (join_url or webinar_id or phones):
        details.append("Passcode: {}".format(html.escape(str(passcode))))
    for phone in phones:
        details.append("Dial-in: {}".format(html.escape(phone)))

    return "<p><strong>Remote access:</strong><br>{}</p>".format("<br>".join(details))


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
            f"<a href=\"{html.escape(source_url)}\">full posted minutes</a> for the complete record and exact wording.</p>"
        )
    else:
        focus_items = _agenda_focus_items(extraction)
        headline = _preview_headline(body_name, meeting_date, focus_items)
        dek = _preview_dek(body_name, meeting_date, meeting_time, location, focus_items)
        if focus_items:
            focus_block = _focus_list_block(focus_items, "What matters most on the agenda")
            summary = _preview_summary(body_name, focus_items, dek)
        else:
            summary = _sentence_from_phrases(
                "The posted agenda includes",
                _summary_phrase_list(_agenda_highlights(extraction)),
            ) or dek
        intro = _preview_intro(body_name, meeting_date, meeting_time, location, focus_items, summary)
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
            f"<p>The public can review the <a href=\"{html.escape(source_url)}\">full official agenda</a> "
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
        desired_existing_slug = _story_slug(connection, meeting, story_type, int(existing_story["id"])) if existing_story else None
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
                and existing_story.get("slug") == desired_existing_slug
            ):
                continue

        story_id = None
        if existing_story:
            story_id = int(existing_story["id"])
            desired_slug = desired_existing_slug or _story_slug(connection, meeting, story_type, story_id)
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
                        slug = %s,
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
                        desired_slug,
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
