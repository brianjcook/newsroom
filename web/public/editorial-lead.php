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

$sourceItemId = (int) ($_GET['id'] ?? 0);
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $sourceItemId > 0) {
    $action = (string) ($_POST['action'] ?? 'save');
    newsroom_save_source_lead($sourceItemId, $_POST);
    if ($action === 'promote_brief') {
        $storyId = newsroom_promote_source_lead_to_brief($sourceItemId);
        header('Location: /desk/leads/' . $sourceItemId . '?promoted=' . (int) $storyId);
        exit;
    }
    header('Location: /desk/leads/' . $sourceItemId . '?saved=1');
    exit;
}

$config = newsroom_config();
$item = newsroom_source_lead_item($sourceItemId);
$saved = isset($_GET['saved']) && $_GET['saved'] === '1';
$promoted = isset($_GET['promoted']) ? (int) $_GET['promoted'] : 0;
$workflowOptions = newsroom_source_lead_workflow_options();
$priorityOptions = [
    'normal' => 'Normal',
    'high' => 'High',
    'must_cover' => 'Must cover',
];
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Source Lead Workspace | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Source Lead Workspace</div>
            <div class="masthead__meta"><a href="/desk/leads">Back to Source Leads</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Turn source leads into a reporting plan without auto-publishing outside material as your own reporting.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/desk">Desk</a>
    </nav>

    <?php if ($item): ?>
        <?php if ($saved): ?><p class="editorial-save-note">Source lead workspace saved.</p><?php endif; ?>
        <?php if ($promoted > 0): ?><p class="editorial-save-note">Brief draft created as story #<?= (int) $promoted ?>.</p><?php endif; ?>
        <section class="story-layout">
            <article>
                <div class="story-meta-row story-meta-row--compact">
                    <span class="signal-pill"><?= htmlspecialchars(newsroom_source_lead_type_label((string) $item['lead_type'])) ?></span>
                    <span class="story-card__meta"><?= htmlspecialchars((string) $item['source_name']) ?></span>
                    <span class="story-card__meta">Score <?= (int) ($item['effective_score'] ?? 0) ?></span>
                    <?php if (!empty($item['published_at'])): ?>
                        <span class="story-card__meta"><?= htmlspecialchars(newsroom_editorial_datetime((string) $item['published_at'])) ?></span>
                    <?php endif; ?>
                </div>
                <h2 class="story-headline"><?= htmlspecialchars((string) $item['title']) ?></h2>
                <p class="story-dek"><a href="<?= htmlspecialchars((string) $item['canonical_url']) ?>" target="_blank" rel="noopener noreferrer">Open original source</a></p>

                <form method="post" class="draft-workspace__form">
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Lead Assignment</h3>
                        <div class="reporting-grid">
                            <label class="editorial-inline-control editorial-inline-control--wide">
                                <span>Lead Title</span>
                                <input type="text" name="title" value="<?= htmlspecialchars((string) $item['title']) ?>">
                            </label>
                            <label class="editorial-inline-control">
                                <span>Status</span>
                                <select name="workflow_status">
                                    <?php foreach ($workflowOptions as $value => $label): ?>
                                        <option value="<?= htmlspecialchars($value) ?>"<?= (string) $item['workflow_status'] === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                                    <?php endforeach; ?>
                                </select>
                            </label>
                            <label class="editorial-inline-control">
                                <span>Priority</span>
                                <select name="priority">
                                    <?php foreach ($priorityOptions as $value => $label): ?>
                                        <option value="<?= htmlspecialchars($value) ?>"<?= (string) $item['priority'] === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                                    <?php endforeach; ?>
                                </select>
                            </label>
                            <label class="editorial-inline-control editorial-inline-control--wide">
                                <span>Reported Angle</span>
                                <input type="text" name="reported_angle" value="<?= htmlspecialchars((string) ($item['reported_angle'] ?? '')) ?>" placeholder="Why does this matter locally, and what is the real story angle?">
                            </label>
                        </div>
                    </section>

                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Writing Draft</h3>
                        <label class="editorial-inline-control">
                            <span>Draft Headline</span>
                            <input type="text" name="draft_headline" value="<?= htmlspecialchars((string) ($item['draft_headline'] ?? '')) ?>">
                        </label>
                        <label class="editorial-inline-control">
                            <span>Draft Dek</span>
                            <textarea name="draft_dek" rows="3"><?= htmlspecialchars((string) ($item['draft_dek'] ?? '')) ?></textarea>
                        </label>
                        <label class="editorial-inline-control">
                            <span>Draft Body</span>
                            <textarea name="draft_body" rows="16"><?= htmlspecialchars((string) ($item['draft_body'] ?? '')) ?></textarea>
                        </label>
                    </section>

                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Reporting Notes</h3>
                        <label class="editorial-inline-control">
                            <span>Questions To Answer</span>
                            <textarea name="questions_to_answer" rows="6"><?= htmlspecialchars((string) ($item['questions_to_answer'] ?? '')) ?></textarea>
                        </label>
                        <label class="editorial-inline-control">
                            <span>Fact-Check Notes</span>
                            <textarea name="fact_check_notes" rows="6"><?= htmlspecialchars((string) ($item['fact_check_notes'] ?? '')) ?></textarea>
                        </label>
                        <label class="editorial-inline-control">
                            <span>Next Steps</span>
                            <textarea name="next_steps_notes" rows="5"><?= htmlspecialchars((string) ($item['next_steps_notes'] ?? '')) ?></textarea>
                        </label>
                        <label class="editorial-inline-control">
                            <span>Desk Notes</span>
                            <textarea name="notes" rows="5"><?= htmlspecialchars((string) ($item['notes'] ?? '')) ?></textarea>
                        </label>
                    </section>

                    <div class="editorial-quick-actions">
                        <button type="submit" name="action" value="save">Save Source Lead</button>
                        <button type="submit" name="action" value="promote_brief">Create Brief Draft</button>
                    </div>
                </form>
            </article>

            <aside>
                <section class="story-information">
                    <div class="story-information__row">
                        <span class="story-information__label">Lead Type</span>
                        <span class="story-information__value"><?= htmlspecialchars(newsroom_source_lead_type_label((string) $item['lead_type'])) ?></span>
                    </div>
                    <div class="story-information__row">
                        <span class="story-information__label">Source</span>
                        <span class="story-information__value"><?= htmlspecialchars((string) $item['source_name']) ?></span>
                    </div>
                    <div class="story-information__row">
                        <span class="story-information__label">Published</span>
                        <span class="story-information__value"><?= !empty($item['published_at']) ? htmlspecialchars(newsroom_editorial_datetime((string) $item['published_at'])) : 'Unknown' ?></span>
                    </div>
                    <div class="story-information__row">
                        <span class="story-information__label">Original</span>
                        <span class="story-information__value"><a href="<?= htmlspecialchars((string) $item['canonical_url']) ?>" target="_blank" rel="noopener noreferrer">Open source</a></span>
                    </div>
                    <?php if (!empty($item['promoted_story_id'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Brief Draft</span>
                            <span class="story-information__value">Story #<?= (int) $item['promoted_story_id'] ?></span>
                        </div>
                    <?php endif; ?>
                </section>

                <?php if (!empty($item['signals'])): ?>
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Lead Signals</h3>
                        <ul class="editorial-signal-list">
                            <?php foreach ($item['signals'] as $signal): ?>
                                <li class="editorial-signal-list__item">
                                    <span class="editorial-signal-list__reason"><?= htmlspecialchars((string) ($signal['reason'] ?? '')) ?></span>
                                    <span class="editorial-signal-list__weight"><?= sprintf('%+d', (int) ($signal['weight'] ?? 0)) ?></span>
                                </li>
                            <?php endforeach; ?>
                        </ul>
                    </section>
                <?php endif; ?>

                <?php if (!empty($item['raw_meta']['excerpt'])): ?>
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Source Excerpt</h3>
                        <p><?= htmlspecialchars((string) $item['raw_meta']['excerpt']) ?></p>
                    </section>
                <?php endif; ?>
            </aside>
        </section>
    <?php else: ?>
        <h2 class="story-headline">Source lead not found</h2>
        <p class="empty-state">This source lead is no longer available.</p>
    <?php endif; ?>
</div>
</body>
</html>
