import json
import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from pymysql.connections import Connection

from .extract import ExtractionRecord
from .modeling import slugify


ADDRESS_PATTERN = re.compile(
    r"\b\d{1,5}(?:-\d{1,5})?\s+"
    r"(?:[A-Z][A-Za-z0-9'.-]*\s+){0,5}"
    r"(?:Road|Rd\.?|Street|St\.?|Avenue|Ave\.?|Highway|Hwy\.?|Drive|Dr\.?|"
    r"Lane|Ln\.?|Way|Boulevard|Blvd\.?|Court|Ct\.?|Circle|Cir\.?|Path|"
    r"Place|Pl\.?|Terrace|Trail|Turnpike|Pike)\b",
    flags=re.IGNORECASE,
)

PROJECT_PATTERNS = (
    "Safe Harbor Marina",
    "River Hawk",
    "Water Wizz",
    "Taco Bell",
    "Follo-Beecher Woods",
    "Little Harbor Golf Course",
    "Marks Cove",
    "Tweedy and Barnes",
    "Douglas S. Westgate Conservation Area",
    "River Walk Conservation Area",
    "WPCF Phase II",
    "Comprehensive Wastewater Management Plan",
)

PUBLIC_SAFETY_SOURCE_SLUGS = {"wareham-police-logs"}
ASSESSOR_SEARCH_URL = "https://gis.vgsi.com/warehamma/Search.aspx"


