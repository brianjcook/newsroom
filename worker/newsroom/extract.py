from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pymysql.connections import Connection

from .config import WorkerConfig
from .documents import DocumentRecord

EXTRACTOR_VERSION = "0.2"


@dataclass(frozen=True)
class ExtractionRecord:
    document_id: int
    title: str
    body_text: str
    structured_json: Dict[str, object]
    confidence_score: float
    warnings: List[str]


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


def _extract_pdf(path: Path) -> Tuple[str, str, float, List[str]]:
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
    return title[:512], body_text, confidence, warnings


def extract_documents(config: WorkerConfig, connection: Connection, documents: List[DocumentRecord]) -> List[ExtractionRecord]:
    Path(config.extractions_dir).mkdir(parents=True, exist_ok=True)
    extractions = []  # type: List[ExtractionRecord]

    for document in documents:
        storage_path = Path(config.storage_root) / document.storage_path
        title = ""
        body_text = ""
        confidence_score = 0.0
        warnings = []  # type: List[str]

        if document.storage_path.lower().endswith(".pdf"):
            title, body_text, confidence_score, warnings = _extract_pdf(storage_path)
        else:
            title, body_text, confidence_score, warnings = _extract_html(storage_path)

        extraction = ExtractionRecord(
            document_id=document.id,
            title=title,
            body_text=body_text,
            structured_json={
                "document_type": document.document_type,
                "storage_path": document.storage_path,
                "character_count": len(body_text),
            },
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
