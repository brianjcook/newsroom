<?php

declare(strict_types=1);

require_once __DIR__ . '/../bootstrap.php';
require_once __DIR__ . '/../lib/content.php';

$config = newsroom_config();
$slug = isset($_GET['slug']) ? (string) $_GET['slug'] : '';
$story = $slug !== '' ? newsroom_story_by_slug($slug) : null;
$citations = $story ? newsroom_story_citations((int) $story['id']) : [];

http_response_code($story ? 200 : 404);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($story['headline'] ?? 'Story not found') ?> | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div>
            <div class="masthead__meta">Wareham, Massachusetts</div>
            <h1 class="masthead__title"><a href="/" style="text-decoration: none;"><?= htmlspecialchars($config['site_name']) ?></a></h1>
            <div class="masthead__tagline">Civic reporting, meeting coverage, and the public record.</div>
        </div>
        <div class="masthead__meta"><a href="/calendar.php">Calendar</a></div>
    </header>

    <div class="story-layout">
        <article class="story-body">
            <?php if ($story): ?>
                <div class="eyebrow"><?= htmlspecialchars(str_replace('_', ' ', $story['story_type'])) ?></div>
                <h2 class="story-headline"><?= htmlspecialchars($story['headline']) ?></h2>
                <div class="story-dek"><?= htmlspecialchars((string) ($story['dek'] ?? '')) ?></div>
                <div class="masthead__meta"><?= htmlspecialchars(date('F j, Y g:i A', strtotime((string) $story['published_at']))) ?></div>
                <div><?= $story['body_html'] ?></div>
            <?php else: ?>
                <h2 class="story-headline">Story not found</h2>
                <p class="empty-state">The requested story could not be found or has not been published.</p>
            <?php endif; ?>
        </article>

        <aside class="footnotes">
            <div class="eyebrow">Sources</div>
            <?php if ($citations): ?>
                <ol>
                    <?php foreach ($citations as $citation): ?>
                        <li class="footnotes__item">
                            <?= htmlspecialchars((string) ($citation['label'] ?: $citation['note_text'] ?: 'Source')) ?>
                            <br>
                            <a href="<?= htmlspecialchars($citation['source_url']) ?>"><?= htmlspecialchars($citation['source_url']) ?></a>
                        </li>
                    <?php endforeach; ?>
                </ol>
            <?php else: ?>
                <p class="empty-state">Source citations will appear here for published stories.</p>
            <?php endif; ?>
        </aside>
    </div>
</div>
</body>
</html>
