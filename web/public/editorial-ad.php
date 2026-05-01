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
    newsroom_save_ad_campaign($id, $_POST);
    header('Location: /desk/ads/' . $id . '?saved=1');
    exit;
}

$config = newsroom_config();
$campaign = newsroom_ad_campaign($id);
$slots = newsroom_ad_slots();
$saved = isset($_GET['saved']) && $_GET['saved'] === '1';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ad Campaign | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Ad Campaign</div>
            <div class="masthead__meta"><a href="/desk/ads">Back to Ads</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Manage local sponsor copy and placement.</div>
        </div>
    </header>

    <?php if ($campaign): ?>
        <?php if ($saved): ?><p class="editorial-save-note">Campaign saved.</p><?php endif; ?>
        <section class="story-layout">
            <article>
                <h2 class="story-headline"><?= htmlspecialchars((string) $campaign['headline']) ?></h2>
                <form method="post" class="draft-workspace__form">
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Placement</h3>
                        <div class="reporting-grid">
                            <label class="editorial-inline-control">
                                <span>Slot</span>
                                <select name="slot_id">
                                    <?php foreach ($slots as $slot): ?>
                                        <option value="<?= (int) $slot['id'] ?>"<?= (int) $campaign['slot_id'] === (int) $slot['id'] ? ' selected' : '' ?>><?= htmlspecialchars((string) $slot['label']) ?></option>
                                    <?php endforeach; ?>
                                </select>
                            </label>
                            <label class="editorial-inline-control">
                                <span>Status</span>
                                <select name="status">
                                    <?php foreach (['draft' => 'Draft', 'active' => 'Active', 'paused' => 'Paused', 'ended' => 'Ended'] as $value => $label): ?>
                                        <option value="<?= htmlspecialchars($value) ?>"<?= (string) $campaign['status'] === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                                    <?php endforeach; ?>
                                </select>
                            </label>
                            <label class="editorial-inline-control">
                                <span>Starts At</span>
                                <input type="text" name="starts_at" value="<?= htmlspecialchars((string) ($campaign['starts_at'] ?? '')) ?>">
                            </label>
                            <label class="editorial-inline-control">
                                <span>Ends At</span>
                                <input type="text" name="ends_at" value="<?= htmlspecialchars((string) ($campaign['ends_at'] ?? '')) ?>">
                            </label>
                        </div>
                    </section>
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Creative</h3>
                        <label class="editorial-inline-control">
                            <span>Advertiser</span>
                            <input type="text" name="advertiser_name" value="<?= htmlspecialchars((string) $campaign['advertiser_name']) ?>">
                        </label>
                        <label class="editorial-inline-control">
                            <span>Label</span>
                            <input type="text" name="label" value="<?= htmlspecialchars((string) $campaign['label']) ?>">
                        </label>
                        <label class="editorial-inline-control">
                            <span>Headline</span>
                            <input type="text" name="headline" value="<?= htmlspecialchars((string) $campaign['headline']) ?>">
                        </label>
                        <label class="editorial-inline-control">
                            <span>Body</span>
                            <textarea name="body_text" rows="5"><?= htmlspecialchars((string) ($campaign['body_text'] ?? '')) ?></textarea>
                        </label>
                        <label class="editorial-inline-control">
                            <span>Destination URL</span>
                            <input type="text" name="destination_url" value="<?= htmlspecialchars((string) ($campaign['destination_url'] ?? '')) ?>">
                        </label>
                        <label class="editorial-inline-control">
                            <span>Internal Notes</span>
                            <textarea name="notes" rows="5"><?= htmlspecialchars((string) ($campaign['notes'] ?? '')) ?></textarea>
                        </label>
                    </section>
                    <button type="submit">Save Campaign</button>
                </form>
            </article>
            <aside>
                <section class="ad-unit ad-unit--rail">
                    <div class="ad-unit__label"><?= htmlspecialchars((string) $campaign['label']) ?></div>
                    <strong><?= htmlspecialchars((string) $campaign['headline']) ?></strong>
                    <?php if (!empty($campaign['body_text'])): ?><p><?= htmlspecialchars((string) $campaign['body_text']) ?></p><?php endif; ?>
                    <?php if (!empty($campaign['destination_url'])): ?><a href="<?= htmlspecialchars((string) $campaign['destination_url']) ?>">Learn more</a><?php endif; ?>
                </section>
            </aside>
        </section>
    <?php else: ?>
        <h2 class="story-headline">Campaign not found</h2>
    <?php endif; ?>
</div>
</body>
</html>
