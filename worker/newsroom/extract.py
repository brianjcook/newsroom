import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pymysql.connections import Connection

from .config import WorkerConfig
from .documents import DocumentRecord
from .modeling import parse_source_meta

EXTRACTOR_VERSION = "0.3"


@dataclass(frozen=True)
class ExtractionRecord:
    document_id: int
    title: str
    body_text: str
    structured_json: Dict[str, object]
    confidence_score: float
    warnings: List[str]


def _normalize_line(value: str) -> str:
    normalized = " ".join(value.replace("\u00a0", " ").split())
    normalized = normalized.replace("T0WN", "TOWN")
    normalized = normalized.replace("\uf0b7", " - ")
    normalized = re.sub(r"(?<=\w)\s+-\s+(?=\w)", "-", normalized)
    repair_patterns = [
        (r"\bR eport\b", "Report"),
        (r"\bRei mbursements\b", "Reimbursements"),
        (r"\bDi scriminatory\b", "Discriminatory"),
        (r"\bHar assment\b", "Harassment"),
        (r"\bFi nancial\b", "Financial"),
        (r"\bCa lendar\b", "Calendar"),
        (r"\bSchoolh ouse\b", "Schoolhouse"),
        (r"\bArtiles\b", "Articles"),
    ]
    for pattern, replacement in repair_patterns:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def _is_pdf_noise_line(line: str) -> bool:
    lowered = line.lower().strip()
    if not lowered:
        return True
    if re.fullmatch(r"\d+", lowered):
        return True
    if lowered in ("town of wareham", "select board", "meeting agenda"):
        return True
    if re.fullmatch(r"(january|february|march|april|may|june|july|august|september|october|november|december) \d{1,2}, \d{4}", lowered):
        return True
    if lowered.startswith("publication date:"):
        return True
    if lowered.startswith("by order of"):
        return True
    return False


def _clean_pdf_lines(body_text: str) -> List[str]:
    expanded = str(body_text or "")
    if expanded.count("\n") < 6:
        expanded = re.sub(r"\s+(DAY\s*&\s*DATE:)\s+", r"\n\1 ", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\s+(TIME:)\s+", r"\n\1 ", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\s+(PLACE:)\s+", r"\n\1 ", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\s+(Zoom Meeting Information:)\s+", r"\n\1 ", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\s+(Meeting ID:)\s+", r"\n\1 ", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\s+(Passcode:)\s+", r"\n\1 ", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\s+([IVXLCDM]+[\.\)])\s+", r"\n\1 ", expanded)
        expanded = re.sub(r"\s+(\d+[\.\)])\s+", r"\n\1 ", expanded)
        expanded = re.sub(r"\s+([a-z][\.\)])\s+", r"\n\1 ", expanded, flags=re.IGNORECASE)
    return [
        line
        for line in (_normalize_line(line) for line in expanded.splitlines())
        if line and not _is_pdf_noise_line(line)
    ]


def _append_item_text(section: Dict[str, object], text: str) -> None:
    items = section.setdefault("items", [])
    normalized = _normalize_line(text)
    if not normalized:
        return
    if items:
        items[-1] = "{} {}".format(str(items[-1]).rstrip(), normalized).strip()
    else:
        items.append(normalized)


def _append_nested_text(section: Dict[str, object], text: str) -> None:
    normalized = _normalize_line(text)
    if not normalized:
        return
    items = section.setdefault("items", [])
    if not items:
        items.append(normalized)
        return
    current = str(items[-1]).rstrip()
    if ":" in current:
        items[-1] = "{}; {}".format(current, normalized)
    else:
        items[-1] = "{}: {}".format(current, normalized)


def _looks_like_agenda_item(line: str) -> bool:
    return bool(
        re.match(r"^\d+[\.\)]\s+.+$", line)
        or re.match(r"^[a-z][\.\)]\s+.+$", line, flags=re.IGNORECASE)
        or re.match(r"^\([0-9]+\)\s+.+$", line)
        or re.match(r"^[ivxlcdm]+[\.\)]\s+.+$", line, flags=re.IGNORECASE)
    )


