import hashlib
import html
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
from .modeling import normalize_body_name, parse_agenda_center_date, parse_agenda_center_datetime, slugify


@dataclass(frozen=True)
class DiscoveredItem:
    canonical_url: str
    title: str
    item_type: str
    content_hash: str
    raw_meta_json: str
    published_at: Optional[str]


WAREHAM_POLICE_LOGS_URL = "https://www.wareham.ma.us/DocumentCenter/Index/316"
WAREHAM_POLICE_TREE_URL = "https://www.wareham.ma.us/admin/DocumentCenter/Home/_AjaxLoadingReact?type=0"
WAREHAM_POLICE_DOCS_URL = "https://www.wareham.ma.us/Admin/DocumentCenter/Home/Document_AjaxBinding?renderMode=0&loadSource=7"
BUZZARDS_BAY_COALITION_NEWS_URL = "https://www.savebuzzardsbay.org/news/"
WAREHAM_PERMIT_REPORT_ARCHIVE_URL = "https://www.wareham.gov/Archive.aspx?AMID=63"
WAREHAM_TOWN_MEETING_URL = "https://www.wareham.gov/351/Town-Meeting-Information"
WAREHAM_BIDS_URL = "https://www.wareham.gov/bids.aspx"
WAREHAM_MEDIA_POSTS_URL = "https://www.warehammedia.org/wp-json/wp/v2/posts"
WAREHAM_MEDIA_SEARCH_TERMS = (
    "Select Board",
    "Planning Board",
    "Conservation Commission",
    "Zoning Board of Appeals",
    "School Committee",
    "Sewer Commissioners",
    "Finance Committee",
    "Board of Health",
    "Board of Library Trustees",
    "Board of Assessors",
    "Community Preservation Committee",
)


def _normalize_label(text: str) -> str:
    return " ".join((text or "").split())


def _html_text(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("rendered") or ""
    text = BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)
    return _normalize_label(html.unescape(text))


def _session_with_headers(config: WorkerConfig) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": config.fetch_user_agent})
    return session


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


def _police_log_title(display_name: str) -> str:
    match = re.match(r"^pl(\d{2})(\d{2})(\d{4})$", display_name.strip(), flags=re.IGNORECASE)
    if not match:
        return "Wareham Police Log {}".format(display_name.strip())
    month, day, year = match.groups()
    try:
        stamp = datetime.strptime("{}-{}-{}".format(year, month, day), "%Y-%m-%d")
        return "Wareham Police Log for {} {}, {}".format(stamp.strftime("%B"), stamp.day, stamp.year)
    except ValueError:
        return "Wareham Police Log {}".format(display_name.strip())


def _parse_month_folder_label(label: str) -> Optional[datetime]:
    try:
        return datetime.strptime(label.strip(), "%Y-%m")
    except ValueError:
        return None


