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

EXTRACTOR_VERSION = "0.2"


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


def _parse_agenda_pdf(body_text: str) -> Dict[str, object]:
    structured = {}  # type: Dict[str, object]
    lines = [_normalize_line(line) for line in body_text.splitlines() if _normalize_line(line)]

    meeting_line = None
    for line in lines[:20]:
        if "marion road" in line.lower() or "room " in line.lower():
            meeting_line = line
            break

    if meeting_line:
        structured["meeting_line"] = meeting_line
        location_match = re.search(r"([0-9:]+\s*[ap]\.?m\.?)\s*[\u2013\u2014•\-\?]+\s*(.+)$", meeting_line, flags=re.IGNORECASE)
        if location_match:
            structured["meeting_time_line"] = location_match.group(1).strip()
            structured["meeting_location_line"] = location_match.group(2).strip()

    sections = []
    current_section = None
    for line in lines:
        section_match = re.match(r"^(\d+)\)\s+(.+)$", line)
        subitem_match = re.match(r"^([a-z]+)\)\s+(.+)$", line, flags=re.IGNORECASE)
        nested_match = re.match(r"^\((\d+)\)\s+(.+)$", line)

        if section_match:
            current_section = {
                "number": int(section_match.group(1)),
                "title": section_match.group(2).strip(),
                "items": [],
            }
            sections.append(current_section)
            continue

        if subitem_match and current_section is not None:
            current_section["items"].append(subitem_match.group(2).strip())
            continue

        if nested_match and current_section is not None and current_section["items"]:
            current_section["items"][-1] = "{}: {}".format(current_section["items"][-1], nested_match.group(2).strip())
            continue

        time_hearing_match = re.match(r"^([0-9:]+\s*[ap]\.?m\.?)\s+(.+)$", line, flags=re.IGNORECASE)
        if time_hearing_match and current_section is not None:
            current_section["items"].append("{} {}".format(time_hearing_match.group(1).strip(), time_hearing_match.group(2).strip()))

    if sections:
        structured["agenda_sections"] = sections

    scored_highlights = []
    for section in sections:
        section_title = section["title"].lower()
        for item in section["items"]:
            lowered = item.lower()
            score = 0
            if "comprehensive wastewater management plan" in lowered:
                score += 100
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
        else:
            title, body_text, confidence_score, warnings = _extract_html(storage_path)

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
                SET status = 'extracted', updated_at = NOW()
                WHERE id = (
                    SELECT source_item_id FROM documents WHERE id = %s
                )
                """,
                (document.id,),
            )

        extractions.append(extraction)

    return extractions
