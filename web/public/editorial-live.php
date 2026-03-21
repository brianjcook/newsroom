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

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    newsroom_save_live_prep_notes((string) ($_POST['entity_type'] ?? ''), (int) ($_POST['entity_id'] ?? 0), (string) ($_POST['live_prep_notes'] ?? ''));
    header('Location: /desk/live?saved=1');
    exit;
}

$config = newsroom_config();
$items = newsroom_live_watch_queue();
$saved = isset($_GET['saved']) && $_GET['saved'] === '1';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Live Watch Queue | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Live Watch Queue</div>
            <div class="masthead__meta"><a href="/desk">Back to Desk</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Preflight pages for meetings worth watching live, whether by Zoom, stream, or public room attendance.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/desk">Desk</a>
    </nav>

    <h2 class="section-heading">Watch Live</h2>
    <p class="section-intro">This queue is the launch point for real-time reporting. It pulls agenda links, Zoom details, and a standard preflight checklist into one place before the meeting starts.</p>
    <?php if ($saved): ?><p class="editorial-save-note">Live prep notes saved.</p><?php endif; ?>

    <section class="methodology-grid">
        <?php if ($items): ?>
            <?php foreach ($items as $item): ?>
                <article class="methodology-card recap-card">
                    <div class="story-meta-row story-meta-row--compact">
                        <span class="signal-pill"><?= htmlspecialchars((string) $item['label']) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars((string) $item['live_prep']['source_type']) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars((string) $item['meta']['meeting_datetime']) ?></span>
                    </div>
                    <h3 class="story-headline"><a href="<?= htmlspecialchars(newsroom_story_url($item)) ?>"><?= htmlspecialchars((string) $item['headline']) ?></a></h3>
                    <p><?= htmlspecialchars((string) ($item['summary'] ?? $item['dek'] ?? '')) ?></p>
                    <div class="editorial-active-queue__actions">
                        <a href="<?= htmlspecialchars((string) ($item['meta']['agenda_url'] ?? '')) ?>" target="_blank" rel="noopener noreferrer">Open agenda</a>
                        <?php if (!empty($item['meta']['remote']['join_url'])): ?>
                            <a href="<?= htmlspecialchars((string) $item['meta']['remote']['join_url']) ?>" target="_blank" rel="noopener noreferrer">Join Zoom</a>
                        <?php endif; ?>
                        <a href="/desk/recaps/<?= htmlspecialchars((string) $item['id']) ?>">Recap workspace</a>
                    </div>
                    <div class="recap-scaffold__section">
                        <strong>Preflight checklist</strong>
                        <ul class="methodology-list">
                            <?php foreach (($item['live_prep']['checklist'] ?? []) as $check): ?>
                                <li><p><?= htmlspecialchars((string) $check) ?></p></li>
                            <?php endforeach; ?>
                        </ul>
                    </div>
                    <form method="post" class="draft-workspace__form">
                        <input type="hidden" name="entity_type" value="story">
                        <input type="hidden" name="entity_id" value="<?= htmlspecialchars((string) $item['id']) ?>">
                        <label class="editorial-inline-control">
                            <span>Live Prep Notes</span>
                            <textarea name="live_prep_notes" rows="5"><?= htmlspecialchars((string) ($item['live_prep_notes'] ?? '')) ?></textarea>
                        </label>
                        <button type="submit">Save Notes</button>
                    </form>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="methodology-card">
                <h3>No live-watch items queued</h3>
                <p class="empty-state">Flag a preview story with `Watch live` from the desk to prepare it here.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
