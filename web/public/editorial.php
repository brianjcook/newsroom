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

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    newsroom_update_editorial_override($_POST);
    header('Location: /desk?saved=1');
    exit;
}

$config = newsroom_config();
$items = newsroom_editorial_items();
$saved = isset($_GET['saved']) && $_GET['saved'] === '1';
$entityFilter = trim((string) ($_GET['entity'] ?? 'all'));
$coverageFilter = trim((string) ($_GET['coverage'] ?? 'all'));
$visibilityFilter = trim((string) ($_GET['visibility'] ?? 'all'));
$workflowFilter = trim((string) ($_GET['workflow'] ?? 'all'));
$watchFilter = trim((string) ($_GET['watch_live'] ?? 'all'));
$followUpFilter = trim((string) ($_GET['follow_up'] ?? 'all'));
$topicFilter = trim((string) ($_GET['topic'] ?? 'all'));
$bodyFilter = trim((string) ($_GET['body'] ?? 'all'));
$queueFilter = trim((string) ($_GET['queue'] ?? ''));
$queuePresets = newsroom_editorial_queue_presets();
$defaultSort = 'score_desc';
if ($queueFilter !== '' && isset($queuePresets[$queueFilter])) {
    $presetFilters = $queuePresets[$queueFilter]['filters'];
    if ($entityFilter === 'all' && isset($presetFilters['entity'])) {
        $entityFilter = (string) $presetFilters['entity'];
    }
    if ($coverageFilter === 'all' && isset($presetFilters['coverage'])) {
        $coverageFilter = (string) $presetFilters['coverage'];
    }
    if ($workflowFilter === 'all' && isset($presetFilters['workflow'])) {
        $workflowFilter = (string) $presetFilters['workflow'];
    }
    if ($watchFilter === 'all' && isset($presetFilters['watch_live'])) {
        $watchFilter = (string) $presetFilters['watch_live'];
    }
    if ($followUpFilter === 'all' && isset($presetFilters['follow_up'])) {
        $followUpFilter = (string) $presetFilters['follow_up'];
    }
    if ($topicFilter === 'all' && isset($presetFilters['topic'])) {
        $topicFilter = (string) $presetFilters['topic'];
    }
    if ($bodyFilter === 'all' && isset($presetFilters['body'])) {
        $bodyFilter = (string) $presetFilters['body'];
    }
    if (empty($_GET['sort']) && isset($presetFilters['sort'])) {
        $defaultSort = (string) $presetFilters['sort'];
    }
}
$sortFilter = trim((string) ($_GET['sort'] ?? $defaultSort));
$workflowOptions = newsroom_workflow_options();

$topicOptions = [];
$bodyOptions = [];
foreach ($items as $item) {
    $bodyName = trim((string) ($item['body_name'] ?? ''));
    if ($bodyName !== '') {
        $bodyOptions[$bodyName] = $bodyName;
    }

    foreach (newsroom_parse_topics($item['topic_tags_json'] ?? null) as $topic) {
        $topicOptions[$topic['slug']] = $topic['label'];
    }
}
asort($topicOptions);
asort($bodyOptions);

$items = array_values(array_filter($items, static function (array $item) use ($entityFilter, $coverageFilter, $visibilityFilter, $workflowFilter, $watchFilter, $followUpFilter, $topicFilter, $bodyFilter): bool {
    if ($entityFilter !== 'all' && (string) $item['entity_type'] !== $entityFilter) {
        return false;
    }
    if ($coverageFilter !== 'all' && (string) $item['effective_coverage_mode'] !== $coverageFilter) {
        return false;
    }
    if ($visibilityFilter === 'hidden' && empty($item['is_hidden'])) {
        return false;
    }
    if ($visibilityFilter === 'visible' && !empty($item['is_hidden'])) {
        return false;
    }
    if ($workflowFilter !== 'all' && (string) ($item['workflow_status'] ?? '') !== $workflowFilter) {
        return false;
    }
    if ($watchFilter === 'watching' && empty($item['watch_live'])) {
        return false;
    }
    if ($watchFilter === 'not_watching' && !empty($item['watch_live'])) {
        return false;
    }
    if ($followUpFilter === 'needed' && empty($item['follow_up_needed'])) {
        return false;
    }
    if ($followUpFilter === 'not_needed' && !empty($item['follow_up_needed'])) {
        return false;
    }
    if ($bodyFilter !== 'all' && (string) ($item['body_name'] ?? '') !== $bodyFilter) {
        return false;
    }
    if ($topicFilter !== 'all') {
        $topicSlugs = array_map(static function (array $topic): string {
            return (string) $topic['slug'];
        }, newsroom_parse_topics($item['topic_tags_json'] ?? null));
        if (!in_array($topicFilter, $topicSlugs, true)) {
            return false;
        }
    }
    return true;
}));

