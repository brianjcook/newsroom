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

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    newsroom_update_editorial_override($_POST);
    header('Location: /editorial.php?saved=1');
    exit;
}

$config = newsroom_config();
$items = newsroom_editorial_items();
$saved = isset($_GET['saved']) && $_GET['saved'] === '1';
$entityFilter = trim((string) ($_GET['entity'] ?? 'all'));
$coverageFilter = trim((string) ($_GET['coverage'] ?? 'all'));
$visibilityFilter = trim((string) ($_GET['visibility'] ?? 'all'));

$items = array_values(array_filter($items, static function (array $item) use ($entityFilter, $coverageFilter, $visibilityFilter): bool {
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
    return true;
}));
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Editorial Desk | <?= htmlspecialchars($config['site_name']) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Editorial Desk</div>
            <div class="masthead__meta"><?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Transparent ranking, coverage suggestions, and manual editorial overrides.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar.php">Calendar</a>
        <a href="/editorial.php">Desk</a>
        <a href="/status.php">Status</a>
    </nav>

    <h2 class="section-heading">Newsworthiness Queue</h2>
    <p class="section-intro">Scores are deterministic and inspectable. The desk can override the score, coverage mode, and visibility without losing the underlying factor breakdown.</p>
    <?php if ($saved): ?>
        <p class="editorial-save-note">Editorial overrides saved.</p>
    <?php endif; ?>

    <section class="editorial-explainer">
        <p>The current score emphasizes civic impact, public interest, timeliness, and body priority. It subtracts points for routine recurring meetings and low-signal appointment-only agendas.</p>
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
        <button type="submit">Apply</button>
    </form>

    <section class="editorial-table-wrap">
        <table class="editorial-table">
            <thead>
            <tr>
                <th>Item</th>
                <th>When</th>
                <th>Type</th>
                <th>Score</th>
                <th>Signals</th>
                <th>Suggested</th>
                <th>Override</th>
            </tr>
            </thead>
            <tbody>
            <?php foreach ($items as $item): ?>
                <tr>
                    <td>
                        <div class="editorial-item__title"><?= htmlspecialchars((string) $item['title']) ?></div>
                        <?php if (!empty($item['body_name'])): ?>
                            <div class="editorial-item__meta"><?= htmlspecialchars((string) $item['body_name']) ?></div>
                        <?php endif; ?>
                        <?php if (!empty($item['public_url'])): ?>
                            <div class="editorial-item__meta"><a href="<?= htmlspecialchars((string) $item['public_url']) ?>"<?= $item['entity_type'] === 'community_event' ? ' target="_blank" rel="noopener noreferrer"' : '' ?>>Open</a></div>
                        <?php endif; ?>
                    </td>
                    <td class="editorial-table__when"><?= htmlspecialchars((string) $item['occurs_at']) ?></td>
                    <td>
                        <div class="editorial-item__meta"><?= htmlspecialchars((string) $item['entity_type']) ?></div>
                        <div><?= htmlspecialchars((string) $item['item_type']) ?></div>
                        <?php if (!empty($item['status_label'])): ?>
                            <div class="editorial-item__meta"><?= htmlspecialchars((string) $item['status_label']) ?></div>
                        <?php endif; ?>
                    </td>
                    <td>
                        <div class="editorial-score"><?= htmlspecialchars((string) $item['effective_score']) ?></div>
                        <?php if ($item['score_override'] !== null && $item['score_override'] !== ''): ?>
                            <div class="editorial-item__meta">base <?= htmlspecialchars((string) $item['editorial_score']) ?></div>
                        <?php endif; ?>
                    </td>
                    <td>
                        <div class="editorial-signals"><?= htmlspecialchars((string) $item['signal_summary']) ?></div>
                    </td>
                    <td>
                        <div><?= htmlspecialchars((string) $item['effective_coverage_mode']) ?></div>
                        <?php if (!empty($item['coverage_override'])): ?>
                            <div class="editorial-item__meta">base <?= htmlspecialchars((string) $item['suggested_coverage_mode']) ?></div>
                        <?php endif; ?>
                    </td>
                    <td>
                        <form method="post" class="editorial-form">
                            <input type="hidden" name="entity_type" value="<?= htmlspecialchars((string) $item['entity_type']) ?>">
                            <input type="hidden" name="entity_id" value="<?= htmlspecialchars((string) $item['entity_id']) ?>">
                            <label>
                                <span>Score</span>
                                <input type="number" name="score_override" min="0" max="100" value="<?= htmlspecialchars($item['score_override'] === null ? '' : (string) $item['score_override']) ?>">
                            </label>
                            <label>
                                <span>Coverage</span>
                                <select name="coverage_override">
                                    <option value=""<?= empty($item['coverage_override']) ? ' selected' : '' ?>>Use suggested</option>
                                    <option value="calendar_only"<?= (string) $item['coverage_override'] === 'calendar_only' ? ' selected' : '' ?>>Calendar only</option>
                                    <option value="brief"<?= (string) $item['coverage_override'] === 'brief' ? ' selected' : '' ?>>Brief</option>
                                    <option value="full_story"<?= (string) $item['coverage_override'] === 'full_story' ? ' selected' : '' ?>>Full story</option>
                                    <option value="must_cover"<?= (string) $item['coverage_override'] === 'must_cover' ? ' selected' : '' ?>>Must cover</option>
                                </select>
                            </label>
                            <?php if ($item['entity_type'] === 'community_event'): ?>
                                <label class="editorial-form__check">
                                    <input type="checkbox" name="is_hidden" value="1"<?= !empty($item['is_hidden']) ? ' checked' : '' ?>>
                                    <span>Hide</span>
                                </label>
                            <?php endif; ?>
                            <label>
                                <span>Notes</span>
                                <textarea name="admin_notes" rows="3"><?= htmlspecialchars((string) ($item['admin_notes'] ?? '')) ?></textarea>
                            </label>
                            <button type="submit">Save</button>
                        </form>
                    </td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </section>
</div>
</body>
</html>
