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
$slug = trim((string) ($_GET['slug'] ?? ''));
$bundle = $slug !== '' ? newsroom_governing_body_bundle($slug) : null;
$bodies = $slug === '' ? newsroom_governing_bodies_index() : [];
if ($slug !== '') {
    http_response_code($bundle ? 200 : 404);
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($bundle['body']['normalized_name'] ?? 'Governing Bodies') ?> | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Boards &amp; Committees</div>
            <div class="masthead__meta"><?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Recent coverage, upcoming meetings, and public-record links by governing body.</div>
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
        <?php if ($bundle): ?>
            <?php $body = $bundle['body']; ?>
            <section class="story-layout">
                <article class="story-body">
                    <div class="eyebrow"><?= htmlspecialchars((string) ($body['body_type'] ?: 'Governing Body')) ?></div>
                    <h2 class="story-headline"><?= htmlspecialchars((string) $body['normalized_name']) ?></h2>
                    <?php if (!empty($body['description'])): ?><p class="story-dek"><?= htmlspecialchars((string) $body['description']) ?></p><?php endif; ?>
                    <section class="story-information">
                        <?php if (!empty($body['meeting_schedule_text'])): ?>
                            <div class="story-information__row"><span class="story-information__label">Schedule</span><span class="story-information__value"><?= htmlspecialchars((string) $body['meeting_schedule_text']) ?></span></div>
                        <?php endif; ?>
                        <?php if (!empty($body['meeting_location_text'])): ?>
                            <div class="story-information__row"><span class="story-information__label">Location</span><span class="story-information__value"><?= htmlspecialchars((string) $body['meeting_location_text']) ?></span></div>
                        <?php endif; ?>
                        <?php if (!empty($body['source_page_url'])): ?>
                            <div class="story-information__row"><span class="story-information__label">Source</span><span class="story-information__value"><a href="<?= htmlspecialchars((string) $body['source_page_url']) ?>" target="_blank" rel="noopener noreferrer">Official page</a></span></div>
                        <?php endif; ?>
                    </section>
                    <h3>Recent Coverage</h3>
                    <?php if (!empty($bundle['stories'])): ?>
                        <ul class="related-list">
                            <?php foreach ($bundle['stories'] as $story): ?>
                                <li><a href="<?= htmlspecialchars(newsroom_story_url($story)) ?>"><?= htmlspecialchars((string) $story['headline']) ?></a></li>
                            <?php endforeach; ?>
                        </ul>
                    <?php else: ?>
                        <p class="empty-state">No published coverage for this body yet.</p>
                    <?php endif; ?>
                </article>
                <aside class="footnotes">
                    <div class="eyebrow">Upcoming</div>
                    <?php if (!empty($bundle['events'])): ?>
                        <?php foreach ($bundle['events'] as $event): ?>
                            <article class="event-item">
                                <strong><?= htmlspecialchars((string) $event['title']) ?></strong>
                                <p class="event-item__datetime"><?= htmlspecialchars(date('F j, Y g:i A', strtotime((string) $event['starts_at']))) ?></p>
                                <?php if (!empty($event['agenda_url'])): ?><p><a href="<?= htmlspecialchars((string) $event['agenda_url']) ?>">Agenda</a></p><?php endif; ?>
                            </article>
                        <?php endforeach; ?>
                    <?php else: ?>
                        <p class="empty-state">No upcoming meetings currently listed.</p>
                    <?php endif; ?>
                </aside>
            </section>
        <?php else: ?>
            <h2 class="story-headline">Body not found</h2>
            <p class="empty-state">The requested board or committee could not be found.</p>
        <?php endif; ?>
    <?php else: ?>
        <h2 class="section-heading">Boards &amp; Committees</h2>
        <section class="story-masonry">
            <?php foreach ($bodies as $body): ?>
                <article class="story-tease">
                    <h3><a href="<?= htmlspecialchars(newsroom_body_url((string) $body['slug'])) ?>"><?= htmlspecialchars((string) $body['normalized_name']) ?></a></h3>
                    <p class="archive-result__meta"><?= (int) $body['story_count'] ?> stories / <?= (int) $body['upcoming_count'] ?> upcoming meetings</p>
                    <?php if (!empty($body['meeting_schedule_text'])): ?><p><?= htmlspecialchars(newsroom_truncate_text((string) $body['meeting_schedule_text'], 160)) ?></p><?php endif; ?>
                </article>
            <?php endforeach; ?>
        </section>
    <?php endif; ?>
</div>
</body>
</html>