def _fetch_police_log_tree(session: requests.Session, folder_id: str, selected_folder: str = "316") -> List[dict]:
    response = session.post(
        WAREHAM_POLICE_TREE_URL,
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
        data=json.dumps(
            {
                "value": str(folder_id),
                "expandTree": str(folder_id) == "316",
                "loadSource": 7,
                "selectedFolder": int(selected_folder),
            }
        ),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("Data") if isinstance(payload, dict) else []
    return data if isinstance(data, list) else []


def _fetch_police_log_documents(session: requests.Session, folder_id: str) -> List[dict]:
    response = session.post(
        WAREHAM_POLICE_DOCS_URL,
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
        data=json.dumps(
            {
                "folderId": int(folder_id),
                "getDocuments": 1,
                "imageRepo": False,
                "renderMode": 0,
                "loadSource": 7,
                "requestingModuleID": 75,
                "searchString": "",
                "pageNumber": 1,
                "rowsPerPage": 100,
                "sortColumn": "DisplayName",
                "sortOrder": 0,
            }
        ),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    documents = payload.get("Documents") if isinstance(payload, dict) else []
    return documents if isinstance(documents, list) else []


def discover_wareham_police_logs(config: WorkerConfig) -> List[DiscoveredItem]:
    session = _session_with_headers(config)
    session.get(WAREHAM_POLICE_LOGS_URL, timeout=30).raise_for_status()

    folder_nodes = _fetch_police_log_tree(session, "316", "316")
    now = datetime.now(timezone.utc)
    current_month_floor = datetime(now.year, now.month, 1)
    recent_folders = []
    for node in folder_nodes:
        label = _normalize_label(str(node.get("Text") or ""))
        if label.lower() == "older" or label == "":
            continue
        folder_month = _parse_month_folder_label(label)
        if not folder_month:
            continue
        month_delta = (current_month_floor.year - folder_month.year) * 12 + (current_month_floor.month - folder_month.month)
        if month_delta < 0 or month_delta > 3:
            continue
        recent_folders.append({"id": str(node.get("Value")), "label": label})

    discovered = []
    for folder in recent_folders:
        for doc in _fetch_police_log_documents(session, folder["id"]):
            display_name = _normalize_label(str(doc.get("DisplayName") or ""))
            if display_name == "" or display_name.lower() == "instructions":
                continue

            canonical_url = urljoin(WAREHAM_POLICE_LOGS_URL, str(doc.get("URL") or ""))
            if canonical_url == WAREHAM_POLICE_LOGS_URL:
                continue

            published_at = parse_agenda_center_datetime(str(doc.get("LastModifiedDateString") or "")) or parse_agenda_center_date(
                str(doc.get("LastModifiedDateString") or "")
            )
            raw_meta = {
                "discovered_from": "wareham_police_logs",
                "source_name": "Wareham Police Logs",
                "folder_label": folder["label"],
                "display_name": display_name,
                "document_id": doc.get("ID"),
                "file_type": doc.get("FileType"),
                "last_uploaded_label": doc.get("LastModifiedDateString"),
                "description": doc.get("Description") or "",
            }
            _register_item(
                discovered,
                canonical_url,
                _police_log_title(display_name),
                "police_log",
                raw_meta,
                published_at,
            )

    unique_by_url = {item.canonical_url: item for item in discovered}
    return list(unique_by_url.values())


def _parse_iso_datetime(value: str) -> Optional[str]:
    value = _normalize_label(value)
    if value == "":
        return None
    for candidate in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            stamp = datetime.strptime(value, candidate)
            return stamp.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _parse_human_datetime(value: str) -> Optional[str]:
    value = _normalize_label(value)
    if value == "":
        return None
    for candidate in ("%B %d, %Y", "%b %d, %Y"):
        try:
            stamp = datetime.strptime(value, candidate)
            return stamp.strftime("%Y-%m-%d 00:00:00")
        except ValueError:
            continue
    return None


def _parse_short_meeting_date(value: str) -> Optional[str]:
    text = _normalize_label(value)
    if text == "":
        return None
    candidates = re.findall(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", text)
    candidates.extend(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text))
    for candidate in candidates:
        for pattern in ("%m-%d-%y", "%m/%d/%y", "%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                stamp = datetime.strptime(candidate, pattern)
                return stamp.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def discover_buzzards_bay_coalition_news(config: WorkerConfig) -> List[DiscoveredItem]:
    session = _session_with_headers(config)
    response = session.get(BUZZARDS_BAY_COALITION_NEWS_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    candidates = {}
    for anchor in soup.select('a[href*="/news/"]'):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        canonical_url = href if href.startswith("http") else urljoin(BUZZARDS_BAY_COALITION_NEWS_URL, href)
        if canonical_url.rstrip("/") == BUZZARDS_BAY_COALITION_NEWS_URL.rstrip("/"):
            continue
        text = _normalize_label(anchor.get_text(" ", strip=True))
        if text == "" or text.lower() == "full story ›":
            continue
        candidates[canonical_url] = {"title": text}

    discovered = []
    for canonical_url, candidate in candidates.items():
        detail_response = session.get(canonical_url, timeout=30)
        detail_response.raise_for_status()
        detail_soup = BeautifulSoup(detail_response.text, "html.parser")

        title = candidate["title"]
        title_node = detail_soup.find("meta", attrs={"property": "og:title"})
        if title_node and title_node.get("content"):
            title = _normalize_label(str(title_node.get("content")))

        excerpt = ""
        excerpt_node = detail_soup.find("meta", attrs={"name": "description"}) or detail_soup.find(
            "meta", attrs={"property": "og:description"}
        )
        if excerpt_node and excerpt_node.get("content"):
            excerpt = _normalize_label(str(excerpt_node.get("content")))

        published_at = None
        time_node = detail_soup.find("meta", attrs={"property": "article:published_time"})
        if time_node and time_node.get("content"):
            published_at = _parse_iso_datetime(str(time_node.get("content")))
        if not published_at:
            published_tag = detail_soup.find("time")
            if published_tag:
                published_at = _parse_human_datetime(published_tag.get_text(" ", strip=True))

        raw_meta = {
            "discovered_from": "buzzards_bay_coalition_news",
            "source_name": "Buzzards Bay Coalition",
            "excerpt": excerpt,
        }
        _register_item(
            discovered,
            canonical_url,
            title,
            "external_article",
            raw_meta,
            published_at,
        )

    unique_by_url = {item.canonical_url: item for item in discovered}
    return list(unique_by_url.values())


def discover_wareham_media_recordings(config: WorkerConfig) -> List[DiscoveredItem]:
    session = _session_with_headers(config)
    discovered = []

    for search_term in WAREHAM_MEDIA_SEARCH_TERMS:
        response = session.get(
            WAREHAM_MEDIA_POSTS_URL,
            params={
                "search": search_term,
                "per_page": 20,
                "orderby": "date",
                "order": "desc",
                "_fields": "id,date,modified,link,title,excerpt",
            },
            timeout=30,
        )
        response.raise_for_status()
        posts = response.json()
        if not isinstance(posts, list):
            continue

        for post in posts:
            if not isinstance(post, dict):
                continue
            canonical_url = _normalize_label(str(post.get("link") or ""))
            title = _html_text(post.get("title"))
            if not canonical_url or not title:
                continue

            body_name = normalize_body_name(title) or normalize_body_name(search_term) or search_term
            if not body_name:
                continue
            meeting_date = _parse_short_meeting_date(title)
            lowered_title = title.lower()
            if meeting_date is None and "meeting" not in lowered_title:
                continue

            recording_posted_at = _parse_iso_datetime(str(post.get("date") or ""))
            excerpt = _html_text(post.get("excerpt"))
            raw_meta = {
                "discovered_from": "wareham_media_recordings",
                "source_name": "Wareham Media",
                "governing_body": body_name,
                "recording_body": body_name,
                "meeting_date": meeting_date,
                "recording_date": meeting_date,
                "recording_posted_at": recording_posted_at,
                "excerpt": excerpt,
                "wordpress_post_id": post.get("id"),
                "context_domain": "meeting_followthrough",
                "publication_guardrail": "context_only",
            }
            if body_name and meeting_date:
                raw_meta["meeting_key"] = "{}-{}".format(slugify(body_name), meeting_date)

            _register_item(
                discovered,
                canonical_url,
                title,
                "meeting_recording",
                raw_meta,
                recording_posted_at,
            )

    unique_by_url = {item.canonical_url: item for item in discovered}
    return list(unique_by_url.values())


def discover_discover_wareham_events(config: WorkerConfig) -> List[DiscoveredItem]:
    return []


def _parse_month_year(value: str) -> Optional[str]:
    cleaned = re.sub(r"\s*\(PDF\)\s*$", "", _normalize_label(value), flags=re.IGNORECASE)
    for candidate in ("%B %Y", "%b %Y"):
        try:
            stamp = datetime.strptime(cleaned, candidate)
            return stamp.strftime("%Y-%m-01 00:00:00")
        except ValueError:
            continue
    return None


def discover_wareham_permit_report_archive(config: WorkerConfig) -> List[DiscoveredItem]:
    session = _session_with_headers(config)
    response = session.get(WAREHAM_PERMIT_REPORT_ARCHIVE_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    discovered = []
    current_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for anchor in soup.select('a[href*="Archive.aspx?ADID="]'):
        href = (anchor.get("href") or "").strip()
        title = _normalize_label(anchor.get_text(" ", strip=True))
        if not href or not title:
            continue
        published_at = _parse_month_year(title)
        if published_at:
            try:
                report_month = datetime.strptime(published_at, "%Y-%m-%d %H:%M:%S")
                month_delta = (current_month.year - report_month.year) * 12 + (current_month.month - report_month.month)
                if month_delta < 0 or month_delta > 18:
                    continue
            except ValueError:
                pass
        raw_meta = {
            "discovered_from": "wareham_permit_report_archive",
            "source_name": "Wareham Permit Report Archive",
            "archive_label": re.sub(r"\s*\(PDF\)\s*$", "", title, flags=re.IGNORECASE),
            "context_domain": "land_use",
            "publication_guardrail": "context_only",
        }
        _register_item(
            discovered,
            urljoin(WAREHAM_PERMIT_REPORT_ARCHIVE_URL, href),
            "Permit Report: {}".format(raw_meta["archive_label"]),
            "permit_report",
            raw_meta,
            published_at,
        )

    unique_by_url = {item.canonical_url: item for item in discovered}
    return list(unique_by_url.values())


def discover_wareham_town_meeting_documents(config: WorkerConfig) -> List[DiscoveredItem]:
    session = _session_with_headers(config)
    response = session.get(WAREHAM_TOWN_MEETING_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    discovered = []
    needles = ("town meeting", "warrant", "finance committee report", "capital plan", "minutes")
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        title = _normalize_label(anchor.get_text(" ", strip=True))
        if not href or not title:
            continue
        lowered = "{} {}".format(title, href).lower()
        if "documentcenter/view" not in lowered:
            continue
        if not any(needle in lowered for needle in needles):
            continue
        raw_meta = {
            "discovered_from": "wareham_town_meeting_documents",
            "source_name": "Wareham Town Meeting Documents",
            "context_domain": "town_meeting",
            "publication_guardrail": "context_only",
        }
        _register_item(
            discovered,
            urljoin(WAREHAM_TOWN_MEETING_URL, href),
            title,
            "town_meeting_record",
            raw_meta,
            _parse_human_datetime(title),
        )

    unique_by_url = {item.canonical_url: item for item in discovered}
    return list(unique_by_url.values())


def discover_wareham_bids_rfps(config: WorkerConfig) -> List[DiscoveredItem]:
    session = _session_with_headers(config)
    response = session.get(WAREHAM_BIDS_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    discovered = []
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        title = _normalize_label(anchor.get_text(" ", strip=True))
        if not href or not title:
            continue
        lowered = "{} {}".format(title, href).lower()
        if not any(token in lowered for token in ("bid", "rfp", "request for proposals", "proposal", "contract")):
            continue
        if "subscribe" in lowered or "list.aspx" in lowered:
            continue
        raw_meta = {
            "discovered_from": "wareham_bids_rfps",
            "source_name": "Wareham Bids and RFPs",
            "context_domain": "procurement",
            "publication_guardrail": "context_only",
        }
        _register_item(
            discovered,
            urljoin(WAREHAM_BIDS_URL, href),
            title,
            "bid_or_rfp",
            raw_meta,
            None,
        )

    unique_by_url = {item.canonical_url: item for item in discovered}
    return list(unique_by_url.values())


def discover_wareham_assessor_reference(config: WorkerConfig) -> List[DiscoveredItem]:
    return []


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
                    status = IF(
                        COALESCE(content_hash, '') <> COALESCE(VALUES(content_hash), ''),
                        'updated',
                        status
                    ),
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
