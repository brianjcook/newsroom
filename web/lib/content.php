<?php

declare(strict_types=1);

require_once __DIR__ . '/db.php';

function newsroom_latest_stories(int $limit = 8): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT id, slug, story_type, headline, dek, summary, published_at
         FROM stories
         WHERE publish_status = :status
         ORDER BY published_at DESC, id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':status', 'published');
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return $statement->fetchAll();
}

function newsroom_story_by_slug(string $slug): ?array
{
    if (!newsroom_db_available()) {
        return null;
    }

    $statement = newsroom_db()->prepare(
        'SELECT id, slug, story_type, headline, dek, summary, body_html, published_at
         FROM stories
         WHERE slug = :slug AND publish_status = :status
         LIMIT 1'
    );
    $statement->execute([
        ':slug' => $slug,
        ':status' => 'published',
    ]);

    $story = $statement->fetch();

    return $story ?: null;
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
        'SELECT id, title, starts_at, location_name, body_name, source_url
         FROM calendar_events
         WHERE starts_at >= NOW() AND status = :status
         ORDER BY starts_at ASC
         LIMIT :limit'
    );
    $statement->bindValue(':status', 'scheduled');
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return $statement->fetchAll();
}

function newsroom_recent_runs(int $limit = 20): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT id, started_at, finished_at, run_status, items_discovered, documents_fetched, extractions_created, meetings_normalized, stories_published, events_created
         FROM generation_runs
         ORDER BY started_at DESC, id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return $statement->fetchAll();
}
