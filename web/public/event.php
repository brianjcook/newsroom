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
$eventId = isset($_GET['id']) ? (int) $_GET['id'] : 0;

if ($eventId <= 0 && strpos($requestPath, 'events/') === 0) {
    $parts = explode('/', $requestPath);
    if (isset($parts[1]) && ctype_digit($parts[1])) {
        $eventId = (int) $parts[1];
    }
}

$event = $eventId > 0 ? newsroom_community_event_by_id($eventId) : null;
$metaBits = $event ? newsroom_community_event_story_meta($event) : [];
$summary = $event ? newsroom_community_event_summary($event) : '';
$focus = $event ? newsroom_community_event_focus($event) : '';
$briefIntro = $event ? newsroom_community_event_brief_intro($event) : '';
$signalItems = $event ? newsroom_community_event_signal_items($event) : [];
$editorialNote = $event ? newsroom_community_event_editorial_note($event) : '';
$relatedBundle = $event ? newsroom_event_related_bundle($event) : ['topic' => null, 'stories' => [], 'events' => []];

http_response_code($event ? 200 : 404);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($event['title'] ?? 'Event not found') ?> | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Wareham, Massachusetts</div>
            <div class="masthead__meta"><?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Community happenings, civic coverage, and the public record.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
    </nav>

    <div class="story-layout">
        <article class="story-body">
            <?php if ($event): ?>
                <div class="eyebrow">Community Event</div>
                <div class="story-filed-meta"><?= htmlspecialchars(date('F j, Y g:i A', strtotime((string) $event['starts_at']))) ?></div>
                <h2 class="story-headline"><?= htmlspecialchars($event['title']) ?></h2>
                <div class="story-meta-row story-meta-row--story">
                    <span class="signal-pill" style="<?= htmlspecialchars(sprintf('--pill-bg:%s; --pill-fg:%s; --pill-border:%s;', $event['body_signal']['bg'], $event['body_signal']['fg'], $event['body_signal']['border'])) ?>"><?= htmlspecialchars($event['source_type'] === 'community_event' ? 'Community Event' : ucwords(str_replace('_', ' ', $event['source_type']))) ?></span>
                </div>
                <div class="story-dek"><?= htmlspecialchars($summary) ?></div>
                <?php if (!empty($event['topics'])): ?>
                    <div class="topic-chip-row topic-chip-row--story">
                        <?php foreach ($event['topics'] as $topic): ?>
                            <a class="topic-chip" href="<?= htmlspecialchars(newsroom_topic_url((string) $topic['slug'])) ?>"><?= htmlspecialchars((string) $topic['label']) ?></a>
                        <?php endforeach; ?>
                    </div>
                <?php endif; ?>
                <div class="story-information">
                    <div class="story-information__row">
                        <span class="story-information__label">Date &amp; Time</span>
                        <span class="story-information__value"><?= htmlspecialchars(date('F j, Y g:i A', strtotime((string) $event['starts_at']))) ?></span>
                    </div>
                    <?php if (!empty($event['location_name'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Location</span>
                            <span class="story-information__value">
                                <?php if (!empty($event['location_map_url'])): ?>
                                    <a href="<?= htmlspecialchars((string) $event['location_map_url']) ?>"><?= htmlspecialchars((string) $event['location_name']) ?></a>
                                <?php else: ?>
                                    <?= htmlspecialchars((string) $event['location_name']) ?>
                                <?php endif; ?>
                            </span>
                        </div>
                    <?php endif; ?>
                    <?php if ($metaBits): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Editorial</span>
                            <span class="story-information__stack">
                                <?php foreach ($metaBits as $bit): ?>
                                    <span><?= htmlspecialchars((string) $bit) ?></span>
                                <?php endforeach; ?>
                            </span>
                        </div>
                    <?php endif; ?>
                    <div class="story-information__row">
                        <span class="story-information__label">Source</span>
                        <span class="story-information__value"><a href="<?= htmlspecialchars((string) $event['source_url']) ?>" target="_blank" rel="noopener noreferrer">View official event listing</a></span>
                    </div>
                </div>

                <p><?= htmlspecialchars($briefIntro) ?></p>
                <?php if ($focus !== ''): ?>
                    <h3>What to Know</h3>
                    <p><?= htmlspecialchars($focus) ?></p>
                <?php endif; ?>
                <?php if ($editorialNote !== ''): ?>
                    <h3>Why It Stands Out</h3>
                    <p><?= htmlspecialchars($editorialNote) ?></p>
                <?php endif; ?>
                <?php if (!empty($event['description'])): ?>
                    <h3>Event Details</h3>
                    <p><?= htmlspecialchars((string) $event['description']) ?></p>
                <?php endif; ?>
                <?php if (!empty($relatedBundle['topic']) && (!empty($relatedBundle['stories']) || !empty($relatedBundle['events']))): ?>
                    <h3>Related Coverage</h3>
                    <p>This item is also part of <a href="<?= htmlspecialchars(newsroom_topic_url((string) $relatedBundle['topic']['slug'])) ?>"><?= htmlspecialchars((string) $relatedBundle['topic']['label']) ?></a> coverage.</p>
                    <?php if (!empty($relatedBundle['stories'])): ?>
                        <ul class="related-list">
                            <?php foreach ($relatedBundle['stories'] as $relatedStory): ?>
                                <li><a href="<?= htmlspecialchars(newsroom_story_url($relatedStory)) ?>"><?= htmlspecialchars((string) $relatedStory['headline']) ?></a></li>
                            <?php endforeach; ?>
                        </ul>
                    <?php endif; ?>
                    <?php if (!empty($relatedBundle['events'])): ?>
                        <h3>More on This Topic</h3>
                        <ul class="related-list">
                            <?php foreach ($relatedBundle['events'] as $relatedEvent): ?>
                                <li><a href="<?= htmlspecialchars((string) $relatedEvent['local_url']) ?>"><?= htmlspecialchars((string) $relatedEvent['title']) ?></a></li>
                            <?php endforeach; ?>
                        </ul>
                    <?php endif; ?>
                <?php endif; ?>
            <?php else: ?>
                <h2 class="story-headline">Event not found</h2>
                <p class="empty-state">The requested event could not be found or is no longer available.</p>
            <?php endif; ?>
        </article>

        <aside class="footnotes">
            <div class="eyebrow">Quick Facts</div>
            <?php if ($event): ?>
                <ol>
                    <li class="footnotes__item">Score <?= htmlspecialchars((string) $event['effective_score']) ?></li>
                    <li class="footnotes__item"><?= htmlspecialchars(str_replace('_', ' ', (string) $event['effective_coverage_mode'])) ?></li>
                    <?php if (!empty($event['source_category'])): ?>
                        <li class="footnotes__item"><?= htmlspecialchars((string) $event['source_category']) ?></li>
                    <?php endif; ?>
                    <?php foreach ($signalItems as $signal): ?>
                        <li class="footnotes__item"><?= htmlspecialchars((string) $signal['reason']) ?> (<?= htmlspecialchars(sprintf('%+d', (int) $signal['weight'])) ?>)</li>
                    <?php endforeach; ?>
                </ol>
            <?php else: ?>
                <p class="empty-state">Event facts will appear here when a listing is available.</p>
            <?php endif; ?>
        </aside>
    </div>
</div>
</body>
</html>