usort($items, static function (array $a, array $b) use ($sortFilter): int {
    switch ($sortFilter) {
        case 'score_asc':
            return ((int) $a['effective_score'] <=> (int) $b['effective_score']) ?: strcmp((string) $a['occurs_at'], (string) $b['occurs_at']);
        case 'date_desc':
            return strcmp((string) $b['occurs_at'], (string) $a['occurs_at']) ?: ((int) $b['effective_score'] <=> (int) $a['effective_score']);
        case 'date_asc':
            return strcmp((string) $a['occurs_at'], (string) $b['occurs_at']) ?: ((int) $b['effective_score'] <=> (int) $a['effective_score']);
        case 'score_desc':
        default:
            return ((int) $b['effective_score'] <=> (int) $a['effective_score']) ?: strcmp((string) $a['occurs_at'], (string) $b['occurs_at']);
    }
});

$queueSummary = newsroom_editorial_queue_summary($items);
$activeQueue = ($queueFilter !== '' && isset($queuePresets[$queueFilter])) ? $queuePresets[$queueFilter] : null;

function newsroom_editorial_queue_url(string $queueKey, array $filters = []): string
{
    $query = array_merge(['queue' => $queueKey], $filters);
    return '/desk?' . http_build_query($query);
}

function newsroom_editorial_queue_actions(?string $queueFilter): array
{
    switch ($queueFilter) {
        case 'watch_live':
            return [
                ['label' => 'Stories Only', 'url' => newsroom_editorial_queue_url('watch_live', ['entity' => 'story'])],
                ['label' => 'Upcoming First', 'url' => newsroom_editorial_queue_url('watch_live', ['sort' => 'date_asc'])],
                ['label' => 'Methodology', 'url' => '/desk/methodology'],
            ];
        case 'recap_needed':
            return [
                ['label' => 'Stories Only', 'url' => newsroom_editorial_queue_url('recap_needed', ['entity' => 'story'])],
                ['label' => 'Newest First', 'url' => newsroom_editorial_queue_url('recap_needed', ['sort' => 'date_desc'])],
                ['label' => 'Methodology', 'url' => '/desk/methodology'],
            ];
        case 'minutes_reconcile':
            return [
                ['label' => 'Stories Only', 'url' => newsroom_editorial_queue_url('minutes_reconcile', ['entity' => 'story'])],
                ['label' => 'Latest Meetings First', 'url' => newsroom_editorial_queue_url('minutes_reconcile', ['sort' => 'date_desc'])],
                ['label' => 'Methodology', 'url' => '/desk/methodology'],
            ];
        case 'follow_up_story':
            return [
                ['label' => 'Highest Score First', 'url' => newsroom_editorial_queue_url('follow_up_story', ['sort' => 'score_desc'])],
                ['label' => 'Stories Only', 'url' => newsroom_editorial_queue_url('follow_up_story', ['entity' => 'story'])],
                ['label' => 'Methodology', 'url' => '/desk/methodology'],
            ];
        case 'must_cover':
            return [
                ['label' => 'Upcoming First', 'url' => newsroom_editorial_queue_url('must_cover', ['sort' => 'date_asc'])],
                ['label' => 'Stories Only', 'url' => newsroom_editorial_queue_url('must_cover', ['entity' => 'story'])],
                ['label' => 'Methodology', 'url' => '/desk/methodology'],
            ];
        default:
            return [];
    }
}

$queueActions = newsroom_editorial_queue_actions($queueFilter);

