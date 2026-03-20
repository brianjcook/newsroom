<?php

declare(strict_types=1);

require_once __DIR__ . '/db.php';

function newsroom_body_signal(?string $bodyName): array
{
    $name = trim((string) $bodyName);
    $palette = [
        ['bg' => '#eadfd1', 'fg' => '#53341d', 'border' => '#b17e45'],
        ['bg' => '#dbe7dc', 'fg' => '#214433', 'border' => '#5b8f73'],
        ['bg' => '#dfe3f1', 'fg' => '#283457', 'border' => '#6d7fba'],
        ['bg' => '#efe0df', 'fg' => '#5a2a28', 'border' => '#bd766d'],
        ['bg' => '#e7e0f0', 'fg' => '#47305c', 'border' => '#8c6bb0'],
        ['bg' => '#f0e8d7', 'fg' => '#5f4420', 'border' => '#c39748'],
        ['bg' => '#dae9ea', 'fg' => '#1f4850', 'border' => '#5c98a0'],
        ['bg' => '#ece2d4', 'fg' => '#5f3825', 'border' => '#c48b62'],
        ['bg' => '#e1e9d9', 'fg' => '#3c5327', 'border' => '#7e9d57'],
        ['bg' => '#e8dde8', 'fg' => '#5a355a', 'border' => '#9c6b9d'],
    ];

    if ($name === '') {
        return [
            'name' => 'Town Meeting',
            'slug' => 'town-meeting',
            'bg' => '#ece4d8',
            'fg' => '#47362b',
            'border' => '#a98767',
        ];
    }

    $index = abs(crc32(strtolower($name))) % count($palette);
    $slug = preg_replace('/[^a-z0-9]+/', '-', strtolower($name));
    $slug = trim((string) $slug, '-');

    return array_merge(
        [
            'name' => $name,
            'slug' => $slug !== '' ? $slug : 'body',
        ],
        $palette[$index]
    );
}

function newsroom_parse_json($value): array
{
    if (is_array($value)) {
        return $value;
    }

    if (!is_string($value) || $value === '') {
        return [];
    }

    $decoded = json_decode($value, true);
    return is_array($decoded) ? $decoded : [];
}

function newsroom_format_story_type(string $storyType): string
{
    return ucwords(str_replace('_', ' ', $storyType));
}

function newsroom_display_location(?string $locationName): ?string
{
    $location = trim((string) $locationName);
    if ($location === '') {
        return null;
    }

    if (strtoupper($location) === $location) {
        $location = ucwords(strtolower($location));
        $location = str_replace(['Ma ', 'Rm ', 'Po Box '], ['MA ', 'Rm. ', 'PO Box '], $location);
        $location = preg_replace('/\bMa\b/', 'MA', $location);
        $location = preg_replace('/\bFy(\d+)/', 'FY$1', $location);
    }

    return newsroom_normalize_street_types((string) preg_replace('/\s+/', ' ', $location));
}

function newsroom_normalize_street_types(string $value): string
{
    $value = trim(preg_replace('/\s+/', ' ', $value));
    if ($value === '') {
        return '';
    }

    $patterns = [
        '/\bRd\.?(?=\s|,|$)/i' => 'Road',
        '/\bAve\.?(?=\s|,|$)/i' => 'Avenue',
        '/\bHwy\.?(?=\s|,|$)/i' => 'Highway',
        '/\bLn\.?(?=\s|,|$)/i' => 'Lane',
        '/\bBlvd\.?(?=\s|,|$)/i' => 'Boulevard',
        '/\bSt\.?(?=\s|,|$)/i' => 'Street',
        '/\bDr\.?(?=\s|,|$)/i' => 'Drive',
    ];

    $value = (string) preg_replace(array_keys($patterns), array_values($patterns), $value);
    $value = (string) preg_replace('/\b(Road|Avenue|Highway|Lane|Boulevard|Street|Drive)\.(?=\s|,|$)/i', '$1', $value);
    return trim($value, " ,.;:-");
}

