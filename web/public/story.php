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
$slug = isset($_GET['slug']) ? (string) $_GET['slug'] : '';
$story = $slug !== '' ? newsroom_story_by_slug($slug) : null;
$citations = $story ? newsroom_story_citations((int) $story['id']) : [];
$storyDate = $story ? (string) ($story['display_date'] ?? $story['published_at']) : null;

function newsroom_pill_style(array $signal): string
{
    return sprintf(
        '--pill-bg:%s; --pill-fg:%s; --pill-border:%s;',
        $signal['bg'] ?? '#ece4d8',
        $signal['fg'] ?? '#47362b',
        $signal['border'] ?? '#a98767'
    );
}

http_response_code($story ? 200 : 404);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($story['headline'] ?? 'Story not found') ?> | <?= htmlspecialchars($config['site_name']) ?></title>
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
            <div class="masthead__meta"><a href="/status.php">Status</a></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Civic reporting, meeting coverage, and the public record.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar.php">Calendar</a>
        <a href="/status.php">Status</a>
    </nav>

    <div class="story-layout">
        <article class="story-body">
            <?php if ($story): ?>
                <div class="eyebrow"><?= htmlspecialchars(str_replace('_', ' ', $story['story_type'])) ?></div>
                <div class="story-meta-row story-meta-row--story">
                    <span class="signal-pill" style="<?= htmlspecialchars(newsroom_pill_style($story['meta']['body_signal'])) ?>"><?= htmlspecialchars($story['meta']['body_name']) ?></span>
                    <span class="story-meta-row__date"><?= htmlspecialchars($story['meta']['meeting_datetime']) ?></span>
                </div>
                <h2 class="story-headline"><?= htmlspecialchars($story['headline']) ?></h2>
                <div class="story-dek"><?= htmlspecialchars((string) ($story['dek'] ?? '')) ?></div>
                <div class="story-information">
                    <div class="story-information__row">
                        <span class="story-information__label">Filed</span>
                        <span><?= htmlspecialchars(date('F j, Y g:i A', strtotime((string) $storyDate))) ?></span>
                    </div>
                    <?php if (!empty($story['meta']['location_name'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Location</span>
                            <span>
                                <?php if (!empty($story['meta']['location_map_url'])): ?>
                                    <a href="<?= htmlspecialchars((string) $story['meta']['location_map_url']) ?>"><?= htmlspecialchars((string) $story['meta']['location_name']) ?></a>
                                <?php else: ?>
                                    <?= htmlspecialchars((string) $story['meta']['location_name']) ?>
                                <?php endif; ?>
                            </span>
                        </div>
                    <?php endif; ?>
                    <?php if (!empty($story['meta']['remote']['join_url']) || !empty($story['meta']['remote']['webinar_id']) || !empty($story['meta']['remote']['passcode'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Remote</span>
                            <span class="story-information__stack">
                                <?php if (!empty($story['meta']['remote']['join_url'])): ?>
                                    <a href="<?= htmlspecialchars((string) $story['meta']['remote']['join_url']) ?>">Join via Zoom</a>
                                <?php endif; ?>
                                <?php if (!empty($story['meta']['remote']['webinar_id'])): ?>
                                    <span>ID <?= htmlspecialchars((string) $story['meta']['remote']['webinar_id']) ?></span>
                                <?php endif; ?>
                                <?php if (!empty($story['meta']['remote']['passcode'])): ?>
                                    <span>Passcode <?= htmlspecialchars((string) $story['meta']['remote']['passcode']) ?></span>
                                <?php endif; ?>
                            </span>
                        </div>
                    <?php endif; ?>
                    <?php if ($story['story_type'] === 'meeting_preview' && !empty($story['meta']['agenda_url'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Agenda</span>
                            <span><a href="<?= htmlspecialchars((string) $story['meta']['agenda_url']) ?>">View official agenda</a></span>
                        </div>
                    <?php endif; ?>
                    <?php if ($story['story_type'] === 'minutes_recap' && !empty($story['meta']['minutes_url'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Minutes</span>
                            <span><a href="<?= htmlspecialchars((string) $story['meta']['minutes_url']) ?>">View posted minutes</a></span>
                        </div>
                    <?php endif; ?>
                    <?php if (!empty($story['meta']['summary_text'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label"><?= $story['story_type'] === 'minutes_recap' ? 'Summary' : 'Coverage' ?></span>
                            <span><?= htmlspecialchars((string) $story['meta']['summary_text']) ?></span>
                        </div>
                    <?php endif; ?>
                </div>
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
