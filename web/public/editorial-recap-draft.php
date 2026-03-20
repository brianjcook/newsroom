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
$id = (int) ($_GET['id'] ?? 0);
$item = newsroom_recap_queue_item($id);

function newsroom_recap_draft_datetime(?string $meetingDate, ?string $meetingTime): string
{
    $date = trim((string) $meetingDate);
    $time = trim((string) $meetingTime);
    if ($date === '') {
        return '';
    }
    $stamp = strtotime($date . ($time !== '' ? ' ' . $time : ''));
    return $stamp === false ? $date : date($time !== '' ? 'F j, Y \a\t g:i A' : 'F j, Y', $stamp);
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Recap Draft | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Recap Draft Workspace</div>
            <div class="masthead__meta"><a href="/desk/recaps">Back to Recap Queue</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">A structured starting shell for post-meeting reporting.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/desk">Desk</a>
    </nav>

    <?php if ($item): ?>
        <?php $draft = $item['draft_workspace'] ?? []; ?>
        <?php $scaffold = $item['recap_scaffold'] ?? []; ?>
        <section class="story-layout">
            <article>
                <div class="story-meta-row story-meta-row--compact">
                    <span class="signal-pill"><?= htmlspecialchars((string) $item['workflow_label']) ?></span>
                    <?php if (!empty($item['body_name'])): ?>
                        <span class="signal-pill"><?= htmlspecialchars((string) $item['body_name']) ?></span>
                    <?php endif; ?>
                    <?php if (!empty($item['meeting_date'])): ?>
                        <span class="story-card__meta"><?= htmlspecialchars(newsroom_recap_draft_datetime((string) $item['meeting_date'], (string) ($item['meeting_time'] ?? ''))) ?></span>
                    <?php endif; ?>
                </div>

                <h2 class="story-headline"><?= htmlspecialchars((string) ($draft['headline'] ?? 'Recap draft')) ?></h2>
                <div class="story-dek"><?= htmlspecialchars((string) ($draft['dek'] ?? '')) ?></div>

                <section class="draft-workspace">
                    <div class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Draft Shell</h3>
                        <pre class="draft-workspace__copy"><?= htmlspecialchars((string) ($draft['body'] ?? '')) ?></pre>
                    </div>

                    <div class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Current Story Summary</h3>
                        <p><?= htmlspecialchars((string) ($item['summary'] ?? '')) ?></p>
                    </div>
                </section>
            </article>

            <aside>
                <section class="story-information">
                    <div class="story-information__row">
                        <span class="story-information__label">Source Story</span>
                        <span class="story-information__value"><a href="<?= htmlspecialchars((string) $item['public_url']) ?>">Open published story</a></span>
                    </div>
                    <?php if (!empty($item['agenda_url'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Agenda</span>
                            <span class="story-information__value"><a href="<?= htmlspecialchars((string) $item['agenda_url']) ?>" target="_blank" rel="noopener noreferrer">Open official agenda</a></span>
                        </div>
                    <?php endif; ?>
                    <?php if (!empty($item['minutes_url'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Minutes</span>
                            <span class="story-information__value"><a href="<?= htmlspecialchars((string) $item['minutes_url']) ?>" target="_blank" rel="noopener noreferrer">Open posted minutes</a></span>
                        </div>
                    <?php endif; ?>
                    <?php if (!empty($item['location_name'])): ?>
                        <div class="story-information__row">
                            <span class="story-information__label">Location</span>
                            <span class="story-information__value"><?= htmlspecialchars((string) $item['location_name']) ?></span>
                        </div>
                    <?php endif; ?>
                </section>

                <?php if (!empty($scaffold['highlights'])): ?>
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Source Highlights</h3>
                        <ul class="methodology-list">
                            <?php foreach ($scaffold['highlights'] as $highlight): ?>
                                <li><p><?= htmlspecialchars((string) $highlight) ?></p></li>
                            <?php endforeach; ?>
                        </ul>
                    </section>
                <?php endif; ?>

                <?php if (!empty($scaffold['verification'])): ?>
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Verification Checklist</h3>
                        <ul class="methodology-list">
                            <?php foreach ($scaffold['verification'] as $check): ?>
                                <li><p><?= htmlspecialchars((string) $check) ?></p></li>
                            <?php endforeach; ?>
                        </ul>
                    </section>
                <?php endif; ?>

                <?php if (!empty($item['admin_notes'])): ?>
                    <section class="draft-workspace__block">
                        <h3 class="section-heading section-heading--tight">Desk Notes</h3>
                        <p><?= htmlspecialchars((string) $item['admin_notes']) ?></p>
                    </section>
                <?php endif; ?>
            </aside>
        </section>
    <?php else: ?>
        <section class="story-layout">
            <article>
                <h2 class="story-headline">Recap draft not found</h2>
                <p class="story-dek">This recap workspace could not be loaded from the current published queue.</p>
            </article>
        </section>
    <?php endif; ?>
</div>
</body>
</html>
