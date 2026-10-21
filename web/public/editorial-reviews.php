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
        newsroom_publication_decide((int) ($_POST['story_id'] ?? 0), (string) ($_POST['decision'] ?? ''),
            (string) ($_POST['revision_hash'] ?? ''), (string) ($_POST['reason'] ?? ''), isset($_POST['review_version']) && ctype_digit((string) $_POST['review_version']) ? (int) $_POST['review_version'] : -1);
        header('Location: /editorial-reviews.php?id=' . (int) $_POST['story_id'] . '&saved=1');
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
    $statement = $db->prepare('SELECT s.id, s.headline, s.publish_status, pr.state, pr.reason,
        pr.approved_hash, ' . newsroom_publication_revision_sql('s') . ' AS current_hash
        FROM stories s LEFT JOIN publication_reviews pr ON pr.story_id = s.id
        WHERE (s.publish_status <> "published" OR NOT (' . newsroom_publication_visibility_sql('s') . '))
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
        .review-copy{white-space:pre-wrap;font:inherit;line-height:1.65;overflow-wrap:anywhere}
        .review-actions{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}
        .review-reason{display:block;width:100%;min-height:80px;box-sizing:border-box;margin:6px 0 16px}
        .review-notice{padding:16px 0;border-block:1px solid currentColor;margin:20px 0}
        .review-row{padding:20px 0;border-bottom:1px solid #c8bca9}
        .review-row p{margin:8px 0}.review-hash{font-family:monospace;font-size:.85rem;overflow-wrap:anywhere}
        .review-source{overflow-wrap:anywhere}
    </style>
</head>
<body><main class="page">
    <header class="masthead"><div class="masthead__core"><h1 class="masthead__title">Publisher review</h1>
        <p>Publication decisions for The Wareham Times</p></div></header>
    <nav class="nav"><a href="/desk">News desk</a><a href="/editorial-reviews.php">Review queue</a><a href="/">Public site</a></nav>
    <?php if ($error): ?><p class="review-notice" role="alert"><?= review_escape($error) ?></p><?php endif; ?>
    <?php if (isset($_GET['saved'])): ?><p class="review-notice" role="status">Your publication decision has been saved.</p><?php endif; ?>
    <?php if ($story): ?>
        <h2><?= review_escape($story['headline']) ?></h2>
        <p><strong>Publication:</strong> <?= review_escape($story['publish_status']) ?> · <strong>Review:</strong> <?= review_escape($story['review_state'] ?: 'Not yet reviewed') ?></p>
        <?php if ($story['review_reason']): ?><p class="review-notice"><strong>Reason:</strong> <?= review_escape($story['review_reason']) ?></p><?php endif; ?>
        <?php if ($story['review_state'] === 'approved' && $story['approved_hash'] !== $story['current_hash']): ?>
            <p class="review-notice">This version differs from the approved version and is hidden from readers.</p>
        <?php endif; ?>
        <p><strong>Type:</strong> <?= review_escape($story['story_type']) ?> · <strong>Label:</strong> <?= review_escape($story['public_label']) ?></p>
        <p><strong>Byline:</strong> <?= review_escape($story['byline_name']) ?> <?= review_escape($story['byline_title']) ?></p>
        <p><strong>Deck:</strong> <?= review_escape($story['dek']) ?></p>
        <p><strong>Summary:</strong> <?= review_escape($story['summary']) ?></p>
        <h3>Published story preview</h3>
        <div class="review-copy"><?= newsroom_publication_preview_html((string) $story['body_html']) ?></div>
        <details><summary>Stored text and HTML</summary>
        <pre class="review-copy"><?= review_escape($story['body_html']) ?></pre>
        <pre class="review-copy"><?= review_escape($story['body_text'] ?: strip_tags((string) $story['body_html'])) ?></pre></details>
        <h3>Sources</h3>
        <?php if (!$citations): ?><p>No citation records are attached. Verify the evidence before approving.</p><?php endif; ?>
        <?php foreach ($citations as $citation): ?>
            <p class="review-source"><?php if (preg_match('~^https?://~i', (string) $citation['source_url'])): ?><a href="<?= review_escape($citation['source_url']) ?>" rel="noopener noreferrer" target="_blank"><?= review_escape($citation['label'] ?: $citation['source_url']) ?></a><?php else: ?><?= review_escape($citation['source_url']) ?><?php endif; ?></p>
        <?php endforeach; ?>
        <h3>Decision</h3>
        <p>Approval publishes the exact version shown here. Material changes require a fresh decision. Holds and withdrawals remain in force during automatic refreshes.</p>
        <form method="post">
            <input type="hidden" name="csrf" value="<?= review_escape($_SESSION['publication_csrf']) ?>">
            <input type="hidden" name="review_version" value="<?= (int) ($story['decision_version'] ?? 0) ?>">
            <input type="hidden" name="story_id" value="<?= (int) $story['id'] ?>">
            <input type="hidden" name="revision_hash" value="<?= review_escape($story['current_hash'] ?? str_repeat('0', 64)) ?>">
            <label for="review-reason">Decision note (required for hold or withdrawal)</label>
            <textarea id="review-reason" name="reason" class="review-reason"></textarea>
            <div class="review-actions"><button name="decision" value="hold">Keep on hold</button><button name="decision" value="withdraw">Withdraw story</button><button name="decision" value="approve">Approve and publish this version</button></div>
        </form>
        <h3>Decision history</h3>
        <?php if (!$history): ?><p>No publisher decisions recorded.</p><?php endif; ?>
        <?php foreach ($history as $event): ?><div class="review-row"><strong><?= review_escape(ucfirst($event['action'])) ?></strong> · <?= review_escape($event['created_at']) ?> UTC · <?= review_escape($event['actor']) ?><p><?= review_escape($event['reason']) ?></p><p class="review-hash">Version <?= review_escape($event['revision_hash']) ?></p></div><?php endforeach; ?>
    <?php elseif ($storyId): ?><h2>Story not found</h2>
    <?php else: ?>
        <form method="get"><label for="story-number">Open story number</label> <input id="story-number" type="number" name="id" min="1" required> <button>Review story</button></form>
        <h2>Stories awaiting a decision</h2><p>Held, withdrawn and unpublished stories appear here. Published stories can also be reviewed by opening their story number.</p>
        <?php if (!$items): ?><p>No stories are awaiting a decision.</p><?php endif; ?>
        <?php foreach (array_slice($items, 0, 50) as $item): ?><article class="review-row"><h3><a href="/editorial-reviews.php?id=<?= (int) $item['id'] ?>"><?= review_escape($item['headline']) ?></a></h3><p><?= review_escape($item['state'] ?: $item['publish_status']) ?></p><p><?= review_escape($item['reason'] ?: 'Unpublished story requires publisher review.') ?></p></article><?php endforeach; ?>
        <?php if (count($items) > 50): ?><p><a href="/editorial-reviews.php?before=<?= (int) $items[49]['id'] ?>">Older stories</a></p><?php endif; ?>
    <?php endif; ?>
</main></body></html>
