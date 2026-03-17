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
        <a href="/calendar.php">Calendar</a>
        <a href="/status.php">Status</a>
    </nav>

    <h2 class="section-heading">Upcoming Meetings</h2>
    <section class="calendar-ledger">
        <?php if ($events): ?>
            <?php foreach ($events as $event): ?>
                <article class="calendar-row">
                    <div class="calendar-row__when"><?= htmlspecialchars(date('D', strtotime((string) $event['starts_at']))) ?><span><?= htmlspecialchars(date('M j', strtotime((string) $event['starts_at']))) ?></span></div>
                    <div class="calendar-row__body">
                        <div class="event-card__meta"><?= htmlspecialchars((string) ($event['body_name'] ?? 'Official Meeting')) ?></div>
                        <h3><?= htmlspecialchars($event['title']) ?></h3>
                        <p><?= htmlspecialchars(date('l, F j, Y g:i A', strtotime((string) $event['starts_at']))) ?></p>
                        <?php if (!empty($event['location_name'])): ?>
                            <p><?= htmlspecialchars((string) $event['location_name']) ?></p>
                        <?php endif; ?>
                    </div>
                    <div class="calendar-row__source"><a href="<?= htmlspecialchars($event['source_url']) ?>">Source</a></div>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="calendar-row">
                <h3>No events yet</h3>
                <p class="empty-state">Official meeting listings will appear after the daily pipeline discovers Wareham source material.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
