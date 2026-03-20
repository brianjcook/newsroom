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
$methodology = newsroom_editorial_methodology();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Desk Methodology | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Editorial News Desk Methodology</div>
            <div class="masthead__meta"><a href="/desk">Back to Desk</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">How the desk scores, sorts, and advances coverage.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/desk">Desk</a>
    </nav>

    <section class="methodology-intro">
        <h2 class="section-heading">How The Desk Works</h2>
        <p class="section-intro">The desk uses deterministic rules, not a black-box model score. Every item gets a score, a suggested coverage mode, topic tags, and a workflow state. You can override those by hand without losing the original signals.</p>
    </section>

    <section class="methodology-grid">
        <article class="methodology-card">
            <h3 class="methodology-card__title">Score Bands</h3>
            <ul class="methodology-list">
                <?php foreach ($methodology['score_bands'] as $band): ?>
                    <li>
                        <strong><?= htmlspecialchars((string) $band['label']) ?></strong>
                        <span><?= htmlspecialchars((string) $band['range']) ?></span>
                        <p><?= htmlspecialchars((string) $band['meaning']) ?></p>
                    </li>
                <?php endforeach; ?>
            </ul>
        </article>

        <article class="methodology-card">
            <h3 class="methodology-card__title">Story Signals</h3>
            <ul class="methodology-list">
                <?php foreach ($methodology['story_rules'] as $rule): ?>
                    <li>
                        <strong><?= htmlspecialchars((string) $rule['signal']) ?></strong>
                        <span><?= htmlspecialchars((string) $rule['weight']) ?></span>
                        <p><?= htmlspecialchars((string) $rule['note']) ?></p>
                    </li>
                <?php endforeach; ?>
            </ul>
        </article>

        <article class="methodology-card">
            <h3 class="methodology-card__title">Community Event Signals</h3>
            <ul class="methodology-list">
                <?php foreach ($methodology['community_rules'] as $rule): ?>
                    <li>
                        <strong><?= htmlspecialchars((string) $rule['signal']) ?></strong>
                        <span><?= htmlspecialchars((string) $rule['weight']) ?></span>
                        <p><?= htmlspecialchars((string) $rule['note']) ?></p>
                    </li>
                <?php endforeach; ?>
            </ul>
        </article>

        <article class="methodology-card">
            <h3 class="methodology-card__title">Workflow Lifecycle</h3>
            <ul class="methodology-list">
                <?php foreach ($methodology['workflow'] as $rule): ?>
                    <li>
                        <strong><?= htmlspecialchars((string) $rule['status']) ?></strong>
                        <p><?= htmlspecialchars((string) $rule['note']) ?></p>
                    </li>
                <?php endforeach; ?>
            </ul>
        </article>
    </section>
</div>
</body>
</html>