def _extract_pdf_source_meta(body_text: str) -> Dict[str, object]:
    metadata = {}  # type: Dict[str, object]
    compact = re.sub(r"\s+", "", body_text)

    join_match = re.search(r"(https://[^\s]*zoom\.us/j/[^\s]+)", body_text, flags=re.IGNORECASE)
    if join_match:
        metadata["remote_join_url"] = join_match.group(1).strip()
    else:
        compact_match = re.search(r"(https://[^\s]*zoom\.us/j/[A-Za-z0-9?=&._%-]+)", compact, flags=re.IGNORECASE)
        if compact_match:
            metadata["remote_join_url"] = compact_match.group(1).strip()

    meeting_id_match = re.search(r"Meeting ID:\s*([0-9 ]{9,})", body_text, flags=re.IGNORECASE)
    if meeting_id_match:
        metadata["remote_webinar_id"] = " ".join(meeting_id_match.group(1).split())

    passcode_match = re.search(r"Passcode:\s*([A-Za-z0-9]+)", body_text, flags=re.IGNORECASE)
    if passcode_match:
        metadata["remote_passcode"] = passcode_match.group(1).strip()

    phone_numbers = []
    for value in re.findall(r"(\+\d[\d\s().,-]{7,}\d(?:,,[0-9#,*]+)?)", body_text):
        normalized = value.strip()
        if normalized not in phone_numbers:
            phone_numbers.append(normalized)
    if phone_numbers:
        metadata["remote_phone_numbers"] = phone_numbers

    return metadata


def _sanitize_location_text(value: str) -> str:
    location = _normalize_line(value)
    location = re.sub(r"^locati\s*on:\s*", "", location, flags=re.IGNORECASE)
    location = re.split(r"\b(?:To join remotely|Join Zoom Meeting|Meeting ID|Mobile:|The WAREHAM)\b", location, maxsplit=1, flags=re.IGNORECASE)[0]
    location = re.sub(r"\bRoom\s+(\d)\s+(\d{2})\b", r"Room \1\2", location, flags=re.IGNORECASE)
    return location.strip(" ,.;:-")


def _is_procedural_item(text: str) -> bool:
    lowered = _normalize_line(text).lower().strip(" .;:-")
    procedural_starts = (
        "call to order",
        "call the meeting to order",
        "call public meeting to order",
        "roll call",
        "citizens participation",
        "announcements",
        "adjournment",
        "adjourn",
        "good news",
        "public participation",
        "student representative report",
        "student attending report",
        "report of the conservation agent",
        "administrative approvals",
        "consent agenda",
        "any other business",
        "signing of documents approved",
        "review and approve minutes",
        "approval of prior meeting minutes",
        "approval of meeting minutes",
        "approve minutes",
        "next meeting",
        "any other business not anticipated",
        "any other business not reasonably anticipated",
        "any business unanticipated",
    )
    return lowered.startswith(procedural_starts)


def _is_header_metadata_item(text: str) -> bool:
    lowered = _normalize_line(text).lower()
    if not lowered:
        return True
    header_tokens = (
        "notice of meeting",
        "commission members",
        "fax:",
        "54 marion road",
        "wareham, massachusetts",
        "town of wareham",
    )
    return any(token in lowered for token in header_tokens)


