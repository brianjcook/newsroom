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
$events = newsroom_upcoming_events(50);
$communityEvents = newsroom_upcoming_community_events(30);
$recentRecaps = newsroom_recent_meeting_recaps(18);

function newsroom_pill_style(array $signal): string
{
    return sprintf(
        '--pill-bg:%s; --pill-fg:%s; --pill-border:%s;',
        $signal['bg'] ?? '#ece4d8',
        $signal['fg'] ?? '#47362b',
        $signal['border'] ?? '#a98767'
    );
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Calendar | <?= htmlspecialchars($config['site_name']) ?></title>
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
            <div class="masthead__tagline">Official meetings and public dates.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
    </nav>

    <h2 class="section-heading">Upcoming Meetings</h2>
    <section class="calendar-ledger">
        <?php if ($events): ?>
            <?php foreach ($events as $event): ?>
                <article class="calendar-row">
                    <div class="calendar-row__when"><?= htmlspecialchars(date('D', strtotime((string) $event['starts_at']))) ?><span><?= htmlspecialchars(date('M j', strtotime((string) $event['starts_at']))) ?></span></div>
                    <div class="calendar-row__body">
                        <div class="story-meta-row story-meta-row--compact">
                            <span class="signal-pill" style="<?= htmlspecialchars(newsroom_pill_style($event['body_signal'])) ?>"><?= htmlspecialchars($event['body_name']) ?></span>
                            <span class="story-card__meta"><?= htmlspecialchars(date('g:i A', strtotime((string) $event['starts_at']))) ?></span>
                        </div>
                        <h3><?= htmlspecialchars($event['title']) ?></h3>
                        <p><?= htmlspecialchars(date('l, F j, Y g:i A', strtotime((string) $event['starts_at']))) ?></p>
                        <?php if (!empty($event['location_name'])): ?>
                            <p><a href="<?= htmlspecialchars((string) $event['location_map_url']) ?>"><?= htmlspecialchars((string) $event['location_name']) ?></a></p>
                        <?php endif; ?>
                        <?php if (!empty($event['remote']['join_url']) || !empty($event['remote']['webinar_id']) || !empty($event['remote']['passcode'])): ?>
                            <div class="meeting-facts">
                                <?php if (!empty($event['remote']['join_url'])): ?>
                                    <span><a href="<?= htmlspecialchars((string) $event['remote']['join_url']) ?>">Zoom</a></span>
                                <?php endif; ?>
                                <?php if (!empty($event['remote']['webinar_id'])): ?>
                                    <span>ID <?= htmlspecialchars((string) $event['remote']['webinar_id']) ?></span>
                                <?php endif; ?>
                                <?php if (!empty($event['remote']['passcode'])): ?>
                                    <span>Passcode <?= htmlspecialchars((string) $event['remote']['passcode']) ?></span>
                                <?php endif; ?>
                            </div>
                        <?php endif; ?>
                        <?php if (!empty($event['summary_text'])): ?>
                            <p class="calendar-row__summary"><?= htmlspecialchars((string) $event['summary_text']) ?></p>
                        <?php endif; ?>
                    </div>
                    <div class="calendar-row__source">
                        <a href="<?= htmlspecialchars((string) $event['agenda_url']) ?>">Agenda</a>
                    </div>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="calendar-row">
                <h3>No events yet</h3>
                <p class="empty-state">Official meeting listings will appear after the daily pipeline discovers Wareham source material.</p>
            </article>
        <?php endif; ?>
    </section>

    <h2 class="section-heading">Community Calendar</h2>
    <section class="calendar-ledger">
        <?php if ($communityEvents): ?>
            <?php foreach ($communityEvents as $event): ?>
                <article class="calendar-row">
                    <div class="calendar-row__when"><?= htmlspecialchars(date('D', strtotime((string) $event['starts_at']))) ?><span><?= htmlspecialchars(date('M j', strtotime((string) $event['starts_at']))) ?></span></div>
                    <div class="calendar-row__body">
                        <div class="story-meta-row story-meta-row--compact">
                            <span class="signal-pill" style="<?= htmlspecialchars(newsroom_pill_style($event['body_signal'])) ?>"><?= htmlspecialchars($event['source_type'] === 'community_event' ? 'Community Event' : ucwords(str_replace('_', ' ', $event['source_type']))) ?></span>
                            <span class="story-card__meta"><?= htmlspecialchars(date('g:i A', strtotime((string) $event['starts_at']))) ?></span>
                            <span class="story-card__meta">Score <?= htmlspecialchars((string) $event['effective_score']) ?></span>
                        </div>
                        <h3><?= htmlspecialchars($event['title']) ?></h3>
                        <p><?= htmlspecialchars(date('l, F j, Y g:i A', strtotime((string) $event['starts_at']))) ?></p>
                        <?php if (!empty($event['location_name'])): ?>
                            <p><?= htmlspecialchars((string) $event['location_name']) ?></p>
                        <?php endif; ?>
                        <?php if (!empty($event['description'])): ?>
                            <p class="calendar-row__summary"><?= htmlspecialchars((string) $event['description']) ?></p>
                        <?php endif; ?>
                    </div>
                    <div class="calendar-row__source">
                        <a href="<?= htmlspecialchars((string) $event['source_url']) ?>" target="_blank" rel="noopener noreferrer">Details</a>
                    </div>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="calendar-row">
                <h3>No community events yet</h3>
                <p class="empty-state">Town calendar events will appear here after the public-calendar sync runs.</p>
            </article>
        <?php endif; ?>
    </section>

    <h2 class="section-heading">Recent Minutes</h2>
    <section class="story-masonry">
        <?php if ($recentRecaps): ?>
            <?php foreach ($recentRecaps as $story): ?>
                <article class="story-tease">
                    <div class="story-meta-row story-meta-row--compact">
                        <span class="signal-pill" style="<?= htmlspecialchars(newsroom_pill_style($story['meta']['body_signal'])) ?>"><?= htmlspecialchars($story['meta']['body_name']) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars($story['meta']['meeting_datetime']) ?></span>
                    </div>
                    <h3><a href="<?= htmlspecialchars(newsroom_story_url($story)) ?>"><?= htmlspecialchars($story['headline']) ?></a></h3>
                    <?php if (!empty($story['meta']['location_name'])): ?>
                        <p><?= htmlspecialchars((string) $story['meta']['location_name']) ?></p>
                    <?php endif; ?>
                    <?php if (!empty($story['meta']['summary_text'])): ?>
                        <p><?= htmlspecialchars((string) $story['meta']['summary_text']) ?></p>
                    <?php endif; ?>
                    <?php if (!empty($story['meta']['minutes_url'])): ?>
                        <p><a href="<?= htmlspecialchars((string) $story['meta']['minutes_url']) ?>">Minutes</a></p>
                    <?php endif; ?>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="story-tease">
                <h3>No minutes recaps yet</h3>
                <p class="empty-state">Published recaps will appear here as minutes are posted and processed.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
