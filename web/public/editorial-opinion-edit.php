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
    newsroom_save_opinion_item($id, $_POST);
    header('Location: /desk/opinion/' . $id . '?saved=1');
    exit;
}

$config = newsroom_config();
$item = newsroom_opinion_item($id);
$saved = isset($_GET['saved']) && $_GET['saved'] === '1';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Opinion Editor | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Opinion Editor</div>
            <div class="masthead__meta"><a href="/desk/opinion">Back to Opinion</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Manual writing space for clearly labeled opinion.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/opinion">Opinion</a>
        <a href="/desk">Desk</a>
    </nav>

    <?php if ($item): ?>
        <?php if ($saved): ?><p class="editorial-save-note">Opinion piece saved.</p><?php endif; ?>
        <section class="story-layout">
            <article>
                <h2 class="story-headline"><?= htmlspecialchars((string) $item['headline']) ?></h2>
                <form method="post" class="draft-workspace__form">
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Publication</h3>
                        <div class="reporting-grid">
                            <label class="editorial-inline-control">
                                <span>Type</span>
                                <select name="story_type">
                                    <?php foreach (['editorial' => 'Editorial', 'column' => 'Column', 'letter' => 'Letter'] as $value => $label): ?>
                                        <option value="<?= htmlspecialchars($value) ?>"<?= (string) $item['story_type'] === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                                    <?php endforeach; ?>
                                </select>
                            </label>
                            <label class="editorial-inline-control">
                                <span>Status</span>
                                <select name="publish_status">
                                    <?php foreach (['draft' => 'Draft', 'published' => 'Published'] as $value => $label): ?>
                                        <option value="<?= htmlspecialchars($value) ?>"<?= (string) $item['publish_status'] === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                                    <?php endforeach; ?>
                                </select>
                            </label>
                            <label class="editorial-inline-control">
                                <span>Display Date</span>
                                <input type="text" name="display_date" value="<?= htmlspecialchars((string) ($item['display_date'] ?? date('Y-m-d H:i:s'))) ?>">
                            </label>
                            <label class="editorial-inline-control">
                                <span>Byline</span>
                                <input type="text" name="byline_name" value="<?= htmlspecialchars((string) ($item['byline_name'] ?? 'Wareham Times Editorial Board')) ?>">
                            </label>
                            <label class="editorial-inline-control">
                                <span>Byline Title</span>
                                <input type="text" name="byline_title" value="<?= htmlspecialchars((string) ($item['byline_title'] ?? 'Opinion')) ?>">
                            </label>
                        </div>
                    </section>

                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Story</h3>
                        <label class="editorial-inline-control">
                            <span>Headline</span>
                            <input type="text" name="headline" value="<?= htmlspecialchars((string) $item['headline']) ?>">
                        </label>
                        <label class="editorial-inline-control">
                            <span>Dek</span>
                            <textarea name="dek" rows="3"><?= htmlspecialchars((string) ($item['dek'] ?? '')) ?></textarea>
                        </label>
                        <label class="editorial-inline-control">
                            <span>Summary</span>
                            <textarea name="summary" rows="3"><?= htmlspecialchars((string) ($item['summary'] ?? '')) ?></textarea>
                        </label>
                        <label class="editorial-inline-control">
                            <span>Body</span>
                            <textarea name="body_text" rows="22"><?= htmlspecialchars((string) ($item['body_text'] ?? strip_tags((string) $item['body_html']))) ?></textarea>
                        </label>
                    </section>

                    <button type="submit">Save Opinion Piece</button>
                </form>
            </article>
            <aside class="footnotes">
                <div class="eyebrow">Public URL</div>
                <p><a href="<?= htmlspecialchars(newsroom_opinion_url_from_slug((string) $item['slug'])) ?>"><?= htmlspecialchars(newsroom_opinion_url_from_slug((string) $item['slug'])) ?></a></p>
                <p class="empty-state">Publishing here is manual. Keep opinion labels explicit and separate from public-record coverage.</p>
            </aside>
        </section>
    <?php else: ?>
        <h2 class="story-headline">Opinion item not found</h2>
    <?php endif; ?>
</div>
</body>
</html>