function newsroom_editorial_datetime(string $value): string
{
    $stamp = strtotime($value);
    if ($stamp === false) {
        return $value;
    }
    if (date('H:i:s', $stamp) === '00:00:00') {
        return date('F j, Y', $stamp);
    }
    return date('F j, Y g:i A', $stamp);
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Editorial News Desk | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Editorial News Desk</div>
            <div class="masthead__meta"><a href="/desk/methodology">Methodology</a> / <a href="/desk?logout=1">Log out</a> / <?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Transparent ranking, coverage suggestions, and manual editorial overrides.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
    </nav>

    <h2 class="section-heading">Newsworthiness Queue</h2>
    <p class="section-intro">Scores are deterministic and inspectable. The desk can override the score, coverage mode, and visibility without losing the underlying factor breakdown.</p>
    <?php if ($saved): ?>
        <p class="editorial-save-note">Editorial overrides saved.</p>
    <?php endif; ?>
    <?php if ($activeQueue): ?>
        <section class="editorial-active-queue">
            <div class="editorial-active-queue__label">Focused queue</div>
            <h3><?= htmlspecialchars((string) $activeQueue['label']) ?></h3>
            <p><?= htmlspecialchars((string) $activeQueue['description']) ?></p>
            <?php if ($queueActions): ?>
                <div class="editorial-active-queue__actions">
                    <?php foreach ($queueActions as $action): ?>
                        <a href="<?= htmlspecialchars((string) $action['url']) ?>"><?= htmlspecialchars((string) $action['label']) ?></a>
                    <?php endforeach; ?>
                </div>
            <?php endif; ?>
        </section>
    <?php endif; ?>

    <section class="editorial-explainer">
        <p>The current score emphasizes civic impact, public interest, timeliness, and body priority. It subtracts points for routine recurring meetings and low-signal appointment-only agendas.</p>
        <p>The workflow is intended as a newsroom lifecycle: preview published, watch live, recap needed, minutes reconcile, follow-up story, and done.</p>
        <p><a href="/desk/methodology">View the full methodology and scoring signals.</a></p>
    </section>

    <form method="get" class="editorial-filters">
        <label>
            <span>Entity</span>
            <select name="entity">
                <option value="all"<?= $entityFilter === 'all' ? ' selected' : '' ?>>All</option>
                <option value="story"<?= $entityFilter === 'story' ? ' selected' : '' ?>>Stories</option>
                <option value="community_event"<?= $entityFilter === 'community_event' ? ' selected' : '' ?>>Community events</option>
            </select>
        </label>
        <label>
            <span>Coverage</span>
            <select name="coverage">
                <option value="all"<?= $coverageFilter === 'all' ? ' selected' : '' ?>>All</option>
                <option value="calendar_only"<?= $coverageFilter === 'calendar_only' ? ' selected' : '' ?>>Calendar only</option>
                <option value="brief"<?= $coverageFilter === 'brief' ? ' selected' : '' ?>>Brief</option>
                <option value="full_story"<?= $coverageFilter === 'full_story' ? ' selected' : '' ?>>Full story</option>
                <option value="must_cover"<?= $coverageFilter === 'must_cover' ? ' selected' : '' ?>>Must cover</option>
            </select>
        </label>
        <label>
            <span>Visibility</span>
            <select name="visibility">
                <option value="all"<?= $visibilityFilter === 'all' ? ' selected' : '' ?>>All</option>
                <option value="visible"<?= $visibilityFilter === 'visible' ? ' selected' : '' ?>>Visible</option>
                <option value="hidden"<?= $visibilityFilter === 'hidden' ? ' selected' : '' ?>>Hidden</option>
            </select>
        </label>
        <label>
            <span>Workflow</span>
            <select name="workflow">
                <option value="all"<?= $workflowFilter === 'all' ? ' selected' : '' ?>>All</option>
                <?php foreach ($workflowOptions as $workflowValue => $workflowLabel): ?>
                    <option value="<?= htmlspecialchars((string) $workflowValue) ?>"<?= $workflowFilter === (string) $workflowValue ? ' selected' : '' ?>><?= htmlspecialchars((string) $workflowLabel) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>
            <span>Watch Live</span>
            <select name="watch_live">
                <option value="all"<?= $watchFilter === 'all' ? ' selected' : '' ?>>All</option>
                <option value="watching"<?= $watchFilter === 'watching' ? ' selected' : '' ?>>Watch live</option>
                <option value="not_watching"<?= $watchFilter === 'not_watching' ? ' selected' : '' ?>>Not flagged</option>
            </select>
        </label>
        <label>
            <span>Follow Up</span>
            <select name="follow_up">
                <option value="all"<?= $followUpFilter === 'all' ? ' selected' : '' ?>>All</option>
                <option value="needed"<?= $followUpFilter === 'needed' ? ' selected' : '' ?>>Needed</option>
                <option value="not_needed"<?= $followUpFilter === 'not_needed' ? ' selected' : '' ?>>Not needed</option>
            </select>
        </label>
        <label>
            <span>Topic</span>
            <select name="topic">
                <option value="all"<?= $topicFilter === 'all' ? ' selected' : '' ?>>All</option>
                <?php foreach ($topicOptions as $topicSlug => $topicLabel): ?>
                    <option value="<?= htmlspecialchars((string) $topicSlug) ?>"<?= $topicFilter === (string) $topicSlug ? ' selected' : '' ?>><?= htmlspecialchars((string) $topicLabel) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>
            <span>Body</span>
            <select name="body">
                <option value="all"<?= $bodyFilter === 'all' ? ' selected' : '' ?>>All</option>
                <?php foreach ($bodyOptions as $bodyName): ?>
                    <option value="<?= htmlspecialchars((string) $bodyName) ?>"<?= $bodyFilter === (string) $bodyName ? ' selected' : '' ?>><?= htmlspecialchars((string) $bodyName) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>
            <span>Sort</span>
            <select name="sort">
                <option value="score_desc"<?= $sortFilter === 'score_desc' ? ' selected' : '' ?>>Score high-low</option>
                <option value="score_asc"<?= $sortFilter === 'score_asc' ? ' selected' : '' ?>>Score low-high</option>
                <option value="date_asc"<?= $sortFilter === 'date_asc' ? ' selected' : '' ?>>Date soonest</option>
                <option value="date_desc"<?= $sortFilter === 'date_desc' ? ' selected' : '' ?>>Date latest</option>
            </select>
        </label>
        <a class="editorial-filters__reset" href="/desk">Reset</a>
        <button type="submit">Apply</button>
    </form>

    <section class="editorial-queue-strip">
        <a class="editorial-queue-card<?= $queueFilter === 'watch_live' ? ' editorial-queue-card--active' : '' ?>" href="<?= htmlspecialchars(newsroom_editorial_queue_url('watch_live')) ?>">
            <span class="editorial-queue-card__label">Watch Live</span>
            <strong><?= htmlspecialchars((string) $queueSummary['watch_live']) ?></strong>
        </a>
        <a class="editorial-queue-card<?= $queueFilter === 'recap_needed' ? ' editorial-queue-card--active' : '' ?>" href="<?= htmlspecialchars(newsroom_editorial_queue_url('recap_needed')) ?>">
            <span class="editorial-queue-card__label">Recap Needed</span>
            <strong><?= htmlspecialchars((string) $queueSummary['recap_needed']) ?></strong>
        </a>
        <a class="editorial-queue-card<?= $queueFilter === 'minutes_reconcile' ? ' editorial-queue-card--active' : '' ?>" href="<?= htmlspecialchars(newsroom_editorial_queue_url('minutes_reconcile')) ?>">
            <span class="editorial-queue-card__label">Minutes Reconcile</span>
            <strong><?= htmlspecialchars((string) $queueSummary['minutes_reconcile']) ?></strong>
        </a>
        <a class="editorial-queue-card<?= $queueFilter === 'follow_up_story' ? ' editorial-queue-card--active' : '' ?>" href="<?= htmlspecialchars(newsroom_editorial_queue_url('follow_up_story')) ?>">
            <span class="editorial-queue-card__label">Follow-Up Story</span>
            <strong><?= htmlspecialchars((string) $queueSummary['follow_up_story']) ?></strong>
        </a>
        <a class="editorial-queue-card<?= $queueFilter === 'must_cover' ? ' editorial-queue-card--active' : '' ?>" href="<?= htmlspecialchars(newsroom_editorial_queue_url('must_cover')) ?>">
            <span class="editorial-queue-card__label">Must Cover</span>
            <strong><?= htmlspecialchars((string) $queueSummary['must_cover']) ?></strong>
        </a>
    </section>

    <section class="editorial-table-wrap">
        <table class="editorial-table">
            <thead>
            <tr>
                <th>Item</th>
                <th>When</th>
                <th>Type</th>
                <th>Score</th>
                <th>Signals</th>
                <th>Topics</th>
                <th>Coverage</th>
                <th>Notes</th>
            </tr>
            </thead>
            <tbody>
            <?php foreach ($items as $item): ?>
                <tr class="editorial-table__row editorial-table__row--<?= htmlspecialchars((string) ($item['workflow_status'] ?? 'monitor')) ?>">
                    <?php $formId = 'editorial-item-' . (string) $item['entity_type'] . '-' . (string) $item['entity_id']; ?>
                    <td>
                        <div class="editorial-item__title"><?= htmlspecialchars((string) $item['title']) ?></div>
                        <div class="editorial-item__meta-group">
                            <?php if (!empty($item['body_name'])): ?>
                                <div class="editorial-item__meta editorial-item__meta--chip"><?= htmlspecialchars((string) $item['body_name']) ?></div>
                            <?php endif; ?>
                            <div class="editorial-item__meta editorial-item__meta--chip"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['entity_type']))) ?></div>
                            <div class="editorial-item__meta editorial-item__meta--chip"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['item_type']))) ?></div>
                            <?php if (!empty($item['status_label'])): ?>
                                <div class="editorial-item__meta editorial-item__meta--chip"><?= htmlspecialchars((string) $item['status_label']) ?></div>
                            <?php endif; ?>
                            <div class="editorial-item__meta editorial-item__meta--chip editorial-item__meta--workflow"><?= htmlspecialchars((string) $item['workflow_label']) ?></div>
                        </div>
                        <?php if (!empty($item['public_url'])): ?>
                            <div class="editorial-item__meta editorial-item__meta--link"><a href="<?= htmlspecialchars((string) $item['public_url']) ?>"<?= $item['entity_type'] === 'community_event' ? ' target="_blank" rel="noopener noreferrer"' : '' ?>>Open item</a></div>
                        <?php endif; ?>
                    </td>
                    <td class="editorial-table__when"><?= htmlspecialchars(newsroom_editorial_datetime((string) $item['occurs_at'])) ?></td>
                    <td>
                        <div class="editorial-item__meta-label">Current Workflow</div>
                        <div class="editorial-item__meta-value"><?= htmlspecialchars((string) $item['workflow_label']) ?></div>
                        <div class="editorial-item__meta-label">Surface</div>
                        <div class="editorial-item__meta-value"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['effective_coverage_mode']))) ?></div>
                    </td>
                    <td>
                        <?php $scoreBand = newsroom_editorial_score_band((int) $item['effective_score']); ?>
                        <div class="editorial-score-card editorial-score-card--<?= htmlspecialchars((string) $scoreBand['class']) ?>">
                            <div class="editorial-score-card__bar"><span style="width: <?= max(0, min(100, (int) $item['effective_score'])) ?>%;"></span></div>
                            <div class="editorial-score-card__value"><?= htmlspecialchars((string) $item['editorial_score']) ?></div>
                            <div class="editorial-score-card__band"><?= htmlspecialchars((string) $scoreBand['label']) ?></div>
                        </div>
                        <div class="editorial-item__meta">Default score</div>
                        <label class="editorial-inline-control">
                            <span>Override</span>
                            <input type="number" form="<?= htmlspecialchars($formId) ?>" name="score_override" min="0" max="100" value="<?= htmlspecialchars($item['score_override'] === null ? '' : (string) $item['score_override']) ?>">
                        </label>
                        <div class="editorial-item__meta editorial-item__meta--score">
                            Effective <?= htmlspecialchars((string) $item['effective_score']) ?>
                            <?php if ($item['score_override'] !== null && $item['score_override'] !== ''): ?>
                                <span class="editorial-score-delta"><?= htmlspecialchars(sprintf('%+d', (int) $item['effective_score'] - (int) $item['editorial_score'])) ?></span>
                            <?php endif; ?>
                        </div>
                    </td>
                    <td>
                        <?php $signals = newsroom_sorted_signals($item['editorial_signals_json'] ?? null); ?>
                        <?php if ($signals): ?>
                            <ul class="editorial-signal-list">
                                <?php foreach ($signals as $signal): ?>
                                    <?php $signalWeight = (int) ($signal['weight'] ?? 0); ?>
                                    <li class="<?= $signalWeight >= 0 ? 'editorial-signal-list__item--positive' : 'editorial-signal-list__item--negative' ?>">
                                        <span class="editorial-signal-list__reason"><?= htmlspecialchars((string) ($signal['reason'] ?? 'Signal')) ?></span>
                                        <span class="editorial-signal-list__weight"><?= htmlspecialchars(sprintf('%+d', $signalWeight)) ?></span>
                                    </li>
                                <?php endforeach; ?>
                            </ul>
                        <?php else: ?>
                            <div class="editorial-item__meta">No scoring signals</div>
                        <?php endif; ?>
                    </td>
                    <td>
                        <?php $topics = newsroom_parse_topics($item['topic_tags_json'] ?? null); ?>
                        <?php if ($topics): ?>
                            <div class="topic-chip-row">
                                <?php foreach ($topics as $topic): ?>
                                    <a class="topic-chip" href="<?= htmlspecialchars(newsroom_topic_url((string) $topic['slug'])) ?>"><?= htmlspecialchars((string) $topic['label']) ?></a>
                                <?php endforeach; ?>
                            </div>
                        <?php else: ?>
                            <div class="editorial-item__meta">No topics</div>
                        <?php endif; ?>
                        <label class="editorial-inline-control">
                            <span>Workflow</span>
                            <select form="<?= htmlspecialchars($formId) ?>" name="workflow_status">
                                <?php $workflowStatus = (string) ($item['workflow_status'] ?? 'monitor'); ?>
                                <?php foreach ($workflowOptions as $workflowValue => $workflowLabel): ?>
                                    <option value="<?= htmlspecialchars((string) $workflowValue) ?>"<?= $workflowStatus === (string) $workflowValue ? ' selected' : '' ?>><?= htmlspecialchars((string) $workflowLabel) ?></option>
                                <?php endforeach; ?>
                            </select>
                        </label>
                    </td>
                    <td>
                        <div class="editorial-item__meta-label">Suggested Coverage</div>
                        <div class="editorial-item__meta-value"><?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['suggested_coverage_mode']))) ?></div>
                        <label class="editorial-inline-control">
                            <span>Override</span>
                            <select form="<?= htmlspecialchars($formId) ?>" name="coverage_override">
                                <option value=""<?= empty($item['coverage_override']) ? ' selected' : '' ?>>Use suggested</option>
                                <option value="calendar_only"<?= (string) $item['coverage_override'] === 'calendar_only' ? ' selected' : '' ?>>Calendar only</option>
                                <option value="brief"<?= (string) $item['coverage_override'] === 'brief' ? ' selected' : '' ?>>Brief</option>
                                <option value="full_story"<?= (string) $item['coverage_override'] === 'full_story' ? ' selected' : '' ?>>Full story</option>
                                <option value="must_cover"<?= (string) $item['coverage_override'] === 'must_cover' ? ' selected' : '' ?>>Must cover</option>
                            </select>
                        </label>
                        <div class="editorial-item__meta">Effective <?= htmlspecialchars(ucwords(str_replace('_', ' ', (string) $item['effective_coverage_mode']))) ?></div>
                    </td>
                    <td>
                        <div class="editorial-item__meta-label">Next Step</div>
                        <p class="editorial-next-action"><?= htmlspecialchars((string) ($item['next_action'] ?? '')) ?></p>
                        <label class="editorial-form__check">
                            <input type="checkbox" form="<?= htmlspecialchars($formId) ?>" name="watch_live" value="1"<?= !empty($item['watch_live']) ? ' checked' : '' ?>>
                            <span>Watch live</span>
                        </label>
                        <label class="editorial-form__check">
                            <input type="checkbox" form="<?= htmlspecialchars($formId) ?>" name="follow_up_needed" value="1"<?= !empty($item['follow_up_needed']) ? ' checked' : '' ?>>
                            <span>Follow up needed</span>
                        </label>
                        <?php if ($item['entity_type'] === 'community_event'): ?>
                            <label class="editorial-form__check">
                                <input type="checkbox" form="<?= htmlspecialchars($formId) ?>" name="is_hidden" value="1"<?= !empty($item['is_hidden']) ? ' checked' : '' ?>>
                                <span>Hide from public event surfacing</span>
                            </label>
                        <?php endif; ?>
                        <label class="editorial-inline-control">
                            <span>Notes</span>
                            <textarea form="<?= htmlspecialchars($formId) ?>" name="admin_notes" rows="4"><?= htmlspecialchars((string) ($item['admin_notes'] ?? '')) ?></textarea>
                        </label>
                        <form method="post" class="editorial-form" id="<?= htmlspecialchars($formId) ?>">
                            <input type="hidden" name="entity_type" value="<?= htmlspecialchars((string) $item['entity_type']) ?>">
                            <input type="hidden" name="entity_id" value="<?= htmlspecialchars((string) $item['entity_id']) ?>">
                        </form>
                        <button type="submit" form="<?= htmlspecialchars($formId) ?>">Save</button>
                    </td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </section>
</div>
</body>
</html>
