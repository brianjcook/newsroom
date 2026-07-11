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
$runs = newsroom_recent_runs();
$diagnostics = newsroom_diagnostic_items();
$contextStatus = newsroom_context_status();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Status | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">System Status</div>
            <div class="masthead__meta"><?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Recent pipeline runs and ingestion counts.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
    </nav>

    <h2 class="section-heading">Context Layer</h2>
    <section class="data-ledger">
        <?php if (!empty($contextStatus['available'])): ?>
            <?php $summary = $contextStatus['summary'] ?? []; ?>
            <article class="data-row">
                <div class="story-card__meta">Active</div>
                <h3>Automated public-record context</h3>
                <p class="run-metric">Entities: <strong><?= htmlspecialchars((string) ($summary['entity_count'] ?? 0)) ?></strong></p>
                <p class="run-metric">Observations: <strong><?= htmlspecialchars((string) ($summary['observation_count'] ?? 0)) ?></strong></p>
                <p class="run-metric">Public observations: <strong><?= htmlspecialchars((string) ($summary['public_observation_count'] ?? 0)) ?></strong></p>
                <p class="run-metric">Guarded observations: <strong><?= htmlspecialchars((string) ($summary['guarded_observation_count'] ?? 0)) ?></strong></p>
                <p class="run-metric">Story links: <strong><?= htmlspecialchars((string) ($summary['story_link_count'] ?? 0)) ?></strong></p>
                <p class="run-metric">Context sources: <strong><?= htmlspecialchars((string) ($summary['context_source_count'] ?? 0)) ?></strong></p>
                <p class="run-metric">Wareham Media items: <strong><?= htmlspecialchars((string) ($summary['recording_item_count'] ?? 0)) ?></strong></p>
            </article>
            <article class="data-row">
                <div class="story-card__meta">Observation Types</div>
                <h3>Public context mix</h3>
                <?php if (!empty($contextStatus['types'])): ?>
                    <?php foreach ($contextStatus['types'] as $typeRow): ?>
                        <p class="run-metric"><?= htmlspecialchars(newsroom_public_observation_label((string) $typeRow['observation_type'])) ?>: <strong><?= htmlspecialchars((string) $typeRow['count_all']) ?></strong></p>
                    <?php endforeach; ?>
                <?php else: ?>
                    <p class="empty-state">No public observations have been indexed yet.</p>
                <?php endif; ?>
            </article>
            <article class="data-row">
                <div class="story-card__meta">Source Modes</div>
                <h3>Automation guardrails</h3>
                <?php foreach (($contextStatus['modes'] ?? []) as $modeRow): ?>
                    <p class="run-metric"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $modeRow['automation_mode']))) ?>: <strong><?= htmlspecialchars((string) $modeRow['source_count']) ?></strong></p>
                <?php endforeach; ?>
            </article>
        <?php else: ?>
            <article class="data-row">
                <div class="story-card__meta">Pending</div>
                <h3>Context layer not initialized</h3>
                <p class="empty-state">The next worker run will create the context tables and source governance fields.</p>
            </article>
        <?php endif; ?>
    </section>

    <h2 class="section-heading">Recent Runs</h2>
    <section class="data-ledger">
        <?php if ($runs): ?>
            <?php foreach ($runs as $run): ?>
                <article class="data-row">
                    <div class="story-card__meta"><?= htmlspecialchars((string) $run['run_status']) ?></div>
                    <h3>Run #<?= htmlspecialchars((string) $run['id']) ?></h3>
                    <p>Started: <?= htmlspecialchars((string) $run['started_at']) ?></p>
                    <p>Finished: <?= htmlspecialchars((string) ($run['finished_at'] ?? 'In progress')) ?></p>
                    <p class="run-metric">Discovered: <strong><?= htmlspecialchars((string) $run['items_discovered']) ?></strong></p>
                    <p class="run-metric">Fetched: <strong><?= htmlspecialchars((string) $run['documents_fetched']) ?></strong></p>
                    <p class="run-metric">Extracted: <strong><?= htmlspecialchars((string) $run['extractions_created']) ?></strong></p>
                    <p class="run-metric">Meetings: <strong><?= htmlspecialchars((string) $run['meetings_normalized']) ?></strong></p>
                    <p class="run-metric">Stories Created: <strong><?= htmlspecialchars((string) $run['stories_published']) ?></strong></p>
                    <p class="run-metric">Stories Updated: <strong><?= htmlspecialchars((string) ($run['stories_updated'] ?? 0)) ?></strong></p>
                    <p class="run-metric">Events Created: <strong><?= htmlspecialchars((string) $run['events_created']) ?></strong></p>
                    <p class="run-metric">Events Updated: <strong><?= htmlspecialchars((string) ($run['events_updated'] ?? 0)) ?></strong></p>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="data-row">
                <h3>No runs yet</h3>
                <p class="empty-state">Run history will appear here once the worker has executed against the configured database.</p>
            </article>
        <?php endif; ?>
    </section>

    <h2 class="section-heading">Diagnostics</h2>
    <section class="data-ledger">
        <?php if ($diagnostics): ?>
            <?php foreach ($diagnostics as $item): ?>
                <article class="data-row">
                    <div class="story-card__meta"><?= htmlspecialchars((string) $item['status']) ?></div>
                    <h3><?= htmlspecialchars((string) ($item['title'] ?: 'Untitled source item')) ?></h3>
                    <p>Confidence: <?= htmlspecialchars((string) ($item['confidence_score'] ?? 'n/a')) ?></p>
                    <?php
                    $reviewFlags = [];
                    if (!empty($item['structured_json'])) {
                        $structured = json_decode((string) $item['structured_json'], true);
                        if (is_array($structured) && !empty($structured['review_flags']) && is_array($structured['review_flags'])) {
                            $reviewFlags = $structured['review_flags'];
                        }
                    }
                    ?>
                    <?php if ($reviewFlags): ?>
                        <p>Review flags: <?= htmlspecialchars(implode(', ', array_map('strval', $reviewFlags))) ?></p>
                    <?php endif; ?>
                    <?php if (!empty($item['warnings_json'])): ?>
                        <p>Warnings: <?= htmlspecialchars((string) $item['warnings_json']) ?></p>
                    <?php endif; ?>
                    <p><a href="<?= htmlspecialchars((string) $item['canonical_url']) ?>">Source</a></p>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="data-row">
                <h3>No diagnostic items</h3>
                <p class="empty-state">Items that need review or have weak extraction confidence will appear here.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
