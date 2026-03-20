import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pymysql.connections import Connection

from .config import WorkerConfig
from .editorial import score_community_event
from .modeling import slugify


CALENDAR_BASE_URL = "https://www.wareham.gov/calendar.aspx"


@dataclass(frozen=True)
class CalendarEvent:
    external_uid: str
    title: str
    slug: str
    starts_at: str
    ends_at: Optional[str]
    location_name: Optional[str]
    address_text: Optional[str]
    body_name: Optional[str]
    source_url: str
    source_category: Optional[str]
    source_type: str
    description: str
    editorial_score: int
    editorial_signals_json: str
    suggested_coverage_mode: str
    raw_meta_json: str


def _clean_text(value: Optional[str]) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _month_urls() -> List[str]:
    now = datetime.utcnow()
    months = [(now.year, now.month)]
    if now.month == 12:
        months.append((now.year + 1, 1))
    else:
        months.append((now.year, now.month + 1))
    return [
        "{}?month={}&year={}".format(CALENDAR_BASE_URL, month, year)
        for year, month in months
    ]


def _event_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    event_id = query.get("EID")
    if not event_id:
        return None
    return str(event_id[0])


def _source_section(anchor) -> Optional[str]:
    for previous in anchor.previous_elements:
        if getattr(previous, "name", None) == "h2":
            text = _clean_text(previous.get_text(" ", strip=True))
            if text in ("Events", "Meetings Calendar", "Holidays"):
                return text
    return None


