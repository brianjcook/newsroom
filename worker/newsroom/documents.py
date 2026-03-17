import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from pymysql.connections import Connection

from .config import WorkerConfig
from .modeling import parse_source_meta


@dataclass(frozen=True)
class SourceItemRecord:
    id: int
    canonical_url: str
    title: str
    item_type: str
    raw_meta_json: Optional[str]


@dataclass(frozen=True)
class DocumentRecord:
    id: int
    source_item_id: int
    document_url: str
    document_type: str
    mime_type: Optional[str]
    storage_path: str


def _url_with_html_true(url: str) -> str:
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["html"] = "true"
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(params), parsed.fragment))


def _looks_like_agenda_wrapper(url: str) -> bool:
    lowered = url.lower()
    return "/agendacenter/viewfile/agenda/" in lowered or "/agendacenter/viewfile/minutes/" in lowered


def _extract_remote_fields(desc_lines: List[str]) -> Dict[str, object]:
    metadata = {}
    phone_numbers = []  # type: List[str]

    for line in desc_lines:
        lowered = line.lower()
        if "to join remotely:" in lowered:
            metadata["remote_join_url"] = line.split(":", 1)[1].strip()
        elif "webinar id:" in lowered:
            metadata["remote_webinar_id"] = line.split(":", 1)[1].strip()
        elif "passcode:" in lowered:
            metadata["remote_passcode"] = line.split(":", 1)[1].strip()
        elif "one tap mobile:" in lowered:
            phone_numbers.extend(re.findall(r"\+\d{10,}", line))

    if phone_numbers:
        metadata["remote_phone_numbers"] = phone_numbers
    return metadata


def _parse_wrapper_html(base_url: str, html: str) -> Dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    wrapper = {}  # type: Dict[str, object]

    title_node = soup.select_one("h1.title")
    if title_node:
        wrapper["wrapper_title"] = " ".join(title_node.get_text(" ", strip=True).split())

    time_node = soup.select_one("span.time")
    if time_node:
        wrapper["wrapper_time_text"] = " ".join(time_node.get_text(" ", strip=True).split())

    desc_lines = [
        " ".join(node.get_text(" ", strip=True).split())
        for node in soup.select("div.desc p")
        if node.get_text(" ", strip=True)
    ]
    if desc_lines:
        wrapper["wrapper_desc_lines"] = desc_lines
        wrapper.update(_extract_remote_fields(desc_lines))

    document_links = []
    for link in soup.select("div.documents a.file[href]"):
        href = link.get("href", "").strip()
        if not href:
            continue
        label = " ".join(link.get_text(" ", strip=True).split())
        document_links.append(
            {
                "label": label,
                "url": urljoin(base_url, href),
            }
        )

    if document_links:
        wrapper["resolved_documents"] = document_links
        wrapper["resolved_document_url"] = document_links[0]["url"]
        wrapper["resolved_document_label"] = document_links[0]["label"]

    return wrapper


def _resolve_source_document(config: WorkerConfig, item: SourceItemRecord) -> Dict[str, object]:
    session = requests.Session()
    session.headers.update({"User-Agent": config.fetch_user_agent})
    resolved = {
        "fetch_url": item.canonical_url,
        "wrapper_meta": {},
        "response": None,
    }  # type: Dict[str, object]

    if _looks_like_agenda_wrapper(item.canonical_url):
        wrapper_url = item.canonical_url if "html=true" in item.canonical_url.lower() else _url_with_html_true(item.canonical_url)
        wrapper_response = session.get(wrapper_url, timeout=45)
        wrapper_response.raise_for_status()
        if "html" in (wrapper_response.headers.get("Content-Type", "").lower()):
            wrapper_meta = _parse_wrapper_html(item.canonical_url, wrapper_response.text)
            resolved["wrapper_meta"] = wrapper_meta
            if wrapper_meta.get("resolved_document_url"):
                resolved["fetch_url"] = str(wrapper_meta["resolved_document_url"])

    response = session.get(str(resolved["fetch_url"]), timeout=45)
    response.raise_for_status()
    resolved["response"] = response
    return resolved


def pending_source_items(connection: Connection) -> List[SourceItemRecord]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, canonical_url, COALESCE(title, '') AS title, item_type, raw_meta_json
            FROM source_items
            WHERE status IN ('discovered', 'updated')
            ORDER BY id ASC
            """
        )
        rows = cursor.fetchall()

    return [
        SourceItemRecord(
            id=int(row["id"]),
            canonical_url=row["canonical_url"],
            title=row["title"],
            item_type=row["item_type"],
            raw_meta_json=row["raw_meta_json"],
        )
        for row in rows
    ]


def _extension_from_url(url: str, mime_type: Optional[str]) -> str:
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return ".pdf"
    if path.endswith(".html") or path.endswith(".htm"):
        return ".html"
    if mime_type:
        if "pdf" in mime_type:
            return ".pdf"
        if "html" in mime_type:
            return ".html"
    return ".bin"


def fetch_documents(config: WorkerConfig, connection: Connection, items: List[SourceItemRecord]) -> List[DocumentRecord]:
    Path(config.documents_dir).mkdir(parents=True, exist_ok=True)
    documents = []  # type: List[DocumentRecord]

    for item in items:
        resolved = _resolve_source_document(config, item)
        response = resolved["response"]
        wrapper_meta = resolved["wrapper_meta"]

        mime_type = response.headers.get("Content-Type", "").split(";")[0].strip() or None
        fetch_url = str(resolved["fetch_url"])
        file_extension = _extension_from_url(fetch_url, mime_type)
        sha256 = hashlib.sha256(response.content).hexdigest()
        relative_path = f"documents/source_item_{item.id}_{sha256[:16]}{file_extension}"
        target_path = Path(config.storage_root) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(response.content)

        source_meta = parse_source_meta(item.raw_meta_json)
        if wrapper_meta:
            source_meta.update(wrapper_meta)
            source_meta["resolved_via_wrapper"] = True

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO documents (
                    source_item_id,
                    document_url,
                    document_type,
                    mime_type,
                    storage_path,
                    sha256,
                    fetched_at,
                    http_status
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                ON DUPLICATE KEY UPDATE
                    document_type = VALUES(document_type),
                    mime_type = VALUES(mime_type),
                    storage_path = VALUES(storage_path),
                    sha256 = VALUES(sha256),
                    fetched_at = VALUES(fetched_at),
                    http_status = VALUES(http_status)
                """,
                (
                    item.id,
                    fetch_url,
                    item.item_type,
                    mime_type,
                    relative_path.replace("\\", "/"),
                    sha256,
                    response.status_code,
                ),
            )
            cursor.execute(
                """
                SELECT id, source_item_id, document_url, document_type, mime_type, storage_path
                FROM documents
                WHERE source_item_id = %s AND document_url = %s
                LIMIT 1
                """,
                (item.id, fetch_url),
            )
            row = cursor.fetchone()
            cursor.execute(
                "UPDATE source_items SET status = 'fetched', raw_meta_json = %s, updated_at = NOW() WHERE id = %s",
                (json.dumps(source_meta), item.id),
            )

        if row:
            documents.append(
                DocumentRecord(
                    id=int(row["id"]),
                    source_item_id=int(row["source_item_id"]),
                    document_url=row["document_url"],
                    document_type=row["document_type"],
                    mime_type=row["mime_type"],
                    storage_path=row["storage_path"],
                )
            )

    return documents
