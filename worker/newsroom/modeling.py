import json
import re
from datetime import datetime
from typing import Dict, Optional, Tuple


BODY_NAME_MAP = {
    "board of selectmen": "Select Board",
    "select board": "Select Board",
    "planning board": "Planning Board",
    "conservation commission": "Conservation Commission",
    "school committee": "School Committee",
    "board of health": "Board of Health",
    "finance committee": "Finance Committee",
    "zoning board of appeals": "Zoning Board of Appeals",
    "historical commission": "Historical Commission",
    "community preservation committee": "Community Preservation Committee",
    "capital planning committee": "Capital Planning Committee",
    "sewer commissioner": "Sewer Commissioners",
    "sewer commissioners": "Sewer Commissioners",
    "water pollution control facility board": "Water Pollution Control Facility Board",
    "redevelopment authority": "Redevelopment Authority",
    "municipal maintenance department": "Municipal Maintenance Department",
    "board of library trustees": "Board of Library Trustees",
    "wfl board of library trustees": "Board of Library Trustees",
    "board of assessors": "Board of Assessors",
    "alternative energy committee": "Alternative Energy Committee",
    "affordable housing trust": "Affordable Housing Trust",
    "bylaw review committee": "Bylaw Review Committee",
    "by-law review committee": "Bylaw Review Committee",
}


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:160] or "item"


def normalize_body_name(text):
    lowered = text.lower()
    for candidate, normalized in BODY_NAME_MAP.items():
        if candidate in lowered:
            return normalized
    return None


def classify_body_type(name):
    lowered = name.lower()
    if "board" in lowered:
        return "board"
    if "committee" in lowered:
        return "committee"
    if "commission" in lowered:
        return "commission"
    if "authority" in lowered:
        return "authority"
    if "trust" in lowered:
        return "trust"
    return "body"


def parse_source_meta(raw_meta_json: Optional[str]) -> Dict[str, object]:
    if not raw_meta_json:
        return {}
    try:
        value = json.loads(raw_meta_json)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _infer_format(lowered: str) -> str:
    if "packet=true" in lowered:
        return "pdf"
    if "html=true" in lowered:
        return "html"
    if ".pdf" in lowered or "viewfile" in lowered:
        return "pdf"
    if ".html" in lowered or ".htm" in lowered:
        return "html"
    return "link"


def classify_artifact(item_title, item_type, source_url, raw_meta=None):
    meta = raw_meta or {}
    lowered = " ".join(
        [
            item_title or "",
            item_type or "",
            source_url or "",
            str(meta.get("artifact_label") or ""),
            str(meta.get("entry_title") or ""),
        ]
    ).lower()
    fmt = _infer_format(lowered)

    if "packet" in lowered:
        return "packet", fmt, False, False
    if "previous version" in lowered:
        return "previous_version", fmt, False, True
    if "transcript" in lowered:
        return "transcript", fmt, False, False
    if "append" in lowered:
        return "appendix", fmt, False, False
    if "minute" in lowered:
        return "minutes", fmt, True, False
    if "agenda" in lowered:
        return "agenda", fmt, True, False
    if "html=true" in lowered:
        return "html_view", "html", False, False
    return "reference", fmt, False, False


def is_public_story_artifact(artifact_type: str) -> bool:
    return artifact_type in ("agenda", "minutes")


def is_calendar_artifact(artifact_type: str) -> bool:
    return artifact_type == "agenda"


def should_review_artifact(artifact_type: str) -> bool:
    return artifact_type in ("agenda", "minutes", "reference")


def parse_agenda_center_datetime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    candidates = [
        "%b %d, %Y %I:%M %p",
        "%B %d, %Y %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def parse_agenda_center_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidates = [
        "%b %d, %Y",
        "%B %d, %Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y-%m-%d",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def derive_meeting_status(text: str) -> str:
    lowered = (text or "").lower()
    if "cancelled" in lowered or "canceled" in lowered:
        return "cancelled"
    if "no meeting scheduled" in lowered:
        return "cancelled"
    if "minute" in lowered:
        return "completed"
    return "scheduled"


def canonical_event_title(body_name):
    if not body_name:
        return None
    if body_name.lower().endswith(" meeting"):
        return body_name
    return "{} Meeting".format(body_name)


def derive_story_dates(meeting_type, meeting_date, meeting_time, artifact_posted_at, published_at):
    display_date = artifact_posted_at or published_at
    sort_date = artifact_posted_at or published_at

    if meeting_type == "meeting_preview" and meeting_date:
        meeting_stamp = "{} {}".format(meeting_date, meeting_time or "00:00:00")
        try:
            meeting_dt = datetime.strptime(meeting_stamp, "%Y-%m-%d %H:%M:%S")
            posted_dt = datetime.strptime(display_date, "%Y-%m-%d %H:%M:%S") if display_date else None
            if posted_dt and meeting_dt >= posted_dt:
                sort_date = meeting_stamp
        except (TypeError, ValueError):
            pass

    return display_date, sort_date