SOURCE_COLUMN_DEFINITIONS = {
    "automation_mode": "ALTER TABLE sources ADD COLUMN automation_mode VARCHAR(32) NOT NULL DEFAULT 'auto_publish' AFTER parser_key",
    "authority_tier": "ALTER TABLE sources ADD COLUMN authority_tier VARCHAR(32) NOT NULL DEFAULT 'official' AFTER automation_mode",
    "privacy_risk": "ALTER TABLE sources ADD COLUMN privacy_risk VARCHAR(32) NOT NULL DEFAULT 'low' AFTER authority_tier",
    "context_enabled": "ALTER TABLE sources ADD COLUMN context_enabled TINYINT(1) NOT NULL DEFAULT 1 AFTER privacy_risk",
    "auto_publish_allowed": "ALTER TABLE sources ADD COLUMN auto_publish_allowed TINYINT(1) NOT NULL DEFAULT 1 AFTER context_enabled",
    "attribution_note": "ALTER TABLE sources ADD COLUMN attribution_note VARCHAR(255) DEFAULT NULL AFTER auto_publish_allowed",
}


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _parse_json(value: object) -> Dict[str, object]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _table_exists(connection: Connection, table_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES LIKE %s", (table_name,))
        return cursor.fetchone() is not None


def _column_exists(connection: Connection, table_name: str, column_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        return cursor.fetchone() is not None


def context_tables_available(connection: Connection) -> bool:
    return _table_exists(connection, "context_entities") and _table_exists(connection, "source_observations")


def _ensure_source_governance_columns(connection: Connection) -> None:
    if not _table_exists(connection, "sources"):
        return
    with connection.cursor() as cursor:
        for column_name, statement in SOURCE_COLUMN_DEFINITIONS.items():
            if not _column_exists(connection, "sources", column_name):
                cursor.execute(statement)


def _ensure_context_tables(connection: Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS context_entities (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                municipality_id BIGINT UNSIGNED DEFAULT NULL,
                entity_type VARCHAR(64) NOT NULL,
                canonical_name VARCHAR(255) NOT NULL,
                normalized_key VARCHAR(191) NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                meta_json JSON DEFAULT NULL,
                first_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uniq_context_entities_type_key (entity_type, normalized_key),
                KEY idx_context_entities_municipality (municipality_id),
                CONSTRAINT fk_context_entities_municipality
                    FOREIGN KEY (municipality_id) REFERENCES municipalities (id)
                    ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS source_observations (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                source_item_id BIGINT UNSIGNED NOT NULL,
                document_id BIGINT UNSIGNED DEFAULT NULL,
                entity_id BIGINT UNSIGNED DEFAULT NULL,
                observation_type VARCHAR(80) NOT NULL,
                observation_label VARCHAR(255) NOT NULL,
                observation_value TEXT DEFAULT NULL,
                observation_json JSON DEFAULT NULL,
                observed_at DATETIME DEFAULT NULL,
                source_url VARCHAR(512) NOT NULL,
                confidence_score DECIMAL(5,2) DEFAULT NULL,
                is_public_context TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uniq_source_observation (
                    source_item_id,
                    entity_id,
                    observation_type(32),
                    observation_label(48),
                    source_url(64)
                ),
                KEY idx_source_observations_entity (entity_id),
                KEY idx_source_observations_type (observation_type),
                KEY idx_source_observations_public (is_public_context),
                CONSTRAINT fk_source_observations_source_item
                    FOREIGN KEY (source_item_id) REFERENCES source_items (id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_source_observations_document
                    FOREIGN KEY (document_id) REFERENCES documents (id)
                    ON DELETE SET NULL,
                CONSTRAINT fk_source_observations_entity
                    FOREIGN KEY (entity_id) REFERENCES context_entities (id)
                    ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS story_context_links (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                story_id BIGINT UNSIGNED NOT NULL,
                entity_id BIGINT UNSIGNED NOT NULL,
                relevance_score INT NOT NULL DEFAULT 0,
                context_reason VARCHAR(255) DEFAULT NULL,
                source_basis_json JSON DEFAULT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uniq_story_context_entity (story_id, entity_id),
                KEY idx_story_context_entity (entity_id),
                KEY idx_story_context_score (relevance_score),
                CONSTRAINT fk_story_context_story
                    FOREIGN KEY (story_id) REFERENCES stories (id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_story_context_entity
                    FOREIGN KEY (entity_id) REFERENCES context_entities (id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )


def _seed_context_sources(connection: Connection) -> None:
    source_rows = [
        {
            "name": "Wareham Permit Report Archive",
            "slug": "wareham-permit-report-archive",
            "source_type": "official_documents",
            "base_url": "https://www.wareham.gov",
            "list_url": "https://www.wareham.gov/Archive.aspx?AMID=63",
            "parser_key": "wareham_permit_report_archive",
            "automation_mode": "context_only",
            "authority_tier": "official",
            "privacy_risk": "low",
            "context_enabled": 1,
            "auto_publish_allowed": 0,
            "attribution_note": "Official monthly permit reports; enrich land-use stories but do not auto-publish standalone stories.",
            "poll_frequency": "daily",
            "is_active": 1,
        },
        {
            "name": "Wareham Town Meeting Documents",
            "slug": "wareham-town-meeting-documents",
            "source_type": "official_documents",
            "base_url": "https://www.wareham.gov",
            "list_url": "https://www.wareham.gov/351/Town-Meeting-Information",
            "parser_key": "wareham_town_meeting_documents",
            "automation_mode": "context_only",
            "authority_tier": "official",
            "privacy_risk": "low",
            "context_enabled": 1,
            "auto_publish_allowed": 0,
            "attribution_note": "Official Town Meeting warrants, reports, capital plans, and minutes for context.",
            "poll_frequency": "daily",
            "is_active": 1,
        },
        {
            "name": "Wareham Bids and RFPs",
            "slug": "wareham-bids-rfps",
            "source_type": "official_documents",
            "base_url": "https://www.wareham.gov",
            "list_url": "https://www.wareham.gov/bids.aspx",
            "parser_key": "wareham_bids_rfps",
            "automation_mode": "context_only",
            "authority_tier": "official",
            "privacy_risk": "low",
            "context_enabled": 1,
            "auto_publish_allowed": 0,
            "attribution_note": "Official procurement postings; enrich budget, infrastructure, and contract stories.",
            "poll_frequency": "daily",
            "is_active": 1,
        },
        {
            "name": "Wareham Assessor Reference",
            "slug": "wareham-assessor-reference",
            "source_type": "official_reference",
            "base_url": "https://gis.vgsi.com/warehamma/",
            "list_url": "https://gis.vgsi.com/warehamma/",
            "parser_key": "wareham_assessor_reference",
            "automation_mode": "context_reference",
            "authority_tier": "official",
            "privacy_risk": "low",
            "context_enabled": 1,
            "auto_publish_allowed": 0,
            "attribution_note": "Official assessor reference used for generated parcel and property-record links.",
            "poll_frequency": "weekly",
            "is_active": 1,
        },
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE sources
            SET automation_mode = 'auto_publish',
                authority_tier = 'official',
                privacy_risk = 'low',
                context_enabled = 1,
                auto_publish_allowed = 1,
                attribution_note = 'Official Town of Wareham agenda and minutes records.'
            WHERE slug = 'wareham-agenda-center'
            """
        )
        cursor.execute(
            """
            UPDATE sources
            SET automation_mode = 'guarded_context',
                authority_tier = 'official',
                privacy_risk = 'high',
                context_enabled = 1,
                auto_publish_allowed = 0,
                attribution_note = 'Official public-safety logs; never auto-publish individual-log stories.'
            WHERE slug = 'wareham-police-logs'
            """
        )
        cursor.execute(
            """
            UPDATE sources
            SET automation_mode = 'context_only',
                authority_tier = 'specialized',
                privacy_risk = 'low',
                context_enabled = 1,
                auto_publish_allowed = 0,
                attribution_note = 'Outside environmental context source; use for attribution and context only.'
            WHERE slug = 'buzzards-bay-coalition-news'
            """
        )
        cursor.execute(
            """
            UPDATE sources
            SET automation_mode = 'calendar_sync',
                authority_tier = 'community',
                privacy_risk = 'low',
                context_enabled = 1,
                auto_publish_allowed = 1,
                attribution_note = 'Community event listings synced into the public calendar.'
            WHERE slug = 'discover-wareham-events'
            """
        )
        for row in source_rows:
            cursor.execute(
                """
                INSERT INTO sources (
                    name,
                    slug,
                    source_type,
                    base_url,
                    list_url,
                    parser_key,
                    automation_mode,
                    authority_tier,
                    privacy_risk,
                    context_enabled,
                    auto_publish_allowed,
                    attribution_note,
                    poll_frequency,
                    is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    source_type = VALUES(source_type),
                    base_url = VALUES(base_url),
                    list_url = VALUES(list_url),
                    parser_key = VALUES(parser_key),
                    automation_mode = VALUES(automation_mode),
                    authority_tier = VALUES(authority_tier),
                    privacy_risk = VALUES(privacy_risk),
                    context_enabled = VALUES(context_enabled),
                    auto_publish_allowed = VALUES(auto_publish_allowed),
                    attribution_note = VALUES(attribution_note),
                    poll_frequency = VALUES(poll_frequency),
                    is_active = VALUES(is_active)
                """,
                (
                    row["name"],
                    row["slug"],
                    row["source_type"],
                    row["base_url"],
                    row["list_url"],
                    row["parser_key"],
                    row["automation_mode"],
                    row["authority_tier"],
                    row["privacy_risk"],
                    row["context_enabled"],
                    row["auto_publish_allowed"],
                    row["attribution_note"],
                    row["poll_frequency"],
                    row["is_active"],
                ),
            )


def ensure_context_schema(connection: Connection) -> None:
    _ensure_source_governance_columns(connection)
    _ensure_context_tables(connection)
    _seed_context_sources(connection)


def _wareham_municipality_id(connection: Connection) -> Optional[int]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM municipalities WHERE slug = %s LIMIT 1", ("wareham-ma",))
        row = cursor.fetchone()
        return int(row["id"]) if row else None


def _normalize_address(value: str) -> str:
    cleaned = _clean_text(value)
    cleaned = cleaned.replace("Cran Hwy", "Cranberry Highway")
    cleaned = cleaned.replace("Cranberry Hwy", "Cranberry Highway")
    cleaned = cleaned.replace("Rte.", "Route")
    cleaned = cleaned.replace("Rt.", "Route")
    suffixes = {
        r"\bRd\.?\b": "Road",
        r"\bSt\.?\b": "Street",
        r"\bAve\.?\b": "Avenue",
        r"\bHwy\.?\b": "Highway",
        r"\bDr\.?\b": "Drive",
        r"\bLn\.?\b": "Lane",
        r"\bBlvd\.?\b": "Boulevard",
        r"\bCt\.?\b": "Court",
        r"\bCir\.?\b": "Circle",
        r"\bPl\.?\b": "Place",
    }
    for pattern, replacement in suffixes.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*,?\s*(Wareham|West Wareham|East Wareham|Onset),?\s*MA(?:\s*\d{5})?.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    return cleaned


def _entity_key(entity_type: str, value: str) -> str:
    if entity_type == "address":
        value = _normalize_address(value)
    key = slugify(value)
    return key[:191] if key else ""


def _assessor_meta(entity_type: str, value: str) -> Dict[str, object]:
    if entity_type != "address":
        return {}
    address = _normalize_address(value)
    match = re.match(r"^(\d{1,5}(?:-\d{1,5})?)\s+(.+)$", address)
    meta = {"assessor_search_url": ASSESSOR_SEARCH_URL}
    if match:
        meta["street_number"] = match.group(1)
        meta["street_name"] = match.group(2)
    return meta


def _upsert_entity(connection: Connection, entity_type: str, display_name: str) -> Optional[int]:
    display = _normalize_address(display_name) if entity_type == "address" else _clean_text(display_name)
    if not display:
        return None
    key = _entity_key(entity_type, display)
    if not key:
        return None

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO context_entities (
                municipality_id,
                entity_type,
                canonical_name,
                normalized_key,
                display_name,
                meta_json
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                canonical_name = VALUES(canonical_name),
                display_name = VALUES(display_name),
                meta_json = VALUES(meta_json)
            """,
            (
                _wareham_municipality_id(connection),
                entity_type,
                display,
                key,
                display,
                json.dumps(_assessor_meta(entity_type, display)),
            ),
        )
        cursor.execute(
            "SELECT id FROM context_entities WHERE entity_type = %s AND normalized_key = %s LIMIT 1",
            (entity_type, key),
        )
        row = cursor.fetchone()
        return int(row["id"]) if row else None


def _extract_entities(text: str) -> List[Tuple[str, str]]:
    entities = []  # type: List[Tuple[str, str]]
    seen = set()

    for match in ADDRESS_PATTERN.finditer(text or ""):
        address = _normalize_address(match.group(0))
        if len(address) < 8:
            continue
        key = ("address", _entity_key("address", address))
        if key[1] and key not in seen:
            seen.add(key)
            entities.append(("address", address))

    lowered = (text or "").lower()
    for project in PROJECT_PATTERNS:
        if project.lower() in lowered:
            key = ("project", _entity_key("project", project))
            if key[1] and key not in seen:
                seen.add(key)
                entities.append(("project", project))

    return entities


def _sentences_for_entity(text: str, entity_name: str, max_items: int = 3) -> List[str]:
    normalized_text = re.sub(r"\s+", " ", text or "")
    parts = re.split(r"(?<=[.;:])\s+|\n+", normalized_text)
    matches = []
    needle = entity_name.lower()
    compact_needle = re.sub(r"\W+", "", needle)
    for part in parts:
        clean = _clean_text(part).strip(" -")
        if len(clean) < 12 or len(clean) > 360:
            continue
        compact = re.sub(r"\W+", "", clean.lower())
        if needle in clean.lower() or (compact_needle and compact_needle in compact):
            matches.append(clean)
        if len(matches) >= max_items:
            break
    return matches


def _observation_type(item_type: str, source_slug: str, title: str) -> str:
    text = " ".join([item_type, source_slug, title]).lower()
    if "permit" in text:
        return "permit_report"
    if "town-meeting" in source_slug or "town meeting" in text or "warrant" in text:
        return "town_meeting_record"
    if "bid" in text or "rfp" in text:
        return "bid_or_rfp"
    if "agenda" in text or "minutes" in text or source_slug == "wareham-agenda-center":
        return "meeting_record"
    if "buzzards" in source_slug:
        return "environment_context"
    if "police" in source_slug:
        return "public_safety_record"
    return "public_record"


def _is_public_context(source_slug: str, observation_type: str, automation_mode: str) -> bool:
    if source_slug in PUBLIC_SAFETY_SOURCE_SLUGS:
        return False
    if observation_type == "public_safety_record":
        return False
    return automation_mode not in ("guarded_context", "private_context")


def _observed_at(raw_meta: Dict[str, object], published_at: object) -> Optional[str]:
    for key in ("posted_at", "published_at", "meeting_date"):
        value = raw_meta.get(key)
        if value:
            return str(value)
    if published_at:
        try:
            return published_at.strftime("%Y-%m-%d %H:%M:%S")
        except AttributeError:
            return str(published_at)
    return None


def _source_row_for_document(connection: Connection, document_id: int) -> Optional[Dict[str, object]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                d.id AS document_id,
                d.document_url,
                si.id AS source_item_id,
                si.title,
                si.item_type,
                si.canonical_url,
                si.raw_meta_json,
                si.published_at,
                s.slug AS source_slug,
                s.name AS source_name,
                COALESCE(s.automation_mode, 'auto_publish') AS automation_mode,
                COALESCE(s.context_enabled, 1) AS context_enabled
            FROM documents d
            INNER JOIN source_items si ON si.id = d.source_item_id
            INNER JOIN sources s ON s.id = si.source_id
            WHERE d.id = %s
            LIMIT 1
            """,
            (document_id,),
        )
        return cursor.fetchone()


def _upsert_observation(
    connection: Connection,
    row: Dict[str, object],
    entity_id: Optional[int],
    observation_type: str,
    label: str,
    value: str,
    observed_at: Optional[str],
    is_public_context: bool,
    confidence_score: Optional[float],
) -> None:
    source_url = str(row.get("document_url") or row.get("canonical_url") or "")
    payload = {
        "source_slug": row.get("source_slug"),
        "source_name": row.get("source_name"),
        "automation_mode": row.get("automation_mode"),
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO source_observations (
                source_item_id,
                document_id,
                entity_id,
                observation_type,
                observation_label,
                observation_value,
                observation_json,
                observed_at,
                source_url,
                confidence_score,
                is_public_context
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                observation_value = VALUES(observation_value),
                observation_json = VALUES(observation_json),
                observed_at = COALESCE(VALUES(observed_at), observed_at),
                confidence_score = VALUES(confidence_score),
                is_public_context = VALUES(is_public_context),
                updated_at = NOW()
            """,
            (
                int(row["source_item_id"]),
                int(row["document_id"]),
                entity_id,
                observation_type,
                label[:255],
                value,
                json.dumps(payload),
                observed_at,
                source_url,
                confidence_score,
                1 if is_public_context else 0,
            ),
        )


def sync_context_observations(connection: Connection, extractions: Sequence[ExtractionRecord]) -> int:
    if not extractions or not context_tables_available(connection):
        return 0

    synced = 0
    for extraction in extractions:
        row = _source_row_for_document(connection, extraction.document_id)
        if not row or not int(row.get("context_enabled") or 0):
            continue

        raw_meta = _parse_json(row.get("raw_meta_json"))
        source_slug = str(row.get("source_slug") or "")
        automation_mode = str(row.get("automation_mode") or "auto_publish")
        title = _clean_text(row.get("title") or extraction.title)
        text = "\n".join(
            [
                title,
                _clean_text(raw_meta.get("entry_title")),
                _clean_text(raw_meta.get("archive_label")),
                extraction.title,
                extraction.body_text or "",
            ]
        )
        entities = _extract_entities(text)
        if not entities:
            continue

        observation_type = _observation_type(str(row.get("item_type") or ""), source_slug, title)
        public_context = _is_public_context(source_slug, observation_type, automation_mode)
        observed = _observed_at(raw_meta, row.get("published_at"))
        label = title or str(row.get("source_name") or "Public record")

        for entity_type, display_name in entities:
            entity_id = _upsert_entity(connection, entity_type, display_name)
            if entity_id is None:
                continue
            snippets = _sentences_for_entity(text, display_name)
            value = " ".join(snippets) if snippets else display_name
            _upsert_observation(
                connection,
                row,
                entity_id,
                observation_type,
                label,
                value[:1400],
                observed,
                public_context,
                float(extraction.confidence_score or 0.0),
            )
            synced += 1

        if automation_mode in ("context_only", "guarded_context", "context_reference"):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE source_items SET status = 'context_indexed', updated_at = NOW() WHERE id = %s",
                    (int(row["source_item_id"]),),
                )

    return synced


def _story_rows(connection: Connection) -> Iterable[Dict[str, object]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                headline,
                dek,
                summary,
                body_text,
                published_at,
                topic_tags_json
            FROM stories
            WHERE publish_status = 'published'
            """
        )
        return cursor.fetchall()


def sync_story_context_links(connection: Connection) -> int:
    if not context_tables_available(connection) or not _table_exists(connection, "story_context_links"):
        return 0

    synced = 0
    for story in _story_rows(connection):
        text = "\n".join(
            [
                _clean_text(story.get("headline")),
                _clean_text(story.get("dek")),
                _clean_text(story.get("summary")),
                _clean_text(story.get("body_text")),
            ]
        )
        entities = _extract_entities(text)
        if not entities:
            continue

        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM story_context_links WHERE story_id = %s", (int(story["id"]),))

        for entity_type, display_name in entities:
            entity_id = _upsert_entity(connection, entity_type, display_name)
            if entity_id is None:
                continue
            headline_text = " ".join([_clean_text(story.get("headline")), _clean_text(story.get("dek"))]).lower()
            relevance = 85 if display_name.lower() in headline_text else 60
            reason = "Mentioned in story headline or dek" if relevance >= 80 else "Mentioned in story text"
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO story_context_links (
                        story_id,
                        entity_id,
                        relevance_score,
                        context_reason,
                        source_basis_json
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        relevance_score = VALUES(relevance_score),
                        context_reason = VALUES(context_reason),
                        source_basis_json = VALUES(source_basis_json),
                        updated_at = NOW()
                    """,
                    (
                        int(story["id"]),
                        entity_id,
                        relevance,
                        reason,
                        json.dumps({"matched": display_name, "entity_type": entity_type}),
                    ),
                )
                synced += 1

    return synced
