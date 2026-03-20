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
$items = newsroom_recap_queue_items();

function newsroom_recap_datetime(string $value): string
{
    $stamp = strtotime($value);
    return $stamp === false ? $value : date('F j, Y g:i A', $stamp);
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Recap Queue | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Recap Workflow Queue</div>
            <div class="masthead__meta"><a href="/desk">Back to Desk</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">A working board for fast recaps and minutes reconciliation.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/desk">Desk</a>
    </nav>

    <h2 class="section-heading">Recap Queue</h2>
    <p class="section-intro">This page pulls together the stories that most likely need immediate post-meeting work: recap drafts first, then published items that should be checked against official minutes.</p>

    <section class="methodology-grid">
        <?php foreach ($items as $item): ?>
            <article class="methodology-card recap-card recap-card--<?= htmlspecialchars((string) $item['workflow_status']) ?>">
                <div class="story-meta-row story-meta-row--compact">
                    <span class="signal-pill"><?= htmlspecialchars((string) $item['workflow_label']) ?></span>
                    <?php if (!empty($item['body_name'])): ?>
                        <span class="signal-pill"><?= htmlspecialchars((string) $item['body_name']) ?></span>
                    <?php endif; ?>
                </div>
                <h3 class="story-headline"><a href="<?= htmlspecialchars((string) $item['public_url']) ?>"><?= htmlspecialchars((string) $item['headline']) ?></a></h3>
                <p class="story-summary"><?= htmlspecialchars((string) ($item['summary'] ?? '')) ?></p>
                <div class="editorial-item__meta-group">
                    <div class="editorial-item__meta editorial-item__meta--chip"><?= htmlspecialchars(newsroom_recap_datetime((string) $item['occurs_at'])) ?></div>
                    <?php if (!empty($item['location_name'])): ?>
                        <div class="editorial-item__meta editorial-item__meta--chip"><?= htmlspecialchars((string) $item['location_name']) ?></div>
                    <?php endif; ?>
                </div>
                <p class="editorial-next-action"><?= htmlspecialchars((string) $item['next_action']) ?></p>
                <div class="editorial-active-queue__actions">
                    <a href="/desk/recaps/<?= htmlspecialchars((string) $item['id']) ?>">Draft workspace</a>
                    <a href="<?= htmlspecialchars((string) $item['public_url']) ?>">Open story</a>
                    <?php if (!empty($item['agenda_url'])): ?>
                        <a href="<?= htmlspecialchars((string) $item['agenda_url']) ?>" target="_blank" rel="noopener noreferrer">Open agenda</a>
                    <?php endif; ?>
                    <?php if (!empty($item['minutes_url'])): ?>
                        <a href="<?= htmlspecialchars((string) $item['minutes_url']) ?>" target="_blank" rel="noopener noreferrer">Open minutes</a>
                    <?php endif; ?>
                </div>
                <?php $scaffold = $item['recap_scaffold'] ?? []; ?>
                <?php if (!empty($scaffold)): ?>
                    <div class="recap-scaffold">
                        <div class="recap-scaffold__section">
                            <strong>Suggested lede</strong>
                            <p><?= htmlspecialchars((string) ($scaffold['lede'] ?? '')) ?></p>
                        </div>
                        <div class="recap-scaffold__section">
                            <strong>Draft angle</strong>
                            <p><?= htmlspecialchars((string) ($scaffold['angle'] ?? '')) ?></p>
                        </div>
                        <?php if (!empty($scaffold['highlights'])): ?>
                            <div class="recap-scaffold__section">
                                <strong>Source highlights</strong>
                                <ul class="methodology-list">
                                    <?php foreach ($scaffold['highlights'] as $highlight): ?>
                                        <li><p><?= htmlspecialchars((string) $highlight) ?></p></li>
                                    <?php endforeach; ?>
                                </ul>
                            </div>
                        <?php endif; ?>
                        <?php if (!empty($scaffold['verification'])): ?>
                            <div class="recap-scaffold__section">
                                <strong>What to verify</strong>
                                <ul class="methodology-list">
                                    <?php foreach ($scaffold['verification'] as $check): ?>
                                        <li><p><?= htmlspecialchars((string) $check) ?></p></li>
                                    <?php endforeach; ?>
                                </ul>
                            </div>
                        <?php endif; ?>
                    </div>
                <?php endif; ?>
                <?php if (!empty($item['admin_notes'])): ?>
                    <div class="recap-card__notes">
                        <strong>Desk Notes</strong>
                        <p><?= htmlspecialchars((string) $item['admin_notes']) ?></p>
                    </div>
                <?php endif; ?>
            </article>
        <?php endforeach; ?>
    </section>
</div>
</body>
</html>
