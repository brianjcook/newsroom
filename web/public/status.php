<?php

declare(strict_types=1);

require_once __DIR__ . '/../bootstrap.php';
require_once __DIR__ . '/../lib/content.php';

$config = newsroom_config();
$runs = newsroom_recent_runs();
$diagnostics = newsroom_diagnostic_items();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Status | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div>
            <div class="masthead__meta">System Status</div>
            <h1 class="masthead__title"><a href="/" style="text-decoration: none;"><?= htmlspecialchars($config['site_name']) ?></a></h1>
            <div class="masthead__tagline">Recent pipeline runs and ingestion counts.</div>
        </div>
        <div class="masthead__meta"><?= date('F j, Y') ?></div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar.php">Calendar</a>
        <a href="/status.php">Status</a>
    </nav>

    <h2 class="section-heading">Recent Runs</h2>
    <section class="story-list">
        <?php if ($runs): ?>
            <?php foreach ($runs as $run): ?>
                <article class="story-card">
                    <div class="story-card__meta"><?= htmlspecialchars((string) $run['run_status']) ?></div>
                    <h3>Run #<?= htmlspecialchars((string) $run['id']) ?></h3>
                    <p>Started: <?= htmlspecialchars((string) $run['started_at']) ?></p>
                    <p>Finished: <?= htmlspecialchars((string) ($run['finished_at'] ?? 'In progress')) ?></p>
                    <p>Discovered: <?= htmlspecialchars((string) $run['items_discovered']) ?></p>
                    <p>Fetched: <?= htmlspecialchars((string) $run['documents_fetched']) ?></p>
                    <p>Extracted: <?= htmlspecialchars((string) $run['extractions_created']) ?></p>
                    <p>Meetings: <?= htmlspecialchars((string) $run['meetings_normalized']) ?></p>
                    <p>Stories: <?= htmlspecialchars((string) $run['stories_published']) ?></p>
                    <p>Events: <?= htmlspecialchars((string) $run['events_created']) ?></p>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="story-card">
                <h3>No runs yet</h3>
                <p class="empty-state">Run history will appear here once the worker has executed against the configured database.</p>
            </article>
        <?php endif; ?>
    </section>

    <h2 class="section-heading">Diagnostics</h2>
    <section class="story-list">
        <?php if ($diagnostics): ?>
            <?php foreach ($diagnostics as $item): ?>
                <article class="story-card">
                    <div class="story-card__meta"><?= htmlspecialchars((string) $item['status']) ?></div>
                    <h3><?= htmlspecialchars((string) ($item['title'] ?: 'Untitled source item')) ?></h3>
                    <p>Confidence: <?= htmlspecialchars((string) ($item['confidence_score'] ?? 'n/a')) ?></p>
                    <?php if (!empty($item['warnings_json'])): ?>
                        <p>Warnings: <?= htmlspecialchars((string) $item['warnings_json']) ?></p>
                    <?php endif; ?>
                    <p><a href="<?= htmlspecialchars((string) $item['canonical_url']) ?>">Source</a></p>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="story-card">
                <h3>No diagnostic items</h3>
                <p class="empty-state">Items that need review or have weak extraction confidence will appear here.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
