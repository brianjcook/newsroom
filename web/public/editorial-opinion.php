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
    $id = newsroom_create_opinion_item();
    header('Location: /desk/opinion/' . $id);
    exit;
}

$config = newsroom_config();
$items = newsroom_opinion_items(80, true);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Opinion Desk | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Opinion Desk</div>
            <div class="masthead__meta"><a href="/desk">Back to Desk</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Create editorials, columns, and letters that stay clearly separated from news coverage.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/opinion">Opinion</a>
        <a href="/desk">Desk</a>
    </nav>

    <div class="editorial-active-queue">
        <div class="editorial-active-queue__label">Opinion Workflow</div>
        <h3>Public opinion is manually written and labeled.</h3>
        <div class="editorial-active-queue__actions">
            <form method="post">
                <input type="hidden" name="action" value="create">
                <button type="submit">New Opinion Piece</button>
            </form>
        </div>
    </div>

    <section class="archive-results">
        <?php foreach ($items as $item): ?>
            <article class="archive-result">
                <div class="story-meta-row story-meta-row--compact">
                    <span class="signal-pill"><?= htmlspecialchars((string) $item['label']) ?></span>
                    <span class="story-card__meta"><?= htmlspecialchars(ucwords((string) $item['publish_status'])) ?></span>
                    <span class="story-card__meta"><?= htmlspecialchars(newsroom_editorial_datetime((string) ($item['display_date'] ?? $item['published_at'] ?? ''))) ?></span>
                </div>
                <h3><a href="/desk/opinion/<?= (int) $item['id'] ?>"><?= htmlspecialchars((string) $item['headline']) ?></a></h3>
                <p class="archive-result__byline">By <?= htmlspecialchars((string) $item['byline']['name']) ?></p>
                <?php if (!empty($item['summary'])): ?><p><?= htmlspecialchars(newsroom_truncate_text((string) $item['summary'], 220)) ?></p><?php endif; ?>
            </article>
        <?php endforeach; ?>
        <?php if (!$items): ?>
            <article class="archive-result">
                <h3>No opinion drafts yet</h3>
                <p class="empty-state">Create the first editorial from this desk.</p>
            </article>
        <?php endif; ?>
    </section>
</div>
</body>
</html>
