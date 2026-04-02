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
$workflowOptions = [
    'draft' => 'Draft in progress',
    'assigned' => 'Assigned',
    'watch_live' => 'Watch live',
    'follow_up_story' => 'Follow-up story',
    'done' => 'Done',
];
$priorityOptions = [
    'normal' => 'Normal',
    'high' => 'High',
    'must_cover' => 'Must cover',
];
$sourceTypeOptions = newsroom_follow_up_source_types();
$sourcePriorityOptions = newsroom_follow_up_source_priorities();
$outreachStatusOptions = newsroom_follow_up_outreach_statuses();
$quoteStatusOptions = newsroom_follow_up_quote_statuses();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Reporting Workspace | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Reporting Workspace</div>
            <div class="masthead__meta"><a href="/desk/follow-ups">Back to Follow-Ups</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Research notes, quote planning, fact checks, and draft writing for second-day reporting.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/desk">Desk</a>
    </nav>

    <?php if ($item): ?>
        <?php if ($saved): ?><p class="editorial-save-note">Reporting workspace saved.</p><?php endif; ?>
        <section class="story-layout">
            <article>
                <div class="story-meta-row story-meta-row--compact">
                    <span class="signal-pill"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['workflow_status']))) ?></span>
                    <span class="story-card__meta"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['priority']))) ?></span>
                    <span class="story-card__meta"><?= (int) ($item['source_count'] ?? 0) ?> sources</span>
                    <span class="story-card__meta"><?= (int) ($item['contact_count'] ?? 0) ?> contacts</span>
                </div>
                <h2 class="story-headline"><?= htmlspecialchars((string) $item['title']) ?></h2>
                <p class="story-dek">Built from <a href="<?= htmlspecialchars((string) $item['public_url']) ?>"><?= htmlspecialchars((string) $item['source_headline']) ?></a>.</p>

                <form method="post" class="draft-workspace__form">
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Assignment</h3>
                        <div class="reporting-grid">
                            <label class="editorial-inline-control">
                                <span>Follow-Up Title</span>
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
                                <input type="text" name="reported_angle" value="<?= htmlspecialchars((string) ($item['reported_angle'] ?? '')) ?>" placeholder="What is the clearest second-day angle?">
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

                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Research Sources</h3>
                        <div class="reporting-repeater">
                            <?php foreach (($item['sources'] ?? []) as $source): ?>
                                <div class="reporting-repeater__row">
                                    <div class="reporting-grid">
                                        <label class="editorial-inline-control">
                                            <span>Source Type</span>
                                            <select name="source_type[]">
                                                <?php foreach ($sourceTypeOptions as $value => $label): ?>
                                                    <option value="<?= htmlspecialchars($value) ?>"<?= (string) ($source['source_type'] ?? '') === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                                                <?php endforeach; ?>
                                            </select>
                                        </label>
                                        <label class="editorial-inline-control">
                                            <span>Priority</span>
                                            <select name="source_priority[]">
                                                <?php foreach ($sourcePriorityOptions as $value => $label): ?>
                                                    <option value="<?= htmlspecialchars($value) ?>"<?= (string) ($source['priority'] ?? '') === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                                                <?php endforeach; ?>
                                            </select>
                                        </label>
                                        <label class="editorial-inline-control editorial-inline-control--wide">
                                            <span>Title</span>
                                            <input type="text" name="source_title[]" value="<?= htmlspecialchars((string) ($source['title'] ?? '')) ?>">
                                        </label>
                                        <label class="editorial-inline-control editorial-inline-control--wide">
                                            <span>URL</span>
                                            <input type="text" name="source_url[]" value="<?= htmlspecialchars((string) ($source['source_url'] ?? '')) ?>">
                                        </label>
                                        <label class="editorial-inline-control">
                                            <span>Publisher / Owner</span>
                                            <input type="text" name="source_publisher[]" value="<?= htmlspecialchars((string) ($source['publisher'] ?? '')) ?>">
                                        </label>
                                        <label class="editorial-inline-control editorial-inline-control--wide">
                                            <span>Notes</span>
                                            <textarea name="source_notes[]" rows="4"><?= htmlspecialchars((string) ($source['notes'] ?? '')) ?></textarea>
                                        </label>
                                    </div>
                                </div>
                            <?php endforeach; ?>
                        </div>
                    </section>

                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">People To Contact</h3>
                        <p class="section-intro section-intro--tight">This is a planning layer only for now. Track who to contact, the status of outreach, and any usable quote once one exists.</p>
                        <div class="reporting-repeater">
                            <?php foreach (($item['contacts'] ?? []) as $contact): ?>
                                <div class="reporting-repeater__row">
                                    <div class="reporting-grid">
                                        <label class="editorial-inline-control">
                                            <span>Name</span>
                                            <input type="text" name="contact_name[]" value="<?= htmlspecialchars((string) ($contact['full_name'] ?? '')) ?>">
                                        </label>
                                        <label class="editorial-inline-control">
                                            <span>Role</span>
                                            <input type="text" name="contact_role_title[]" value="<?= htmlspecialchars((string) ($contact['role_title'] ?? '')) ?>">
                                        </label>
                                        <label class="editorial-inline-control">
                                            <span>Organization</span>
                                            <input type="text" name="contact_organization[]" value="<?= htmlspecialchars((string) ($contact['organization'] ?? '')) ?>">
                                        </label>
                                        <label class="editorial-inline-control">
                                            <span>Email</span>
                                            <input type="email" name="contact_email[]" value="<?= htmlspecialchars((string) ($contact['email'] ?? '')) ?>">
                                        </label>
                                        <label class="editorial-inline-control">
                                            <span>Outreach Status</span>
                                            <select name="contact_outreach_status[]">
                                                <?php foreach ($outreachStatusOptions as $value => $label): ?>
                                                    <option value="<?= htmlspecialchars($value) ?>"<?= (string) ($contact['outreach_status'] ?? '') === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                                                <?php endforeach; ?>
                                            </select>
                                        </label>
                                        <label class="editorial-inline-control">
                                            <span>Quote Status</span>
                                            <select name="contact_quote_status[]">
                                                <?php foreach ($quoteStatusOptions as $value => $label): ?>
                                                    <option value="<?= htmlspecialchars($value) ?>"<?= (string) ($contact['quote_status'] ?? '') === $value ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                                                <?php endforeach; ?>
                                            </select>
                                        </label>
                                        <label class="editorial-inline-control editorial-inline-control--wide">
                                            <span>Quote / Response</span>
                                            <textarea name="contact_quote_text[]" rows="4"><?= htmlspecialchars((string) ($contact['quote_text'] ?? '')) ?></textarea>
                                        </label>
                                        <label class="editorial-inline-control editorial-inline-control--wide">
                                            <span>Notes</span>
                                            <textarea name="contact_notes[]" rows="4"><?= htmlspecialchars((string) ($contact['notes'] ?? '')) ?></textarea>
                                        </label>
                                    </div>
                                </div>
                            <?php endforeach; ?>
                        </div>
                    </section>

                    <button type="submit">Save Reporting Workspace</button>
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

                <section class="story-information">
                    <div class="story-information__row">
                        <span class="story-information__label">Reporting status</span>
                        <span class="story-information__value"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['workflow_status']))) ?></span>
                    </div>
                    <div class="story-information__row">
                        <span class="story-information__label">Priority</span>
                        <span class="story-information__value"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['priority']))) ?></span>
                    </div>
                    <div class="story-information__row">
                        <span class="story-information__label">Sources tracked</span>
                        <span class="story-information__value"><?= (int) ($item['source_count'] ?? 0) ?></span>
                    </div>
                    <div class="story-information__row">
                        <span class="story-information__label">Contacts tracked</span>
                        <span class="story-information__value"><?= (int) ($item['contact_count'] ?? 0) ?></span>
                    </div>
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

                <?php if (!empty($item['reported_angle'])): ?>
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Current Angle</h3>
                        <p><?= htmlspecialchars((string) $item['reported_angle']) ?></p>
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
