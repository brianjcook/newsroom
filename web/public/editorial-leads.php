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
$sourceFilter = trim((string) ($_GET['source'] ?? 'all'));
$typeFilter = trim((string) ($_GET['lead_type'] ?? 'all'));
$statusFilter = trim((string) ($_GET['status'] ?? 'all'));
$priorityFilter = trim((string) ($_GET['priority'] ?? 'all'));
$recencyFilter = trim((string) ($_GET['recency'] ?? 'all'));
$sortFilter = trim((string) ($_GET['sort'] ?? 'score_desc'));

$sourceOptions = [];
$typeOptions = [];
foreach ($items as $item) {
    $sourceOptions[(string) $item['source_slug']] = (string) $item['source_name'];
    $typeOptions[(string) $item['lead_type']] = newsroom_source_lead_type_label((string) $item['lead_type']);
}
asort($sourceOptions);
asort($typeOptions);

$items = array_values(array_filter($items, static function (array $item) use ($sourceFilter, $typeFilter, $statusFilter, $priorityFilter, $recencyFilter): bool {
    if ($sourceFilter !== 'all' && (string) ($item['source_slug'] ?? '') !== $sourceFilter) {
        return false;
    }
    if ($typeFilter !== 'all' && (string) ($item['lead_type'] ?? '') !== $typeFilter) {
        return false;
    }
    if ($statusFilter !== 'all' && (string) ($item['workflow_status'] ?? '') !== $statusFilter) {
        return false;
    }
    if ($priorityFilter !== 'all' && (string) ($item['priority'] ?? '') !== $priorityFilter) {
        return false;
    }
    if ($recencyFilter !== 'all') {
        $stamp = strtotime((string) ($item['published_at'] ?? ''));
        if ($stamp === false) {
            return false;
        }
        $daysOld = (time() - $stamp) / 86400;
        if ($recencyFilter === '7d' && $daysOld > 7) {
            return false;
        }
        if ($recencyFilter === '30d' && $daysOld > 30) {
            return false;
        }
        if ($recencyFilter === '90d' && $daysOld > 90) {
            return false;
        }
    }
    return true;
}));

usort($items, static function (array $a, array $b) use ($sortFilter): int {
    switch ($sortFilter) {
        case 'date_desc':
            return strcmp((string) ($b['published_at'] ?? ''), (string) ($a['published_at'] ?? ''));
        case 'date_asc':
            return strcmp((string) ($a['published_at'] ?? ''), (string) ($b['published_at'] ?? ''));
        case 'score_asc':
            return ((int) ($a['effective_score'] ?? 0) <=> (int) ($b['effective_score'] ?? 0))
                ?: strcmp((string) ($b['published_at'] ?? ''), (string) ($a['published_at'] ?? ''));
        case 'score_desc':
        default:
            return ((int) ($b['effective_score'] ?? 0) <=> (int) ($a['effective_score'] ?? 0))
                ?: strcmp((string) ($b['published_at'] ?? ''), (string) ($a['published_at'] ?? ''));
    }
});
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

    <form method="get" class="editorial-filters archive-filters">
        <label>
            <span>Source</span>
            <select name="source">
                <option value="all"<?= $sourceFilter === 'all' ? ' selected' : '' ?>>All</option>
                <?php foreach ($sourceOptions as $slug => $label): ?>
                    <option value="<?= htmlspecialchars((string) $slug) ?>"<?= $sourceFilter === (string) $slug ? ' selected' : '' ?>><?= htmlspecialchars((string) $label) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>
            <span>Lead Type</span>
            <select name="lead_type">
                <option value="all"<?= $typeFilter === 'all' ? ' selected' : '' ?>>All</option>
                <?php foreach ($typeOptions as $slug => $label): ?>
                    <option value="<?= htmlspecialchars((string) $slug) ?>"<?= $typeFilter === (string) $slug ? ' selected' : '' ?>><?= htmlspecialchars((string) $label) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>
            <span>Status</span>
            <select name="status">
                <option value="all"<?= $statusFilter === 'all' ? ' selected' : '' ?>>All</option>
                <?php foreach (newsroom_source_lead_workflow_options() as $value => $label): ?>
                    <option value="<?= htmlspecialchars((string) $value) ?>"<?= $statusFilter === (string) $value ? ' selected' : '' ?>><?= htmlspecialchars((string) $label) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>
            <span>Priority</span>
            <select name="priority">
                <option value="all"<?= $priorityFilter === 'all' ? ' selected' : '' ?>>All</option>
                <option value="normal"<?= $priorityFilter === 'normal' ? ' selected' : '' ?>>Normal</option>
                <option value="high"<?= $priorityFilter === 'high' ? ' selected' : '' ?>>High</option>
                <option value="must_cover"<?= $priorityFilter === 'must_cover' ? ' selected' : '' ?>>Must cover</option>
            </select>
        </label>
        <label>
            <span>Recency</span>
            <select name="recency">
                <option value="all"<?= $recencyFilter === 'all' ? ' selected' : '' ?>>All</option>
                <option value="7d"<?= $recencyFilter === '7d' ? ' selected' : '' ?>>Past 7 days</option>
                <option value="30d"<?= $recencyFilter === '30d' ? ' selected' : '' ?>>Past 30 days</option>
                <option value="90d"<?= $recencyFilter === '90d' ? ' selected' : '' ?>>Past 90 days</option>
            </select>
        </label>
        <label>
            <span>Sort</span>
            <select name="sort">
                <option value="score_desc"<?= $sortFilter === 'score_desc' ? ' selected' : '' ?>>Score high-low</option>
                <option value="score_asc"<?= $sortFilter === 'score_asc' ? ' selected' : '' ?>>Score low-high</option>
                <option value="date_desc"<?= $sortFilter === 'date_desc' ? ' selected' : '' ?>>Newest first</option>
                <option value="date_asc"<?= $sortFilter === 'date_asc' ? ' selected' : '' ?>>Oldest first</option>
            </select>
        </label>
        <a class="editorial-filters__reset" href="/desk/leads">Reset</a>
        <button type="submit">Apply</button>
    </form>

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
