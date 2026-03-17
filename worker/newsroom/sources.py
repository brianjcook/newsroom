import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pymysql.connections import Connection

from .config import WorkerConfig
from .modeling import parse_agenda_center_date, parse_agenda_center_datetime, slugify


@dataclass(frozen=True)
class DiscoveredItem:
    canonical_url: str
    title: str
    item_type: str
    content_hash: str
    raw_meta_json: str
    published_at: Optional[str]


def _normalize_label(text: str) -> str:
    return " ".join((text or "").split())


def _parse_entry_heading(text: str) -> (Optional[str], Optional[str]):
    normalized = _normalize_label(text)
    if "Posted" not in normalized:
        return parse_agenda_center_date(normalized), None

    before, after = normalized.split("Posted", 1)
    meeting_date = parse_agenda_center_date(before.replace("—", " ").replace("-", " ").strip())
    posted_at = parse_agenda_center_datetime(after.strip())
    return meeting_date, posted_at


def _artifact_item_type(label: str) -> str:
    lowered = label.lower()
    if "minutes" in lowered:
        return "minutes"
    if "agenda" in lowered:
        return "agenda"
    if "packet" in lowered:
        return "packet"
    if "previous version" in lowered:
        return "previous_version"
    if "html" in lowered:
        return "html_view"
    return "reference"


def _register_item(discovered, canonical_url, title, item_type, raw_meta, published_at):
    content_hash = hashlib.sha256(
        "{}|{}|{}|{}".format(
            canonical_url,
            title,
            item_type,
            raw_meta.get("meeting_key") or "",
        ).encode("utf-8")
    ).hexdigest()
    discovered.append(
        DiscoveredItem(
            canonical_url=canonical_url,
            title=title[:512],
            item_type=item_type,
            content_hash=content_hash,
            raw_meta_json=json.dumps(raw_meta),
            published_at=published_at,
        )
    )


def discover_wareham_agenda_center(config: WorkerConfig) -> List[DiscoveredItem]:
    response = requests.get(
        config.agenda_center_url,
        headers={"User-Agent": config.fetch_user_agent},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    discovered = []  # type: List[DiscoveredItem]
    current_body = None
    current_entry_title = None
    current_entry_date = None
    current_posted_at = None

    for node in soup.find_all(["h2", "h3", "a"]):
        node_name = node.name.lower()
        text = _normalize_label(node.get_text(" ", strip=True))

        if node_name == "h2":
            if not text or text.lower() in ("agenda center", "agenda center view current list"):
                continue
            if text.lower().startswith("print"):
                continue
            current_body = text
            current_entry_title = None
            current_entry_date = None
            current_posted_at = None
            continue

        if node_name == "h3":
            current_entry_date, current_posted_at = _parse_entry_heading(text)
            current_entry_title = None
            continue

        href = (node.get("href") or "").strip()
        if not href or not text or current_body is None:
            continue

        lower_href = href.lower()
        lower_text = text.lower()
        if lower_text in ("notify me®", "notify me", "rss") or lower_href.endswith("list.aspx#agendacenter") or lower_href.endswith("rss.aspx#agendacenter"):
            continue
        if "agenda" not in lower_href and "agenda" not in lower_text and "minute" not in lower_href and "minute" not in lower_text and "packet" not in lower_text and "html" not in lower_text and "previous version" not in lower_text:
            continue

        canonical_url = urljoin(config.agenda_center_url, href)

        if current_entry_title is None and "viewfile" in lower_href and "packet=true" not in lower_href:
            current_entry_title = text

        artifact_label = text
        display_title = current_entry_title or text
        item_type = _artifact_item_type(artifact_label)
        if item_type == "reference" and ("viewfile" in lower_href or "html=true" in lower_href):
            item_type = "agenda" if "agenda" in lower_href else "minutes" if "minutes" in lower_href else "reference"

        meeting_key = None
        if current_body and current_entry_date:
            meeting_key = "{}-{}".format(slugify(current_body), current_entry_date)

        raw_meta = {
            "discovered_from": "agenda_center",
            "governing_body": current_body,
            "entry_title": display_title,
            "artifact_label": artifact_label,
            "meeting_date": current_entry_date,
            "posted_at": current_posted_at,
            "meeting_key": meeting_key,
            "anchor_text": text,
        }
        _register_item(
            discovered,
            canonical_url,
            display_title,
            item_type,
            raw_meta,
            current_posted_at,
        )

    unique_by_url = {item.canonical_url: item for item in discovered}
    return list(unique_by_url.values())


def upsert_source_items(connection: Connection, source_id: int, items: Iterable[DiscoveredItem]) -> int:
    discovered_count = 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with connection.cursor() as cursor:
        for item in items:
            cursor.execute(
                """
                SELECT raw_meta_json
                FROM source_items
                WHERE source_id = %s AND canonical_url = %s
                LIMIT 1
                """,
                (source_id, item.canonical_url),
            )
            existing = cursor.fetchone()
            merged_meta = {}
            if existing and existing.get("raw_meta_json"):
                try:
                    current_meta = json.loads(existing["raw_meta_json"])
                    if isinstance(current_meta, dict):
                        merged_meta.update(current_meta)
                except (TypeError, ValueError):
                    pass
            try:
                incoming_meta = json.loads(item.raw_meta_json)
                if isinstance(incoming_meta, dict):
                    merged_meta.update(incoming_meta)
            except (TypeError, ValueError):
                pass

            cursor.execute(
                """
                INSERT INTO source_items (
                    source_id,
                    canonical_url,
                    title,
                    item_type,
                    published_at,
                    first_seen_at,
                    last_seen_at,
                    content_hash,
                    status,
                    raw_meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'discovered', %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    item_type = VALUES(item_type),
                    published_at = COALESCE(VALUES(published_at), published_at),
                    last_seen_at = VALUES(last_seen_at),
                    content_hash = VALUES(content_hash),
                    raw_meta_json = VALUES(raw_meta_json)
                """,
                (
                    source_id,
                    item.canonical_url,
                    item.title,
                    item.item_type,
                    item.published_at,
                    now,
                    now,
                    item.content_hash,
                    json.dumps(merged_meta),
                ),
            )
            discovered_count += 1

    return discovered_count
