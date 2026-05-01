<?php

declare(strict_types=1);

$bootstrapPath = file_exists(__DIR__ . '/../bootstrap.php')
    ? __DIR__ . '/../bootstrap.php'
    : __DIR__ . '/bootstrap.php';
$contentPath = file_exists(__DIR__ . '/../lib/content.php')
    ? __DIR__ . '/../lib/content.php'
    : __DIR__ . '/lib/content.php';

require_once $bootstrapPath;
require_once $contentPath;

$config = newsroom_config();
$requestPath = trim((string) parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH), '/');
$slug = isset($_GET['slug']) ? (string) $_GET['slug'] : '';
if ($slug === '' && strpos($requestPath, 'opinion/') === 0) {
    $slug = rawurldecode(substr($requestPath, strlen('opinion/')));
}
$story = $slug !== '' ? newsroom_story_by_slug($slug) : null;
$items = $slug === '' ? newsroom_opinion_items(30) : [];
$ad = newsroom_active_ads('story-rail', 1)[0] ?? null;
if ($slug !== '') {
    http_response_code($story && newsroom_story_is_opinion($story) ? 200 : 404);
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($story['headline'] ?? 'Opinion') ?> | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Opinion</div>
            <div class="masthead__meta"><?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Editorials, columns, and clearly labeled opinion from the newsroom.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/opinion">Opinion</a>
        <a href="/bodies">Bodies</a>
        <a href="/archive">Archive</a>
    </nav>

    <?php if ($slug !== ''): ?>
        <?php if ($story && newsroom_story_is_opinion($story)): ?>
            <section class="story-layout">
                <article class="story-body">
                    <div class="eyebrow"><?= htmlspecialchars((string) $story['label']) ?></div>
                    <div class="story-filed-meta"><?= htmlspecialchars(newsroom_editorial_datetime((string) ($story['display_date'] ?? $story['published_at'] ?? ''))) ?></div>
                    <h2 class="story-headline"><?= htmlspecialchars((string) $story['headline']) ?></h2>
                    <div class="story-byline">By <?= htmlspecialchars((string) $story['byline']['name']) ?> <span><?= htmlspecialchars((string) $story['byline']['title']) ?></span></div>
                    <?php if (!empty($story['topics'])): ?>
                        <div class="topic-chip-row topic-chip-row--story">
                            <?php foreach ($story['topics'] as $topic): ?>
                                <a class="topic-chip" href="<?= htmlspecialchars(newsroom_topic_url((string) $topic['slug'])) ?>"><?= htmlspecialchars((string) $topic['label']) ?></a>
                            <?php endforeach; ?>
                        </div>
                    <?php endif; ?>
                    <?php if (!empty($story['dek'])): ?><p class="story-dek"><?= htmlspecialchars((string) $story['dek']) ?></p><?php endif; ?>
                    <div><?= $story['body_html'] ?></div>
                </article>
                <aside class="footnotes">
                    <div class="eyebrow">Opinion</div>
                    <p class="empty-state">Opinion pieces are separate from source-grounded meeting previews, recaps, and reported briefs.</p>
                    <?php if ($ad): ?>
                        <section class="ad-unit ad-unit--rail">
                            <div class="ad-unit__label"><?= htmlspecialchars((string) $ad['label']) ?></div>
                            <strong><?= htmlspecialchars((string) $ad['headline']) ?></strong>
                            <?php if (!empty($ad['body_text'])): ?><p><?= htmlspecialchars((string) $ad['body_text']) ?></p><?php endif; ?>
                            <?php if (!empty($ad['destination_url'])): ?><a href="<?= htmlspecialchars((string) $ad['destination_url']) ?>">Learn more</a><?php endif; ?>
                        </section>
                    <?php endif; ?>
                </aside>
            </section>
        <?php else: ?>
            <h2 class="story-headline">Opinion not found</h2>
            <p class="empty-state">The requested opinion piece could not be found or has not been published.</p>
        <?php endif; ?>
    <?php else: ?>
        <h2 class="section-heading">Opinion</h2>
        <section class="archive-results">
            <?php if ($items): ?>
                <?php foreach ($items as $item): ?>
                    <article class="archive-result">
                        <div class="story-meta-row story-meta-row--compact">
                            <span class="signal-pill"><?= htmlspecialchars((string) $item['label']) ?></span>
                            <span class="story-card__meta"><?= htmlspecialchars(newsroom_editorial_datetime((string) ($item['display_date'] ?? $item['published_at'] ?? ''))) ?></span>
                        </div>
                        <h3><a href="<?= htmlspecialchars(newsroom_opinion_url_from_slug((string) $item['slug'])) ?>"><?= htmlspecialchars((string) $item['headline']) ?></a></h3>
                        <p class="archive-result__byline">By <?= htmlspecialchars((string) $item['byline']['name']) ?></p>
                        <?php if (!empty($item['summary'])): ?><p><?= htmlspecialchars(newsroom_truncate_text((string) $item['summary'], 260)) ?></p><?php endif; ?>
                    </article>
                <?php endforeach; ?>
            <?php else: ?>
                <article class="archive-result">
                    <h3>No opinion pieces published yet</h3>
                    <p class="empty-state">Editorials and columns will appear here once they are published from the desk.</p>
                </article>
            <?php endif; ?>
        </section>
    <?php endif; ?>
</div>
</body>
</html>
