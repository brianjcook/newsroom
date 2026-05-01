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

if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'create') {
    $id = newsroom_create_ad_campaign();
    header('Location: /desk/ads/' . $id);
    exit;
}

$config = newsroom_config();
$campaigns = newsroom_ad_campaigns();
$slots = newsroom_ad_slots();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ad Space | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Ad Space</div>
            <div class="masthead__meta"><a href="/desk">Back to Desk</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Local sponsorship inventory, clearly labeled and separated from news coverage.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/desk">Desk</a>
    </nav>

    <div class="editorial-active-queue">
        <div class="editorial-active-queue__label">Inventory</div>
        <h3><?= count($slots) ?> slots / <?= count($campaigns) ?> campaigns</h3>
        <div class="editorial-active-queue__actions">
            <form method="post">
                <input type="hidden" name="action" value="create">
                <button type="submit">New Campaign</button>
            </form>
        </div>
    </div>

    <section class="archive-results">
        <?php foreach ($campaigns as $campaign): ?>
            <article class="archive-result">
                <div class="story-meta-row story-meta-row--compact">
                    <span class="signal-pill"><?= htmlspecialchars((string) $campaign['label']) ?></span>
                    <span class="story-card__meta"><?= htmlspecialchars((string) $campaign['slot_label']) ?></span>
                    <span class="story-card__meta"><?= htmlspecialchars(ucwords((string) $campaign['status'])) ?></span>
                </div>
                <h3><a href="/desk/ads/<?= (int) $campaign['id'] ?>"><?= htmlspecialchars((string) $campaign['headline']) ?></a></h3>
                <p class="archive-result__byline"><?= htmlspecialchars((string) $campaign['advertiser_name']) ?></p>
                <?php if (!empty($campaign['body_text'])): ?><p><?= htmlspecialchars(newsroom_truncate_text((string) $campaign['body_text'], 220)) ?></p><?php endif; ?>
            </article>
        <?php endforeach; ?>
        <?php if (!$campaigns): ?>
            <article class="archive-result">
                <h3>No campaigns yet</h3>
                <p class="empty-state">Create a draft campaign, assign it to a slot, then activate it when ready.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
