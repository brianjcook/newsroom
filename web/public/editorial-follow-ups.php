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

newsroom_require_editorial_login();

$config = newsroom_config();
$items = newsroom_follow_up_items();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Follow-Up Queue | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Follow-Up Story Queue</div>
            <div class="masthead__meta"><a href="/desk">Back to Desk</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Second-day stories, accountability angles, and unresolved items worth pursuing.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/desk">Desk</a>
    </nav>

    <h2 class="section-heading">Follow-Up Queue</h2>
    <section class="methodology-grid">
        <?php if ($items): ?>
            <?php foreach ($items as $item): ?>
                <article class="methodology-card recap-card">
                    <div class="story-meta-row story-meta-row--compact">
                        <span class="signal-pill"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['workflow_status']))) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['priority']))) ?></span>
                    </div>
                    <h3 class="story-headline"><a href="/desk/follow-ups/<?= htmlspecialchars((string) $item['id']) ?>"><?= htmlspecialchars((string) $item['title']) ?></a></h3>
                    <p><?= htmlspecialchars((string) ($item['notes'] ?? '')) ?></p>
                    <p class="archive-result__meta">Source story: <a href="<?= htmlspecialchars((string) $item['public_url']) ?>"><?= htmlspecialchars((string) $item['source_headline']) ?></a></p>
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
            <article class="methodology-card">
                <h3>No follow-up items yet</h3>
                <p class="empty-state">Create them from recap workspaces when a meeting clearly calls for another story.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
