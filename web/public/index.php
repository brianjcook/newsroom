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
$stories = newsroom_latest_stories();
$events = newsroom_upcoming_events();
$lead = $stories[0] ?? null;
$secondaryStories = array_slice($stories, 1);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div>
            <div class="masthead__meta">Wareham, Massachusetts</div>
            <h1 class="masthead__title">The Wareham Times</h1>
            <div class="masthead__tagline">Civic reporting, meeting coverage, and the public record.</div>
        </div>
        <div class="masthead__meta"><?= date('F j, Y') ?></div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar.php">Calendar</a>
        <a href="/status.php">Status</a>
    </nav>

    <section class="lead-grid">
        <article class="lead-story">
            <div class="eyebrow">Lead Story</div>
            <?php if ($lead): ?>
                <h2><a href="/story.php?slug=<?= urlencode($lead['slug']) ?>"><?= htmlspecialchars($lead['headline']) ?></a></h2>
                <p><?= htmlspecialchars($lead['dek'] ?: $lead['summary'] ?: '') ?></p>
            <?php else: ?>
                <h2>Newsroom scaffold is live.</h2>
                <p class="empty-state">Published stories will appear here once the worker discovers and processes Wareham source material.</p>
            <?php endif; ?>
        </article>

        <aside class="sidebar">
            <div class="eyebrow">Upcoming Meetings</div>
            <div class="event-list">
                <?php if ($events): ?>
                    <?php foreach ($events as $event): ?>
                        <article class="event-card">
                            <div class="event-card__meta"><?= htmlspecialchars((string) ($event['body_name'] ?? 'Official Meeting')) ?></div>
                            <strong><?= htmlspecialchars($event['title']) ?></strong>
                            <p><?= htmlspecialchars(date('F j, Y g:i A', strtotime((string) $event['starts_at']))) ?></p>
                        </article>
                    <?php endforeach; ?>
                <?php else: ?>
                    <p class="empty-state">No calendar entries yet.</p>
                <?php endif; ?>
            </div>
        </aside>
    </section>

    <h2 class="section-heading">Latest Coverage</h2>
    <section class="section-grid">
        <?php if ($secondaryStories): ?>
            <?php foreach ($secondaryStories as $story): ?>
                <article class="story-card">
                    <div class="story-card__meta"><?= htmlspecialchars(str_replace('_', ' ', $story['story_type'])) ?></div>
                    <h3><a href="/story.php?slug=<?= urlencode($story['slug']) ?>"><?= htmlspecialchars($story['headline']) ?></a></h3>
                    <p><?= htmlspecialchars($story['dek'] ?: $story['summary'] ?: '') ?></p>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="story-card">
                <div class="story-card__meta">Status</div>
                <h3>Initial site scaffold</h3>
                <p>The public site is connected to the database schema and ready for published stories and official meeting listings.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