function newsroom_format_meeting_datetime(?string $date, ?string $time, string $fallback = ''): string
{
    if (!$date) {
        return $fallback;
    }

    $stamp = trim($date . ' ' . ($time ?: '00:00:00'));
    $parsed = strtotime($stamp);
    if ($parsed === false) {
        return $fallback ?: $date;
    }

    if ($time && $time !== '00:00:00') {
        return date('F j, Y g:i A', $parsed);
    }

    return date('F j, Y', $parsed);
}

function newsroom_google_maps_url(?string $locationName): ?string
{
    $location = trim((string) $locationName);
    if ($location === '') {
        return null;
    }

    return 'https://www.google.com/maps/search/?api=1&query=' . rawurlencode($location);
}

function newsroom_remote_details(array $structured): array
{
    $sourceMeta = isset($structured['source_meta']) && is_array($structured['source_meta'])
        ? $structured['source_meta']
        : [];
    foreach (['remote_join_url', 'remote_webinar_id', 'remote_passcode', 'remote_phone_numbers'] as $key) {
        if ((!isset($sourceMeta[$key]) || $sourceMeta[$key] === '') && isset($structured[$key])) {
            $sourceMeta[$key] = $structured[$key];
        }
    }

    $phones = isset($sourceMeta['remote_phone_numbers']) && is_array($sourceMeta['remote_phone_numbers'])
        ? array_values(array_filter(array_map('strval', $sourceMeta['remote_phone_numbers'])))
        : [];

    $joinUrl = !empty($sourceMeta['remote_join_url']) ? (string) $sourceMeta['remote_join_url'] : null;
    $webinarId = !empty($sourceMeta['remote_webinar_id']) ? (string) $sourceMeta['remote_webinar_id'] : null;
    $passcode = !empty($sourceMeta['remote_passcode']) ? (string) $sourceMeta['remote_passcode'] : null;
    $hasActionable = $joinUrl !== null || $webinarId !== null || !empty($phones);

    return [
        'join_url' => $joinUrl,
        'webinar_id' => $webinarId,
        'passcode' => $hasActionable ? $passcode : null,
        'phones' => $phones,
    ];
}

function newsroom_story_meta_presenter(array $row): array
{
    $bodyName = (string) ($row['body_name'] ?? $row['governing_body'] ?? '');
    $signal = newsroom_body_signal($bodyName);
    $storyType = (string) ($row['story_type'] ?? '');
    $meetingDate = isset($row['meeting_date']) ? (string) $row['meeting_date'] : null;
    $meetingTime = isset($row['meeting_time']) ? (string) $row['meeting_time'] : null;
    $locationName = newsroom_display_location(isset($row['location_name']) ? (string) $row['location_name'] : null);
    $structured = newsroom_parse_json($row['artifact_structured_json'] ?? null);
    $sourceMeta = newsroom_parse_json($row['agenda_source_meta_json'] ?? null);
    if ($sourceMeta) {
        $structured['source_meta'] = array_merge(
            isset($structured['source_meta']) && is_array($structured['source_meta']) ? $structured['source_meta'] : [],
            $sourceMeta
        );
    }
    $remote = newsroom_remote_details($structured);

    return [
        'body_name' => $signal['name'],
        'body_signal' => $signal,
        'story_type_label' => newsroom_format_story_type($storyType),
        'meeting_datetime' => newsroom_format_meeting_datetime($meetingDate, $meetingTime, (string) ($row['display_date'] ?? $row['published_at'] ?? '')),
        'location_name' => $locationName,
        'location_map_url' => $storyType === 'meeting_preview' ? newsroom_google_maps_url($locationName) : null,
        'agenda_url' => !empty($row['agenda_url']) ? (string) $row['agenda_url'] : null,
        'minutes_url' => !empty($row['minutes_url']) ? (string) $row['minutes_url'] : null,
        'summary_text' => trim((string) ($row['summary'] ?? $row['dek'] ?? '')),
        'dek_text' => trim((string) ($row['dek'] ?? '')),
        'remote' => $remote,
    ];
}

