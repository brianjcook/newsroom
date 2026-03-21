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

$id = (int) ($_GET['id'] ?? 0);
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $id > 0) {
    newsroom_save_follow_up_item($id, $_POST);
    header('Location: /desk/follow-ups/' . $id . '?saved=1');
    exit;
}

$config = newsroom_config();
$item = newsroom_follow_up_item($id);
$saved = isset($_GET['saved']) && $_GET['saved'] === '1';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Follow-Up Workspace | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Follow-Up Workspace</div>
            <div class="masthead__meta"><a href="/desk/follow-ups">Back to Follow-Ups</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Turn recap signals into a second-day or explanatory story plan.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/desk">Desk</a>
    </nav>

    <?php if ($item): ?>
        <?php if ($saved): ?><p class="editorial-save-note">Follow-up workspace saved.</p><?php endif; ?>
        <section class="story-layout">
            <article>
                <div class="story-meta-row story-meta-row--compact">
                    <span class="signal-pill"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['workflow_status']))) ?></span>
                    <span class="story-card__meta"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['priority']))) ?></span>
                </div>
                <h2 class="story-headline"><?= htmlspecialchars((string) $item['title']) ?></h2>
                <p class="story-dek">Built from <a href="<?= htmlspecialchars((string) $item['public_url']) ?>"><?= htmlspecialchars((string) $item['source_headline']) ?></a>.</p>
                <form method="post" class="draft-workspace__form">
                    <label class="editorial-inline-control">
                        <span>Follow-Up Title</span>
                        <input type="text" name="title" value="<?= htmlspecialchars((string) $item['title']) ?>">
                    </label>
                    <label class="editorial-inline-control">
                        <span>Status</span>
                        <select name="workflow_status">
                            <?php foreach (['draft' => 'Draft', 'assigned' => 'Assigned', 'watch_live' => 'Watch Live', 'done' => 'Done'] as $value => $label): ?>
                                <option value="<?= htmlspecialchars($value) ?>"<?= (string) $item['workflow_status'] === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                            <?php endforeach; ?>
                        </select>
                    </label>
                    <label class="editorial-inline-control">
                        <span>Priority</span>
                        <select name="priority">
                            <?php foreach (['normal' => 'Normal', 'high' => 'High', 'must_cover' => 'Must cover'] as $value => $label): ?>
                                <option value="<?= htmlspecialchars($value) ?>"<?= (string) $item['priority'] === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                            <?php endforeach; ?>
                        </select>
                    </label>
                    <label class="editorial-inline-control">
                        <span>Desk Notes</span>
                        <textarea name="notes" rows="5"><?= htmlspecialchars((string) ($item['notes'] ?? '')) ?></textarea>
                    </label>
                    <label class="editorial-inline-control">
                        <span>Draft Body</span>
                        <textarea name="draft_body" rows="14"><?= htmlspecialchars((string) ($item['draft_body'] ?? '')) ?></textarea>
                    </label>
                    <button type="submit">Save Follow-Up</button>
                </form>
            </article>
            <aside>
                <section class="draft-workspace__block">
                    <h3 class="section-heading section-heading--tight">Source Story</h3>
                    <p><a href="<?= htmlspecialchars((string) $item['public_url']) ?>"><?= htmlspecialchars((string) $item['source_headline']) ?></a></p>
                    <?php if (!empty($item['source_summary'])): ?>
                        <p><?= htmlspecialchars((string) $item['source_summary']) ?></p>
                    <?php endif; ?>
                </section>
                <?php if (!empty($item['topics'])): ?>
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Topics</h3>
                        <div class="topic-chip-row">
                            <?php foreach ($item['topics'] as $topic): ?>
                                <a class="topic-chip" href="<?= htmlspecialchars(newsroom_topic_url((string) $topic['slug'])) ?>"><?= htmlspecialchars((string) $topic['label']) ?></a>
                            <?php endforeach; ?>
                        </div>
                    </section>
                <?php endif; ?>
            </aside>
        </section>
    <?php else: ?>
        <h2 class="story-headline">Follow-up not found</h2>
        <p class="empty-state">This follow-up item is no longer available.</p>
    <?php endif; ?>
</div>
</body>
</html>
