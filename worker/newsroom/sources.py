from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pymysql.connections import Connection

from .config import WorkerConfig


@dataclass(frozen=True)
class DiscoveredItem:
    canonical_url: str
    title: str
    item_type: str
    content_hash: str
    raw_meta_json: str


def discover_wareham_agenda_center(config: WorkerConfig) -> list[DiscoveredItem]:
    response = requests.get(
        config.agenda_center_url,
        headers={"User-Agent": config.fetch_user_agent},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    discovered: list[DiscoveredItem] = []

    for link in soup.select("a[href]"):
        href = (link.get("href") or "").strip()
        text = " ".join(link.get_text(" ", strip=True).split())
        if not href or not text:
            continue

        lower_href = href.lower()
        lower_text = text.lower()
        if "agenda" not in lower_href and "agenda" not in lower_text and "minute" not in lower_href and "minute" not in lower_text:
            continue

        canonical_url = urljoin(config.agenda_center_url, href)
        if "minute" in lower_href or "minute" in lower_text:
            item_type = "minutes_pdf" if lower_href.endswith(".pdf") else "meeting_page"
        else:
            item_type = "agenda_pdf" if lower_href.endswith(".pdf") else "meeting_page"

        content_hash = hashlib.sha256(f"{canonical_url}|{text}|{item_type}".encode("utf-8")).hexdigest()
        raw_meta_json = json.dumps(
            {
                "discovered_from": "agenda_center",
                "anchor_text": text,
            }
        )
        discovered.append(
            DiscoveredItem(
                canonical_url=canonical_url,
                title=text[:512],
                item_type=item_type,
                content_hash=content_hash,
                raw_meta_json=raw_meta_json,
            )
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
                INSERT INTO source_items (
                    source_id,
                    canonical_url,
                    title,
                    item_type,
                    first_seen_at,
                    last_seen_at,
                    content_hash,
                    status,
                    raw_meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'discovered', %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    item_type = VALUES(item_type),
                    last_seen_at = VALUES(last_seen_at),
                    content_hash = VALUES(content_hash),
                    raw_meta_json = VALUES(raw_meta_json)
                """,
                (
                    source_id,
                    item.canonical_url,
                    item.title,
                    item.item_type,
                    now,
                    now,
                    item.content_hash,
                    item.raw_meta_json,
                ),
            )
            discovered_count += 1

    return discovered_count
