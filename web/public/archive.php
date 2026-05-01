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
$filters = [
    'q' => trim((string) ($_GET['q'] ?? '')),
    'entity' => trim((string) ($_GET['entity'] ?? 'all')),
    'topic' => trim((string) ($_GET['topic'] ?? 'all')),
    'body' => trim((string) ($_GET['body'] ?? 'all')),
    'story_type' => trim((string) ($_GET['story_type'] ?? 'all')),
];
$results = newsroom_archive_results($filters);
$options = newsroom_archive_filter_options();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Archive &amp; Search | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Archive &amp; Search</div>
            <div class="masthead__meta"><?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Search stories, event briefs, and topic coverage across the newsroom archive.</div>
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

    <h2 class="section-heading">Archive &amp; Search</h2>
    <form method="get" class="editorial-filters archive-filters">
        <label>
            <span>Search</span>
            <input type="text" name="q" value="<?= htmlspecialchars($filters['q']) ?>" placeholder="Wastewater, chili contest, zoning...">
        </label>
        <label>
            <span>Entity</span>
            <select name="entity">
                <option value="all"<?= $filters['entity'] === 'all' ? ' selected' : '' ?>>All</option>
                <option value="story"<?= $filters['entity'] === 'story' ? ' selected' : '' ?>>Stories</option>
                <option value="community_event"<?= $filters['entity'] === 'community_event' ? ' selected' : '' ?>>Events</option>
            </select>
        </label>
        <label>
            <span>Story Type</span>
            <select name="story_type">
                <option value="all"<?= $filters['story_type'] === 'all' ? ' selected' : '' ?>>All</option>
                <?php foreach ($options['story_types'] as $value => $label): ?>
                    <option value="<?= htmlspecialchars((string) $value) ?>"<?= $filters['story_type'] === (string) $value ? ' selected' : '' ?>><?= htmlspecialchars((string) $label) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>
            <span>Topic</span>
            <select name="topic">
                <option value="all"<?= $filters['topic'] === 'all' ? ' selected' : '' ?>>All</option>
                <?php foreach ($options['topics'] as $value => $label): ?>
                    <option value="<?= htmlspecialchars((string) $value) ?>"<?= $filters['topic'] === (string) $value ? ' selected' : '' ?>><?= htmlspecialchars((string) $label) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>
            <span>Body</span>
            <select name="body">
                <option value="all"<?= $filters['body'] === 'all' ? ' selected' : '' ?>>All</option>
                <?php foreach ($options['bodies'] as $value => $label): ?>
                    <option value="<?= htmlspecialchars((string) $value) ?>"<?= $filters['body'] === (string) $value ? ' selected' : '' ?>><?= htmlspecialchars((string) $label) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <button type="submit">Search</button>
    </form>

    <p class="section-intro">This archive blends formal meeting coverage and first-party community event pages so the site can be browsed like a newsroom morgue instead of a raw feed.</p>

    <section class="archive-results">
        <?php if ($results): ?>
            <?php foreach ($results as $item): ?>
                <article class="archive-result">
                    <div class="story-meta-row story-meta-row--compact">
                        <span class="signal-pill"><?= htmlspecialchars((string) $item['label']) ?></span>
                        <?php if (($item['entity_type'] ?? '') === 'community_event' && !empty($item['event_tier']['label'])): ?>
                            <span class="story-card__meta"><?= htmlspecialchars((string) $item['event_tier']['label']) ?></span>
                        <?php endif; ?>
                        <span class="story-card__meta">Rank <?= htmlspecialchars((string) round((float) ($item['editorial_rank'] ?? 0))) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars(date('F j, Y g:i A', strtotime((string) $item['occurs_at']))) ?></span>
                    </div>
                    <h3><a href="<?= htmlspecialchars((string) $item['public_url']) ?>"><?= htmlspecialchars((string) $item['title']) ?></a></h3>
                    <p class="archive-result__byline">By <?= htmlspecialchars((string) $item['byline']['name']) ?><?php if (!empty($item['byline']['title'])): ?> <span><?= htmlspecialchars((string) $item['byline']['title']) ?></span><?php endif; ?></p>
                    <?php if (!empty($item['body_name'])): ?>
                        <p class="archive-result__meta"><?= htmlspecialchars((string) $item['body_name']) ?></p>
                    <?php endif; ?>
                    <?php if (!empty($item['summary_text'])): ?>
                        <p><?= htmlspecialchars(newsroom_truncate_text((string) $item['summary_text'], 260)) ?></p>
                    <?php endif; ?>
                    <?php if (!empty($item['topics'])): ?>
                        <div class="topic-chip-row">
                            <?php foreach ($item['topics'] as $topic): ?>
                                <a class="topic-chip" href="<?= htmlspecialchars(newsroom_topic_url((string) $topic['slug'])) ?>"><?= htmlspecialchars((string) $topic['label']) ?></a>
                            <?php endforeach; ?>
                        </div>
                    <?php endif; ?>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="archive-result">
                <h3>No archive matches found</h3>
                <p class="empty-state">Try a broader topic, a different board name, or a shorter keyword phrase.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