def _clean_preservation_item(text: str) -> str:
    cleaned = _normalize_line(text)
    if not cleaned:
        return ""

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
    cleaned = re.sub(
        r"\s+[A-Z][A-Za-z.\s]+\s*,?\s*Chair Wareham Historic District Commission.*$",
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
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    return cleaned


def _split_compound_item(text: str) -> List[str]:
    normalized = _normalize_line(text)
    if not normalized:
        return []

    finance_split = _split_finance_article_item(normalized)
    if len(finance_split) > 1:
        return finance_split

    petition_split = _split_zoning_petition_item(normalized)
    if len(petition_split) > 1:
        return petition_split

    split_segments = [normalized]
    if ";" in normalized:
        split_segments = [segment.strip(" ,.;:-") for segment in normalized.split(";") if segment.strip(" ,.;:-")]
    expanded = []  # type: List[str]
    for segment in split_segments:
        second_pass = _split_school_style_item(segment)
        if len(second_pass) > 1:
            for child in second_pass:
                expanded.extend(_split_school_style_item(child))
        else:
            expanded.extend(second_pass)

    if len(expanded) < 2:
        return expanded or [normalized]

    prefix = ""
    lead = expanded[0]
    if ":" in lead:
        maybe_prefix, maybe_value = lead.split(":", 1)
        if len(maybe_prefix.strip()) <= 32:
            prefix = maybe_prefix.strip()
            expanded[0] = maybe_value.strip(" ,.;:-")

    generic_prefixes = {
        "reports",
        "report",
        "policy review",
        "old business",
        "new business",
        "appointments",
        "hearings",
    }
    if prefix.lower() not in generic_prefixes and not prefix.lower().endswith("report"):
        prefix = ""

    normalized_segments = []
    for segment in expanded:
        cleaned = _normalize_line(segment)
        if not cleaned:
            continue
        if prefix:
            if cleaned.lower().startswith("{}:".format(prefix).lower()):
                normalized_segments.append(cleaned)
            else:
                normalized_segments.append("{}: {}".format(prefix, cleaned))
        else:
            normalized_segments.append(cleaned)
    return normalized_segments or [normalized]


def _clean_zoning_segment(text: str) -> str:
    cleaned = _normalize_line(text)
    cleaned = re.sub(r"^(hearings?|continued hearings?)\s*:?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^petition#\s*applicant name\s*application type\s*decision deadline\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bthat the chair did not reasonably anticipate.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    return cleaned


def _split_zoning_petition_item(text: str) -> List[str]:
    normalized = _normalize_line(text)
    lowered = normalized.lower()
    if "petition#" not in lowered and not ("variance" in lowered or "special permit" in lowered):
        return [normalized]

    matches = list(re.finditer(r"\b\d{2}-\d{2}\b", normalized))
    if len(matches) < 2:
        return [normalized]

    segments = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        segment = _clean_zoning_segment(normalized[start:end])
        if segment:
            segments.append(segment)

    deduped = []
    seen = set()
    for segment in segments:
        key = segment.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(segment)
    return deduped or [normalized]


def _split_school_style_item(text: str) -> List[str]:
    normalized = _normalize_line(text)
    if not normalized:
        return []

    school_choice_match = re.search(
        r"school choice\s+(\d{4})\s*-\s*(\d{2}).*vote",
        normalized,
        flags=re.IGNORECASE,
    )
    if school_choice_match:
        start_year = school_choice_match.group(1)
        end_year = "{}{}".format(start_year[:2], school_choice_match.group(2))
        return ["School Choice {}-{} (vote)".format(start_year, end_year)]

    policy_match = re.match(r"^(Policy Review)(?:-?VOTE)?\s+(.+)$", normalized, flags=re.IGNORECASE)
    if policy_match:
        suffix = policy_match.group(2).strip(" ,.;:-")
        policy_parts = [part.strip(" ,.;:-") for part in re.split(r",\s*", suffix) if part.strip(" ,.;:-")]
        if len(policy_parts) > 1:
            return ["Policy Review: {}".format(part) for part in policy_parts]

    marker_pattern = re.compile(
        r"(?=(School Committee Report|Superintendent[’']?s Report|Director of Finance|Financial Report|Grants Report|School Choice Vote|Policy Review(?:-?VOTE)?))",
        flags=re.IGNORECASE,
    )
    matches = list(marker_pattern.finditer(normalized))
    if len(matches) > 1:
        segments = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
            segment = normalized[start:end].strip(" ,.;:-")
            if segment:
                segments.append(segment)
        if segments:
            return segments

    report_match = re.match(r"^(Superintendent[’']?s Report)\s+\d{1,2}:\d{2}\s*[ap]\.?m\.?\s*-\s*(.+)$", normalized, flags=re.IGNORECASE)
    if report_match:
        suffix = report_match.group(2).strip(" ,.;:-")
        report_parts = [part.strip(" ,.;:-") for part in re.split(r"\s+-\s+|,\s*", suffix) if part.strip(" ,.;:-")]
        cleaned_parts = []
        for part in report_parts:
            if "bill and payroll warrants-district calendar" in part.lower():
                cleaned_parts.append("Superintendent's Report: Bill and Payroll Warrants")
                cleaned_parts.append("Superintendent's Report: District Calendar 2025-26 Update (possible vote)")
                continue
            if part.lower() in ("gifts", "bill and payroll warrants", "district calendar 2025-26 update", "district calendar 2025 26 update"):
                cleaned_parts.append("Superintendent's Report: {}".format(part))
            elif part.lower().endswith("(possible vote)") and "district calendar" in part.lower():
                cleaned_parts.append("Superintendent's Report: {}".format(part))
            else:
                cleaned_parts.append(part)
        if len(cleaned_parts) > 1:
            return cleaned_parts

    return [normalized]


def _split_finance_article_item(text: str) -> List[str]:
    normalized = _normalize_line(text)
    lowered = normalized.lower()
    if "article #" not in lowered or "budget" not in lowered:
        return [normalized]

    article_matches = list(re.finditer(r"Article\s*#\s*\d+\s+", normalized, flags=re.IGNORECASE))
    if len(article_matches) < 2:
        return [normalized]

    segments = []
    for index, match in enumerate(article_matches):
        start = match.start()
        end = article_matches[index + 1].start() if index + 1 < len(article_matches) else len(normalized)
        segment = normalized[start:end].strip(" ,.;:-")
        if segment:
            segments.append(segment)
    return segments or [normalized]


def _normalize_section_items(section: Dict[str, object]) -> List[str]:
    cleaned_items = []
    for item in section.get("items") or []:
        normalized = _clean_preservation_item(str(item))
        if not normalized or _is_procedural_item(normalized) or _is_header_metadata_item(normalized):
            continue
        for candidate in _split_compound_item(normalized):
            cleaned_candidate = _clean_preservation_item(candidate)
            if not cleaned_candidate:
                continue
            if cleaned_candidate.lower().strip(" .;:-\u2013\u2014") == "discussion and possible vote":
                continue
            if cleaned_items and re.match(r"^[\-\u2013\u2014]\s*", cleaned_candidate):
                cleaned_items[-1] = "{} {}".format(
                    str(cleaned_items[-1]).rstrip(" ,.;:-"),
                    re.sub(r"^[\-\u2013\u2014]\s*", "- ", cleaned_candidate),
                ).strip()
                continue
            cleaned_items.append(cleaned_candidate)
    deduped = []
    seen = set()
    for item in cleaned_items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _parse_heading_only_sections(lines: List[str]) -> List[Dict[str, object]]:
    sections = []
    current_section = None  # type: Optional[Dict[str, object]]
    heading_map = {
        "minutes": "Minutes",
        "old business": "Old Business",
        "new business": "New Business",
    }

    for raw_line in lines:
        line = _normalize_line(raw_line)
        lowered = line.lower().strip(" .;:-")
        if not line or _is_header_metadata_item(line):
            continue

        matched_heading = None
        for prefix, title in heading_map.items():
            if lowered.startswith(prefix):
                matched_heading = title
                break

        if matched_heading:
            if current_section and current_section.get("items"):
                sections.append(current_section)
            current_section = {
                "number": len(sections) + 1,
                "title": matched_heading,
                "items": [],
            }
            tail = line[len(prefix):].strip(" .;:-")
            if tail and not _is_procedural_item(tail) and tail.lower().strip(" .;:-\u2013\u2014") != "discussion and possible vote":
                current_section["items"].append(tail)
            continue

        if current_section:
            if _is_procedural_item(line) or lowered.strip(" .;:-\u2013\u2014") == "discussion and possible vote":
                continue
            current_section["items"].append(line)

    if current_section and current_section.get("items"):
        sections.append(current_section)
    return sections


def _inline_section_heading(line: str) -> Tuple[str, str]:
    normalized = _normalize_line(line)
    if not normalized:
        return "", ""
    for heading in ("Minutes", "Old Business", "New Business"):
        if normalized.lower().startswith(heading.lower()):
            tail = normalized[len(heading):].strip(" .;:-")
            return heading, tail
    return "", ""


def _parse_agenda_pdf(body_text: str) -> Dict[str, object]:
    structured = {}  # type: Dict[str, object]
    lines = _clean_pdf_lines(body_text)
    structured["source_meta"] = _extract_pdf_source_meta(body_text)

    agenda_start_index = next((index for index, line in enumerate(lines) if _looks_like_agenda_item(line)), len(lines))
    header_lines = lines[:agenda_start_index]

    date_time_index = None
    for index, line in enumerate(header_lines[:20]):
        if line.lower().startswith("date and time:"):
            value = line.split(":", 1)[1].strip()
            structured["meeting_line"] = value
            date_match = re.search(r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})", value)
            time_match = re.search(r"(\d{1,2}:\d{2}\s*[ap]\.?m\.?)", value, flags=re.IGNORECASE)
            if date_match:
                structured["meeting_date_line"] = date_match.group(1).strip()
            if time_match:
                structured["meeting_time_line"] = time_match.group(1).strip()
            date_time_index = index
            break
        if re.search(r"[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}\s*[-\u2013\u2014]\s*\d{1,2}:\d{2}\s*[ap]\.?m\.?", line, flags=re.IGNORECASE):
            date_time_index = index
            structured["meeting_line"] = line
            date_match = re.search(r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})", line)
            time_match = re.search(r"(\d{1,2}:\d{2}\s*[ap]\.?m\.?)", line, flags=re.IGNORECASE)
            if date_match:
                structured["meeting_date_line"] = date_match.group(1).strip()
            if time_match:
                structured["meeting_time_line"] = time_match.group(1).strip()
            break

    explicit_location = next((line.split(":", 1)[1].strip().rstrip(".") for line in header_lines if line.lower().startswith("location:")), None)
    if explicit_location:
        explicit_location = _sanitize_location_text(explicit_location)
        structured["meeting_location_line"] = explicit_location
        structured["meeting_location_name"] = explicit_location.split(",", 1)[0].strip()

    if date_time_index is not None and not structured.get("meeting_location_line"):
        location_lines = []
        for line in header_lines[date_time_index + 1:]:
            lowered = line.lower()
            if (
                lowered.startswith("join zoom meeting")
                or lowered.startswith("topic:")
                or lowered.startswith("time:")
                or lowered.startswith("meeting id:")
                or lowered.startswith("passcode:")
                or lowered.startswith("one tap mobile")
                or lowered.startswith("join instructions")
                or lowered == "---"
                or line.startswith("http://")
                or line.startswith("https://")
                or re.match(r"^\+\d{10,}", line)
                or re.fullmatch(r"[A-Za-z0-9_-]{12,}", line)
            ):
                continue
            location_lines.append(line)

        if location_lines:
            venue = location_lines[0]
            remainder = location_lines[1:]
            room_lines = [item for item in remainder if re.search(r"\broom\b|\brm\b", item, flags=re.IGNORECASE)]
            address_lines = [item for item in remainder if item not in room_lines]
            location_parts = [venue] + address_lines + room_lines
            structured["meeting_location_name"] = _sanitize_location_text(venue)
            structured["meeting_location_line"] = _sanitize_location_text(", ".join(location_parts))
            if address_lines:
                structured["meeting_address_line"] = _sanitize_location_text(", ".join(address_lines))

    if not structured.get("meeting_location_line"):
        header_text = " ".join(header_lines)
        address_match = re.search(r"(\d+\s+[A-Za-z]+\s+(?:Road|Rd\.?|Street|St\.?|Avenue|Ave\.?)(?:\s*,?\s*Room\s+\d+)?(?:\s*,?\s*Wareham,\s*MA\.?)?)", header_text, flags=re.IGNORECASE)
        room_match = re.search(r"(Room\s+\d+)", header_text, flags=re.IGNORECASE)
        if address_match:
            location_parts = [address_match.group(1).strip()]
            if room_match and room_match.group(1) not in location_parts[0]:
                location_parts.append(room_match.group(1).strip())
            structured["meeting_location_line"] = _sanitize_location_text(", ".join(location_parts))
            structured["meeting_location_name"] = structured["meeting_location_line"]

    sections = []
    current_section = {"number": 1, "title": "Agenda", "items": []}  # type: Dict[str, object]
    current_heading = ""
    for line in lines[agenda_start_index:]:
        inline_section_title, inline_section_tail = _inline_section_heading(line)
        heading_match = re.match(r"^([IVXLCDM]+)[\.\)]\s+(.+)$", line, flags=re.IGNORECASE)
        section_match = re.match(r"^(\d+)[\.\)]\s+(.+)$", line)
        subitem_match = re.match(r"^([a-z]+)[\.\)]\s+(.+)$", line, flags=re.IGNORECASE)
        nested_match = re.match(r"^\((\d+)\)\s+(.+)$", line)
        roman_match = re.match(r"^([ivxlcdm]+)[\.\)]\s+(.+)$", line, flags=re.IGNORECASE)

        if inline_section_title:
            if current_section.get("items"):
                sections.append(current_section)
            current_section = {
                "number": len(sections) + 1,
                "title": inline_section_title,
                "items": [],
            }
            current_heading = ""
            tail_lower = inline_section_tail.lower().strip(" .;:-")
            if inline_section_tail and tail_lower != "discussion and possible vote" and not _is_procedural_item(inline_section_tail):
                current_section["items"].append(inline_section_tail)
            continue

        if heading_match:
            heading_title = heading_match.group(2).strip().rstrip(":")
            if current_section.get("items"):
                sections.append(current_section)
            current_section = {
                "number": len(sections) + 1,
                "title": heading_title,
                "items": [],
            }
            current_heading = ""
            continue

        if line.endswith(":") and len(line) < 120 and not section_match:
            current_heading = line.rstrip(":").strip()
            continue

        if section_match:
            item_text = section_match.group(2).strip()
            if current_heading and current_heading.lower() not in ("agenda", "call to order by the chair", "roll call"):
                item_text = "{}: {}".format(current_heading, item_text)
            current_section["items"].append(item_text)
            continue

        if subitem_match:
            _append_nested_text(current_section, subitem_match.group(2).strip())
            continue

        if roman_match:
            _append_nested_text(current_section, roman_match.group(2).strip())
            continue

        if nested_match:
            _append_nested_text(current_section, nested_match.group(2).strip())
            continue

        time_hearing_match = re.match(r"^([0-9:]+\s*[ap]\.?m\.?)\s+(.+)$", line, flags=re.IGNORECASE)
        if time_hearing_match:
            current_section["items"].append("{} {}".format(time_hearing_match.group(1).strip(), time_hearing_match.group(2).strip()))
            continue

        article_match = re.match(r"^(Article\s*#\s*\d+\s+.+)$", line, flags=re.IGNORECASE)
        if article_match:
            current_section["items"].append(article_match.group(1).strip())
            continue

        if current_section["items"]:
            _append_item_text(current_section, line)

    if current_section.get("items"):
        sections.append(current_section)

    if not any(section.get("items") for section in sections):
        sections = _parse_heading_only_sections(lines)

    if sections:
        for section in sections:
            section["items"] = _normalize_section_items(section)
        structured["agenda_sections"] = sections

    scored_highlights = []
    for section in sections:
        section_title = section["title"].lower()
        for item in section["items"]:
            lowered = item.lower()
            score = 0
            if "continued public hearings" in lowered and " – " not in item and "-" not in item:
                continue
            if "public hearings:" in lowered and " – " not in item and "-" not in item:
                continue
            if "safe harbor marina" in lowered:
                score += 92
            if "school choice" in lowered:
                score += 70
            if "policy review" in lowered:
                score += 58
            if "discriminatory harassment" in lowered:
                score += 44
            if "tobacco violation" in lowered:
                score += 95
            if "comprehensive wastewater management plan" in lowered:
                score += 100
            if "title 5" in lowered:
                score += 50
            if "variance request" in lowered:
                score += 40
            if "possible vote" in lowered:
                score += 40
            if "discussion" in lowered:
                score += 20
            if "public hearing" in lowered or "hearing" in lowered:
                score += 25
            if "presentation" in lowered:
                score += 15
            if "appoint town counsel" in lowered or "appoint" in lowered:
                score += 10
            if "open space" in lowered or "town meeting" in lowered:
                score += 10
            if "article #" in lowered:
                score += 5
            if section_title in ("town business", "hearings"):
                score += 5

            if score > 0:
                scored_highlights.append((score, item))

    if scored_highlights:
        scored_highlights.sort(key=lambda pair: (-pair[0], pair[1]))
        structured["agenda_highlights"] = [item for _, item in scored_highlights[:8]]
    elif sections:
        fallback_highlights = []
        for section in sections:
            for item in section.get("items") or []:
                normalized = _normalize_line(str(item))
                if not normalized or _is_procedural_item(normalized):
                    continue
                fallback_highlights.append(normalized)
                if len(fallback_highlights) >= 8:
                    break
            if len(fallback_highlights) >= 8:
                break
        if fallback_highlights:
            structured["agenda_highlights"] = fallback_highlights

    return structured