function newsroom_event_presenter(array $row): array
{
    $bodyName = (string) ($row['body_name'] ?? '');
    $signal = newsroom_body_signal($bodyName);
    $structured = newsroom_parse_json($row['agenda_structured_json'] ?? null);
    $sourceMeta = newsroom_parse_json($row['agenda_source_meta_json'] ?? null);
    if ($sourceMeta) {
        $structured['source_meta'] = array_merge(
            isset($structured['source_meta']) && is_array($structured['source_meta']) ? $structured['source_meta'] : [],
            $sourceMeta
        );
    }
    $remote = newsroom_remote_details($structured);
    $locationName = newsroom_display_location(isset($row['location_name']) ? (string) $row['location_name'] : null);
    return [
        'id' => $row['id'],
        'title' => (string) $row['title'],
        'starts_at' => (string) $row['starts_at'],
        'body_name' => $signal['name'],
        'body_signal' => $signal,
        'location_name' => $locationName,
        'location_map_url' => newsroom_google_maps_url($locationName),
        'agenda_url' => !empty($row['agenda_url']) ? (string) $row['agenda_url'] : (string) ($row['source_url'] ?? ''),
        'minutes_url' => !empty($row['minutes_url']) ? (string) $row['minutes_url'] : null,
        'remote' => $remote,
        'summary_text' => trim((string) ($row['story_summary'] ?? $row['story_dek'] ?? $row['description'] ?? '')),
        'dek_text' => trim((string) ($row['story_dek'] ?? '')),
    ];
}

function newsroom_recent_story_presenter(array $row): array
{
    return array_merge($row, ['meta' => newsroom_story_meta_presenter($row)]);
}

function newsroom_latest_stories(int $limit = 8): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.story_type,
            s.headline,
            s.dek,
            s.summary,
            s.published_at,
            s.display_date,
            s.sort_date,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            COALESCE(gb.normalized_name, m.governing_body) AS body_name,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_url,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS artifact_structured_json
            ,
            (
                SELECT si.raw_meta_json
                FROM meeting_artifacts ma
                INNER JOIN source_items si ON si.id = ma.source_item_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_source_meta_json
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE publish_status = :status
           AND NOT (
                s.story_type = "meeting_preview"
                AND m.meeting_date IS NOT NULL
                AND m.meeting_date < DATE_SUB(CURDATE(), INTERVAL 2 DAY)
            )
         ORDER BY
            CASE
                WHEN s.story_type = "meeting_preview" AND m.meeting_date IS NOT NULL AND TIMESTAMP(m.meeting_date, COALESCE(m.meeting_time, "00:00:00")) >= NOW() THEN 0
                ELSE 1
            END ASC,
            CASE
                WHEN s.story_type = "meeting_preview" AND m.meeting_date IS NOT NULL AND TIMESTAMP(m.meeting_date, COALESCE(m.meeting_time, "00:00:00")) >= NOW()
                THEN TIMESTAMP(m.meeting_date, COALESCE(m.meeting_time, "00:00:00"))
                ELSE NULL
            END ASC,
            COALESCE(s.sort_date, s.display_date, s.published_at, TIMESTAMP(m.meeting_date, COALESCE(m.meeting_time, "00:00:00"))) DESC,
            s.id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':status', 'published');
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return array_map('newsroom_recent_story_presenter', $statement->fetchAll());
}

function newsroom_story_by_slug(string $slug): ?array
{
    if (!newsroom_db_available()) {
        return null;
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.story_type,
            s.headline,
            s.dek,
            s.summary,
            s.body_html,
            s.published_at,
            s.display_date,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            COALESCE(gb.normalized_name, m.governing_body) AS body_name,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_url,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id
                  AND ma.artifact_type = CASE WHEN s.story_type = "minutes_recap" THEN "minutes" ELSE "agenda" END
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS artifact_structured_json
            ,
            (
                SELECT si.raw_meta_json
                FROM meeting_artifacts ma
                INNER JOIN source_items si ON si.id = ma.source_item_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_source_meta_json
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE s.slug = :slug AND s.publish_status = :status
         LIMIT 1'
    );
    $statement->execute([
        ':slug' => $slug,
        ':status' => 'published',
    ]);

    $story = $statement->fetch();
    if (!$story) {
        return null;
    }

    $story['meta'] = newsroom_story_meta_presenter($story);
    return $story;
}

function newsroom_story_citations(int $storyId): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT citation_number, label, source_url, quote_text, note_text
         FROM story_citations
         WHERE story_id = :story_id
         ORDER BY citation_number ASC'
    );
    $statement->execute([':story_id' => $storyId]);

    return $statement->fetchAll();
}