def _list_event_links(config: WorkerConfig) -> List[Dict[str, str]]:
    discovered = {}
    for month_url in _month_urls():
        response = requests.get(
            month_url,
            headers={"User-Agent": config.fetch_user_agent},
            timeout=30,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select('a[href*="Calendar.aspx?EID="]'):
            href = anchor.get("href") or ""
            absolute_url = urljoin(CALENDAR_BASE_URL, href)
            event_id = _event_id(absolute_url)
            if not event_id:
                continue

            title = _clean_text(anchor.get_text(" ", strip=True))
            if not title or title.lower() in ("more details", "google", "bing", "home"):
                continue

            existing = discovered.get(event_id) or {}
            if title.lower() == "more details" and existing.get("title"):
                title = existing["title"]

            discovered[event_id] = {
                "external_uid": "wareham-calendar-{}".format(event_id),
                "detail_url": absolute_url,
                "title": title if title.lower() != "more details" else existing.get("title", ""),
                "source_category": _source_section(anchor) or existing.get("source_category"),
            }
    return list(discovered.values())


def _parse_datetime(detail_scope) -> (Optional[str], Optional[str]):
    hidden = detail_scope.select_one('[itemprop="startDate"]')
    start_raw = _clean_text(hidden.get_text(" ", strip=True) if hidden else "")
    start_dt = None
    end_dt = None

    if start_raw:
        try:
            start_dt = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            start_dt = None

    time_text = ""
    for detail in detail_scope.select(".specificDetail"):
        label = _clean_text(detail.select_one(".specificDetailHeader").get_text(" ", strip=True) if detail.select_one(".specificDetailHeader") else "")
        if label.lower().startswith("time"):
            item = detail.select_one(".specificDetailItem")
            time_text = _clean_text(item.get_text(" ", strip=True) if item else "")
            break

    if start_dt and time_text and "-" in time_text:
        end_text = _clean_text(time_text.split("-", 1)[1])
        try:
            parsed_end = datetime.strptime(
                "{} {}".format(start_dt.strftime("%Y-%m-%d"), end_text),
                "%Y-%m-%d %I:%M %p",
            )
            end_dt = parsed_end
        except ValueError:
            end_dt = None

    return (
        start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt else None,
        end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else None,
    )


def _parse_location(detail_scope) -> Dict[str, Optional[str]]:
    location_name = None
    address_text = None

    location_node = detail_scope.select_one('[itemprop="location"] [itemprop="name"]')
    if location_node:
        location_name = _clean_text(location_node.get_text(" ", strip=True))

    address_node = detail_scope.select_one('[itemprop="address"]')
    if address_node:
        address_text = _clean_text(address_node.get_text(" ", strip=True))

    if (not location_name or location_name.lower() == "event location") and address_text:
        location_name = re.split(r"\s+\d", address_text, maxsplit=1)[0].strip(" ,")
        if location_name == "":
            location_name = address_text

    return {"location_name": location_name, "address_text": address_text}


def _parse_description(event_details, title: str, location_name: Optional[str]) -> str:
    blocks = event_details.select(".fr-view")
    for block in blocks:
        raw = block.get_text("\n", strip=True)
        lines = [_clean_text(line) for line in raw.splitlines()]
        filtered = []
        for line in lines:
            if line == "":
                continue
            lower = line.lower()
            if lower in (
                _clean_text(title).lower(),
                "when",
                "location",
                "registered",
                "registration",
                "map",
                "agenda",
            ):
                continue
            if location_name and lower == _clean_text(location_name).lower():
                continue
            if re.match(r"^[A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}$", line):
                continue
            if re.match(r"^\d{1,2}:\d{2}\s+[AP]M(\s*-\s*\d{1,2}:\d{2}\s+[AP]M)?$", line, flags=re.I):
                continue
            filtered.append(line)
        text = _clean_text(" ".join(filtered))
        if len(text) < 30:
            continue
        if text.startswith("Location:"):
            continue
        return text
    return ""


def _infer_source_type(source_category: Optional[str], title: str, description: str) -> str:
    text = " ".join(filter(None, [_clean_text(source_category), _clean_text(title), _clean_text(description)])).lower()
    if (source_category or "").lower() == "events":
        return "community_event"
    if (source_category or "").lower() == "holidays":
        return "holiday"
    if "meeting agenda" in text or (source_category or "").lower() == "meetings calendar":
        return "official_meeting"
    if "metropolitan planning organization" in text or "regional" in text:
        return "regional_public_meeting"
    return "community_event"


def _body_name(title: str, source_type: str) -> Optional[str]:
    cleaned = _clean_text(title)
    if source_type != "official_meeting":
        return None
    cleaned = re.sub(r"\bMeeting Agenda\b.*$", "", cleaned, flags=re.I).strip(" -")
    return cleaned or None


def _fetch_event_detail(config: WorkerConfig, seed: Dict[str, str]) -> Optional[CalendarEvent]:
    response = requests.get(
        seed["detail_url"],
        headers={"User-Agent": config.fetch_user_agent},
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    event_details = soup.select_one(".eventDetails")
    if not event_details:
        return None

    detail_scope = event_details.select_one("#ctl00_ctl00_MainContent_ModuleContent_ctl00_ctl04_eventDetails") or event_details
    title_node = event_details.select_one("h1")
    title = _clean_text(title_node.get_text(" ", strip=True) if title_node else seed.get("title"))
    starts_at, ends_at = _parse_datetime(detail_scope)
    if not starts_at:
        return None

    location = _parse_location(detail_scope)
    description = _parse_description(event_details, title, location["location_name"])
    source_type = _infer_source_type(seed.get("source_category"), title, description)
    body_name = _body_name(title, source_type)
    raw_meta = {
        "detail_url": seed["detail_url"],
        "source_category": seed.get("source_category"),
        "description": description,
        "address_text": location["address_text"],
    }
    scoring = score_community_event(
        {
            "title": title,
            "description": description,
            "starts_at": starts_at,
            "source_category": seed.get("source_category"),
            "source_type": source_type,
        }
    )
    return CalendarEvent(
        external_uid=seed["external_uid"],
        title=title,
        slug=slugify(title)[:191],
        starts_at=starts_at,
        ends_at=ends_at,
        location_name=location["location_name"],
        address_text=location["address_text"],
        body_name=body_name,
        source_url=seed["detail_url"],
        source_category=seed.get("source_category"),
        source_type=source_type,
        description=description,
        editorial_score=int(scoring["score"]),
        editorial_signals_json=json.dumps(scoring["signals"]),
        suggested_coverage_mode=str(scoring["coverage_mode"]),
        raw_meta_json=json.dumps(raw_meta),
    )


def sync_community_calendar(config: WorkerConfig, connection: Connection) -> int:
    seeds = _list_event_links(config)
    synced = 0

    for seed in seeds:
        item = _fetch_event_detail(config, seed)
        if not item:
            continue

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO community_events (
                    external_uid,
                    title,
                    slug,
                    starts_at,
                    ends_at,
                    location_name,
                    address_text,
                    body_name,
                    source_url,
                    source_category,
                    source_type,
                    description,
                    editorial_score,
                    editorial_signals_json,
                    suggested_coverage_mode,
                    topic_tags_json,
                    raw_meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    slug = VALUES(slug),
                    starts_at = VALUES(starts_at),
                    ends_at = VALUES(ends_at),
                    location_name = VALUES(location_name),
                    address_text = VALUES(address_text),
                    body_name = VALUES(body_name),
                    source_url = VALUES(source_url),
                    source_category = VALUES(source_category),
                    source_type = VALUES(source_type),
                    description = VALUES(description),
                    editorial_score = VALUES(editorial_score),
                    editorial_signals_json = VALUES(editorial_signals_json),
                    suggested_coverage_mode = VALUES(suggested_coverage_mode),
                    topic_tags_json = VALUES(topic_tags_json),
                    raw_meta_json = VALUES(raw_meta_json)
                """,
                (
                    item.external_uid,
                    item.title,
                    item.slug,
                    item.starts_at,
                    item.ends_at,
                    item.location_name,
                    item.address_text,
                    item.body_name,
                    item.source_url,
                    item.source_category,
                    item.source_type,
                    item.description,
                    item.editorial_score,
                    item.editorial_signals_json,
                    item.suggested_coverage_mode,
                    json.dumps(score_community_event(
                        {
                            "title": item.title,
                            "description": item.description,
                            "starts_at": item.starts_at,
                            "source_category": item.source_category,
                            "source_type": item.source_type,
                        }
                    )["topics"]),
                    item.raw_meta_json,
                ),
            )
            synced += 1

    return synced