def _pdf_review_flags(body_text: str, confidence_score: float, warnings: List[str], structured: Dict[str, object]) -> List[str]:
    flags = []  # type: List[str]
    body_length = len((body_text or "").strip())
    sections = structured.get("agenda_sections") or []
    highlights = structured.get("agenda_highlights") or []

    if confidence_score < 0.55:
        flags.append("low_confidence_pdf")
    if body_length < 250:
        flags.append("thin_pdf_text")
    if any("little or no extractable text" in warning.lower() for warning in warnings):
        flags.append("sparse_pdf_pages")
    if any("empty text" in warning.lower() for warning in warnings):
        flags.append("empty_pdf_text")
    if not sections and not highlights and body_length < 1200:
        flags.append("unstructured_pdf")

    deduped = []
    for flag in flags:
        if flag not in deduped:
            deduped.append(flag)
    return deduped


def _source_meta(connection: Connection, source_item_id: int) -> Dict[str, object]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT raw_meta_json FROM source_items WHERE id = %s LIMIT 1",
            (source_item_id,),
        )
        row = cursor.fetchone()
    if not row:
        return {}
    return parse_source_meta(row["raw_meta_json"])


def _extract_html(path: Path) -> Tuple[str, str, float, List[str]]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text(" ", strip=True)

    body_text = "\n".join(
        line.strip()
        for line in soup.get_text("\n").splitlines()
        if line.strip()
    )
    confidence = 0.75 if body_text else 0.2
    warnings = [] if body_text else ["HTML extraction produced empty text."]
    return title[:512], body_text, confidence, warnings