function newsroom_upcoming_events(int $limit = 10): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            ce.id,
            ce.title,
            ce.starts_at,
            ce.location_name,
            ce.body_name,
            ce.source_url,
            ce.description,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = ce.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_url,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = ce.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT s.dek
                FROM stories s
                WHERE s.meeting_id = ce.meeting_id AND s.story_type = "meeting_preview" AND s.publish_status = "published"
                LIMIT 1
            ) AS story_dek,
            (
                SELECT s.summary
                FROM stories s
                WHERE s.meeting_id = ce.meeting_id AND s.story_type = "meeting_preview" AND s.publish_status = "published"
                LIMIT 1
            ) AS story_summary,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = ce.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_structured_json
            ,
            (
                SELECT si.raw_meta_json
                FROM meeting_artifacts ma
                INNER JOIN source_items si ON si.id = ma.source_item_id
                WHERE ma.meeting_id = ce.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_source_meta_json
         FROM calendar_events ce
         WHERE ce.starts_at >= NOW() AND ce.status = :status
         ORDER BY ce.starts_at ASC
         LIMIT :limit'
    );
    $statement->bindValue(':status', 'scheduled');
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return array_map('newsroom_event_presenter', $statement->fetchAll());
}

function newsroom_recent_meeting_recaps(int $limit = 12): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.story_type,
            s.headline,
            s.dek,
            s.summary,
            s.published_at,
            s.display_date,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            COALESCE(gb.normalized_name, m.governing_body) AS body_name,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS artifact_structured_json
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE s.publish_status = "published" AND s.story_type = "minutes_recap"
         ORDER BY COALESCE(s.sort_date, s.display_date, s.published_at) DESC, s.id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return array_map('newsroom_recent_story_presenter', $statement->fetchAll());
}

function newsroom_recent_runs(int $limit = 20): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT id, started_at, finished_at, run_status, items_discovered, documents_fetched, extractions_created, meetings_normalized, stories_published, stories_updated, events_created, events_updated
         FROM generation_runs
         ORDER BY started_at DESC, id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return $statement->fetchAll();
}

function newsroom_diagnostic_items(int $limit = 20): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            si.id,
            si.title,
            si.canonical_url,
            si.status,
            MAX(de.confidence_score) AS confidence_score,
            MAX(de.warnings_json) AS warnings_json,
            MAX(de.structured_json) AS structured_json
         FROM source_items si
         LEFT JOIN documents d ON d.source_item_id = si.id
         LEFT JOIN document_extractions de ON de.document_id = d.id
         WHERE (
                si.status IN ("needs_review", "extracted")
                OR (de.confidence_score IS NOT NULL AND de.confidence_score < 0.60)
           )
           AND LOWER(COALESCE(si.title, "")) NOT LIKE "%packet%"
           AND LOWER(COALESCE(si.title, "")) NOT LIKE "%previous version%"
           AND LOWER(COALESCE(si.title, "")) NOT LIKE "%html%"
           AND LOWER(COALESCE(si.title, "")) NOT IN ("notify meÂ®", "notify me", "rss")
           AND LOWER(COALESCE(si.canonical_url, "")) NOT LIKE "%/list.aspx#agendacenter%"
           AND LOWER(COALESCE(si.canonical_url, "")) NOT LIKE "%/rss.aspx#agendacenter%"
         GROUP BY si.id, si.title, si.canonical_url, si.status
         ORDER BY si.updated_at DESC, si.id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return $statement->fetchAll();
}
