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
    return re.sub(r"(?<=\w)\s+-\s+(?=\w)", "-", normalized)


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
    return [
        line
        for line in (_normalize_line(line) for line in body_text.splitlines())
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
        "roll call",
        "announcements",
        "adjournment",
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
    )
    return lowered.startswith(procedural_starts)


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
        heading_match = re.match(r"^([IVXLCDM]+)[\.\)]\s+(.+)$", line, flags=re.IGNORECASE)
        section_match = re.match(r"^(\d+)[\.\)]\s+(.+)$", line)
        subitem_match = re.match(r"^([a-z]+)[\.\)]\s+(.+)$", line, flags=re.IGNORECASE)
        nested_match = re.match(r"^\((\d+)\)\s+(.+)$", line)
        roman_match = re.match(r"^([ivxlcdm]+)[\.\)]\s+(.+)$", line, flags=re.IGNORECASE)

        if heading_match:
            current_heading = heading_match.group(2).strip().rstrip(":")
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

        if current_section["items"]:
            _append_item_text(current_section, line)

    if current_section.get("items"):
        sections.append(current_section)

    if sections:
        for section in sections:
            cleaned_items = []
            for item in section.get("items") or []:
                normalized = _normalize_line(str(item))
                if normalized and not _is_procedural_item(normalized):
                    cleaned_items.append(normalized)
            section["items"] = cleaned_items
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