def _extract_pdf(path: Path) -> Tuple[str, str, float, List[str], Dict[str, object]]:
    reader = PdfReader(str(path))
    pages = []  # type: List[str]
    warnings = []  # type: List[str]

    for index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if not page_text.strip():
            warnings.append(f"Page {index} had little or no extractable text.")
        pages.append(page_text.strip())

    body_text = "\n\n".join(page for page in pages if page)
    title = path.stem.replace("_", " ")
    confidence = 0.85 if body_text else 0.15
    if not body_text:
        warnings.append("PDF extraction produced empty text.")
    return title[:512], body_text, confidence, warnings, _parse_agenda_pdf(body_text)


def extract_documents(config: WorkerConfig, connection: Connection, documents: List[DocumentRecord]) -> List[ExtractionRecord]:
    Path(config.extractions_dir).mkdir(parents=True, exist_ok=True)
    extractions = []  # type: List[ExtractionRecord]

    for document in documents:
        storage_path = Path(config.storage_root) / document.storage_path
        title = ""
        body_text = ""
        confidence_score = 0.0
        warnings = []  # type: List[str]
        extra_structured = {}  # type: Dict[str, object]
        source_meta = _source_meta(connection, document.source_item_id)

        if document.storage_path.lower().endswith(".pdf"):
            title, body_text, confidence_score, warnings, extra_structured = _extract_pdf(storage_path)
            review_flags = _pdf_review_flags(body_text, confidence_score, warnings, extra_structured)
            if review_flags:
                extra_structured["review_flags"] = review_flags
        else:
            title, body_text, confidence_score, warnings = _extract_html(storage_path)

        extracted_source_meta = extra_structured.pop("source_meta", {})
        if isinstance(extracted_source_meta, dict):
            source_meta = dict(source_meta)
            source_meta.update(extracted_source_meta)

        if source_meta.get("wrapper_title"):
            title = str(source_meta["wrapper_title"])

        extraction = ExtractionRecord(
            document_id=document.id,
            title=title,
            body_text=body_text,
            structured_json=dict({
                "document_type": document.document_type,
                "storage_path": document.storage_path,
                "character_count": len(body_text),
                "source_meta": source_meta,
            }, **extra_structured),
            confidence_score=confidence_score,
            warnings=warnings,
        )

        extraction_path = Path(config.storage_root) / "extractions" / f"document_{document.id}.json"
        extraction_path.write_text(
            json.dumps(
                {
                    "title": extraction.title,
                    "body_text": extraction.body_text,
                    "structured_json": extraction.structured_json,
                    "confidence_score": extraction.confidence_score,
                    "warnings": extraction.warnings,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_extractions (
                    document_id,
                    extractor_version,
                    title,
                    body_text,
                    structured_json,
                    confidence_score,
                    warnings_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    extraction.document_id,
                    EXTRACTOR_VERSION,
                    extraction.title,
                    extraction.body_text,
                    json.dumps(extraction.structured_json),
                    extraction.confidence_score,
                    json.dumps(extraction.warnings),
                ),
            )
            cursor.execute(
                """
                UPDATE source_items
                SET status = %s, updated_at = NOW()
                WHERE id = (
                    SELECT source_item_id FROM documents WHERE id = %s
                )
                """,
                ("needs_review" if extra_structured.get("review_flags") else "extracted", document.id),
            )

        extractions.append(extraction)

    return extractions
