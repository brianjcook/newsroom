<?php

declare(strict_types=1);

$root = file_exists(__DIR__ . '/../bootstrap.php') ? __DIR__ . '/..' : __DIR__;
require_once $root . '/bootstrap.php';
require_once $root . '/lib/publication.php';
newsroom_publication_require_publisher();
newsroom_publication_audit_schema();

if (empty($_SESSION['publication_csrf'])) {
    $_SESSION['publication_csrf'] = bin2hex(random_bytes(32));
}
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['auth_action'] ?? '') !== 'login') {
    if (!hash_equals($_SESSION['publication_csrf'], (string) ($_POST['csrf'] ?? ''))) {
        http_response_code(403);
        exit('This decision could not be verified. Reload the review page and try again.');
    }
    try {
        $decision = (string) ($_POST['decision'] ?? '');
        if (trim((string) ($_POST['reason'] ?? '')) === '') {
            $_POST['reason'] = ['hold' => 'Publisher kept this story on hold.', 'withdraw' => 'Publisher chose not to publish this story.'][$decision] ?? '';
        }
        newsroom_publication_decide((int) ($_POST['story_id'] ?? 0), $decision,
            (string) ($_POST['revision_hash'] ?? ''), (string) ($_POST['reason'] ?? ''), isset($_POST['review_version']) && ctype_digit((string) $_POST['review_version']) ? (int) $_POST['review_version'] : -1);
        header('Location: /editorial-reviews.php?saved=1');
        exit;
    } catch (RuntimeException $exception) {
        http_response_code(409);
        $error = $exception->getMessage();
    }
}
$db = newsroom_db();
$storyId = max(0, (int) ($_GET['id'] ?? $_POST['story_id'] ?? 0));
$story = null;
$history = $citations = $items = [];
if ($storyId > 0) {
    $statement = $db->prepare('SELECT s.*, ' . newsroom_publication_revision_sql('s') . ' AS current_hash,
        pr.state AS review_state, pr.reason AS review_reason, pr.approved_hash, pr.decision_version
        FROM stories s LEFT JOIN publication_reviews pr ON pr.story_id = s.id WHERE s.id = :id');
    $statement->execute([':id' => $storyId]);
    $story = $statement->fetch() ?: null;
    if (!$story) { http_response_code(404); }
    $statement = $db->prepare('SELECT citation_number, label, source_url FROM story_citations WHERE story_id = :id ORDER BY citation_number');
    $statement->execute([':id' => $storyId]);
    $citations = $statement->fetchAll();
    $statement = $db->prepare('SELECT * FROM publication_review_events WHERE story_id = :id ORDER BY id DESC LIMIT 30');
    $statement->execute([':id' => $storyId]);
    $history = $statement->fetchAll();
} else {
    $before = max(0, (int) ($_GET['before'] ?? 0));
    $view = (string) ($_GET['view'] ?? 'pending');
    $condition = $view === 'declined' ? 'pr.state = "withdrawn"'
        : ($view === 'drafts' ? '(pr.story_id IS NULL AND s.publish_status <> "published")'
        : '(pr.state NOT IN ("approved", "withdrawn") OR (pr.state = "approved" AND NOT (' . newsroom_publication_visibility_sql('s') . ')))');
    $statement = $db->prepare('SELECT s.id, s.headline, s.publish_status, pr.state, pr.reason,
        pr.approved_hash, ' . newsroom_publication_revision_sql('s') . ' AS current_hash
        FROM stories s LEFT JOIN publication_reviews pr ON pr.story_id = s.id
        WHERE ' . $condition . '
        AND (:before_all = 0 OR s.id < :before_id) ORDER BY s.id DESC LIMIT 51');
    $statement->execute([':before_all' => $before, ':before_id' => $before]);
    $items = $statement->fetchAll();
}
function review_escape($text): string { return htmlspecialchars((string) $text, ENT_QUOTES, 'UTF-8'); }
?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Publisher review | The Wareham Times</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <style>
        .review-copy{white-space:normal;font:inherit;line-height:1.65;overflow-wrap:anywhere}
        .review-actions{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}
        .review-reason{display:block;width:100%;min-height:80px;box-sizing:border-box;margin:6px 0 16px}
        .review-notice{padding:16px 0;border-block:1px solid currentColor;margin:20px 0}
        .review-row{padding:20px 0;border-bottom:1px solid #c8bca9}
        .review-row p{margin:8px 0}.review-muted{opacity:.7;font-size:.9em}.review-details{margin:24px 0}.review-primary{background:#29251f;color:#fff;padding:10px 20px;border:1px solid #29251f}.review-actions button{cursor:pointer}.review-row a:hover{color:#8b482e}.review-actions{align-items:center}
        .review-source{overflow-wrap:anywhere}
    </style>
</head>
<body><main class="page">
    <header class="masthead"><div class="masthead__core"><h1 class="masthead__title">Publisher review</h1>
        <p>The Wareham Times</p></div></header>
    <nav class="nav"><a href="/desk">News desk</a><a href="/editorial-reviews.php">Review queue</a><a href="/">Public site</a></nav>
    <?php if ($error): ?><p class="review-notice" role="alert"><?= review_escape($error) ?></p><?php endif; ?>
    <?php if (isset($_GET['saved'])): ?><p class="review-notice" role="status">Your publication decision has been saved.</p><?php endif; ?>
    <?php if ($story): ?>
        <h2><?= review_escape($story['headline']) ?></h2>
        <?php if ($story['review_reason']): ?><p class="review-notice"><strong>Why this needs you</strong><br><?= review_escape($story['review_reason']) ?></p><?php endif; ?>
        <?php if ($story['review_state'] === 'approved' && $story['approved_hash'] !== $story['current_hash']): ?>
            <p class="review-notice">This version differs from the approved version and is hidden from readers.</p>
        <?php endif; ?>
        <p class="review-muted"><?= review_escape($story['byline_name'] ?: 'Wareham Times News Desk') ?><?php if ($story['public_label']): ?> · <?= review_escape($story['public_label']) ?><?php endif; ?></p>
        <?php if ($story['dek']): ?><p><?= review_escape($story['dek']) ?></p><?php endif; ?>
        <div class="review-copy"><?= newsroom_publication_preview_html((string) $story['body_html']) ?></div>
        <details class="review-details"><summary>Sources and additional details</summary>
        <?php if ($story['summary']): ?><p><strong>Summary:</strong> <?= review_escape($story['summary']) ?></p><?php endif; ?>
        <h3>Sources</h3>
        <?php if (!$citations): ?><p>No citation records are attached. Verify the evidence before approving.</p><?php endif; ?>
        <?php foreach ($citations as $citation): ?>
            <p class="review-source"><?php if (preg_match('~^https?://~i', (string) $citation['source_url'])): ?><a href="<?= review_escape($citation['source_url']) ?>" rel="noopener noreferrer" target="_blank"><?= review_escape($citation['label'] ?: $citation['source_url']) ?></a><?php else: ?><?= review_escape($citation['source_url']) ?><?php endif; ?></p>
        <?php endforeach; ?>
        </details>
        <p class="review-muted">Publish this version, leave it on hold, or decline it. A changed story comes back for review.</p>
        <form method="post">
            <input type="hidden" name="csrf" value="<?= review_escape($_SESSION['publication_csrf']) ?>">
            <input type="hidden" name="review_version" value="<?= (int) ($story['decision_version'] ?? 0) ?>">
            <input type="hidden" name="story_id" value="<?= (int) $story['id'] ?>">
            <input type="hidden" name="revision_hash" value="<?= review_escape($story['current_hash'] ?? str_repeat('0', 64)) ?>">
            <details class="review-details"><summary>Add a note (optional)</summary>
                <label for="review-reason">Your note</label><textarea id="review-reason" name="reason" class="review-reason"></textarea>
            </details>
            <div class="review-actions"><button class="review-primary" name="decision" value="approve">Publish</button><button name="decision" value="hold">Keep on hold</button><button name="decision" value="withdraw">Do not publish</button></div>
        </form>
        <details class="review-details"><summary>Previous decisions</summary>
        <?php if (!$history): ?><p>No publisher decisions recorded.</p><?php endif; ?>
        <?php foreach ($history as $event): ?><div class="review-row"><strong><?= review_escape(ucfirst($event['action'])) ?></strong> · <?= review_escape($event['created_at']) ?> UTC · <?= review_escape($event['actor']) ?><p><?= review_escape($event['reason']) ?></p></div><?php endforeach; ?>
        </details>
    <?php elseif ($storyId): ?><h2>Story not found</h2>
    <?php else: ?>
        <h2><?= ($view ?? 'pending') === 'declined' ? 'Not publishing' : (($view ?? 'pending') === 'drafts' ? 'Other drafts' : 'Needs your decision') ?></h2>
        <p><a href="/editorial-reviews.php">Needs review</a> · <a href="?view=drafts">Other drafts</a> · <a href="?view=declined">Not publishing</a></p>
        <?php if (!$items): ?><p>Nothing needs your attention here.</p><?php endif; ?>
        <?php foreach (array_slice($items, 0, 50) as $item): ?><article class="review-row"><h3><a href="/editorial-reviews.php?id=<?= (int) $item['id'] ?>"><?= review_escape($item['headline']) ?></a></h3><p><?= review_escape($item['reason'] ?: 'Read this draft and decide whether to publish it.') ?></p></article><?php endforeach; ?>
        <?php if (count($items) > 50): ?><p><a href="/editorial-reviews.php?view=<?= review_escape($view) ?>&amp;before=<?= (int) $items[49]['id'] ?>">Older stories</a></p><?php endif; ?>
    <?php endif; ?>
</main></body></html>
