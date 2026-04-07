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
$items = newsroom_source_leads();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Source Leads | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Source Leads</div>
            <div class="masthead__meta"><a href="/desk">Back to Desk</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Police logs and outside-source articles that may deserve reporting, context use, or a follow-up story.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/desk">Desk</a>
    </nav>

    <h2 class="section-heading">Source Leads</h2>
    <p class="section-intro">These are not auto-published stories. They are editorial inputs: public-safety records and outside reporting/context sources that may warrant a brief, follow-up, or reporting workspace.</p>

    <section class="methodology-grid">
        <?php if ($items): ?>
            <?php foreach ($items as $item): ?>
                <article class="methodology-card recap-card">
                    <div class="story-meta-row story-meta-row--compact">
                        <span class="signal-pill"><?= htmlspecialchars(newsroom_source_lead_type_label((string) $item['lead_type'])) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars((string) $item['source_name']) ?></span>
                        <span class="story-card__meta">Score <?= (int) ($item['effective_score'] ?? 0) ?></span>
                        <?php if (!empty($item['published_label'])): ?>
                            <span class="story-card__meta"><?= htmlspecialchars((string) $item['published_label']) ?></span>
                        <?php endif; ?>
                    </div>
                    <h3 class="story-headline"><a href="/desk/leads/<?= htmlspecialchars((string) $item['source_item_id']) ?>"><?= htmlspecialchars((string) $item['title']) ?></a></h3>
                    <?php if (!empty($item['reported_angle'])): ?>
                        <p class="story-dek"><?= htmlspecialchars((string) $item['reported_angle']) ?></p>
                    <?php endif; ?>
                    <?php if (!empty($item['notes'])): ?>
                        <p><?= htmlspecialchars((string) $item['notes']) ?></p>
                    <?php endif; ?>
                    <div class="editorial-active-queue__actions">
                        <a href="/desk/leads/<?= htmlspecialchars((string) $item['source_item_id']) ?>">Open reporting workspace</a>
                        <a href="<?= htmlspecialchars((string) $item['public_url']) ?>" target="_blank" rel="noopener noreferrer">Open source</a>
                    </div>
                    <?php if (!empty($item['signals'])): ?>
                        <ul class="editorial-signal-list">
                            <?php foreach (array_slice($item['signals'], 0, 3) as $signal): ?>
                                <li class="editorial-signal-list__item">
                                    <span class="editorial-signal-list__reason"><?= htmlspecialchars((string) ($signal['reason'] ?? '')) ?></span>
                                    <span class="editorial-signal-list__weight"><?= sprintf('%+d', (int) ($signal['weight'] ?? 0)) ?></span>
                                </li>
                            <?php endforeach; ?>
                        </ul>
                    <?php endif; ?>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="methodology-card">
                <h3>No source leads yet</h3>
                <p class="empty-state">Police logs and outside article leads will appear here after discovery runs.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
