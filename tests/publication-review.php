<?php
/** Real-MySQL regression tests. Run only against a disposable *_test database. */
declare(strict_types=1);
require_once __DIR__ . '/../web/lib/publication.php';

$pdo = newsroom_db();
$database = (string) $pdo->query('SELECT DATABASE()')->fetchColumn();
if (!str_ends_with($database, '_test')) {
    throw new RuntimeException('Refusing publication integration tests outside a disposable *_test database.');
}
$pdo->exec('CREATE TABLE IF NOT EXISTS stories (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    headline TEXT NULL, dek TEXT NULL, summary TEXT NULL,
    public_label VARCHAR(64) NULL, byline_name VARCHAR(128) NULL, byline_title VARCHAR(128) NULL,
    story_type VARCHAR(32) NULL, slug VARCHAR(191) NULL, topic_tags_json JSON NULL,
    display_date DATETIME NULL, sort_date DATETIME NULL,
    body_html MEDIUMTEXT NULL, body_text MEDIUMTEXT NULL,
    source_basis_json JSON NULL,
    publish_status VARCHAR(32) NOT NULL DEFAULT "draft",
    published_at DATETIME NULL,
    meeting_id BIGINT UNSIGNED NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');
$pdo->exec('CREATE TABLE IF NOT EXISTS story_citations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    story_id BIGINT UNSIGNED NOT NULL, citation_number INT NOT NULL,
    label VARCHAR(255) NULL, source_url VARCHAR(512) NOT NULL, quote_text TEXT NULL, note_text TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');
newsroom_publication_schema();
function check(bool $condition, string $message): void
{
    if (!$condition) { throw new RuntimeException($message); }
}
function revision(int $id): string
{
    $statement = newsroom_db()->prepare('SELECT ' . newsroom_publication_revision_sql('s') . ' FROM stories s WHERE s.id = :id');
    $statement->execute([':id' => $id]);
    return (string) $statement->fetchColumn();
}
function visible(int $id): bool
{
    $statement = newsroom_db()->prepare('SELECT COUNT(*) FROM stories s WHERE s.id = :id AND s.publish_status = "published" AND (' . newsroom_publication_visibility_sql('s') . ')');
    $statement->execute([':id' => $id]);
    return (int) $statement->fetchColumn() === 1;
}
function status(int $id): string
{
    $statement = newsroom_db()->prepare('SELECT publish_status FROM stories WHERE id = :id');
    $statement->execute([':id' => $id]);
    return (string) $statement->fetchColumn();
}
function denied(callable $action, string $message): void
{
    try { $action(); } catch (RuntimeException $exception) { return; }
    throw new RuntimeException($message);
}

$id = 900001;
$pdo->exec('DELETE FROM publication_reviews WHERE story_id = 900001');
$pdo->exec('DELETE FROM stories WHERE id = 900001');
$pdo->exec('INSERT INTO stories (id, headline, dek, summary, body_html, body_text, source_basis_json, publish_status) VALUES
    (900001, "Budget meeting", "A routine budget meeting", "Source-backed summary", "<p>Meeting details.</p>", "Meeting details.", JSON_OBJECT("source", "official agenda"), "published")');
check(visible($id), 'Legacy published story without review must retain visibility.');
$hash = revision($id);
check(strlen($hash) === 64, 'Revision fingerprint must be SHA-256.');
newsroom_publication_decide($id, 'hold', $hash, 'Potential legal sensitivity requires publisher review.');
check(!visible($id), 'Held story remained publicly visible.');
check(status($id) === 'draft', 'Holding story must remove published status.');
$pdo->exec('UPDATE stories SET publish_status = "published" WHERE id = 900001');
check(!visible($id), 'Worker status rewrite bypassed publication hold.');
newsroom_publication_decide($id, 'approve', revision($id), 'Publisher reviewed the source and approved this exact text.');
check(visible($id), 'Approval of exact revision must restore publication.');
check(status($id) === 'published', 'Approved story must be published.');

$approvedHash = revision($id);
$pdo->exec('UPDATE stories SET body_html = "<p>Materially different content.</p>" WHERE id = 900001');
check(revision($id) !== $approvedHash, 'Body edit did not change revision fingerprint.');
check(!visible($id), 'Changed content inherited approval of an older revision.');
$reviewBefore = $pdo->query('SELECT * FROM publication_reviews WHERE story_id = 900001')->fetch();
$statusBefore = status($id);
denied(static fn() => newsroom_publication_decide($id, 'approve', $approvedHash, 'Stale browser submission'), 'Stale approval was accepted.');
check(!$pdo->inTransaction(), 'Failed stale decision left an open transaction.');
check(status($id) === $statusBefore, 'Failed stale decision changed publication status.');
check($pdo->query('SELECT * FROM publication_reviews WHERE story_id = 900001')->fetch() === $reviewBefore, 'Failed stale decision changed review record.');

foreach (['headline', 'dek', 'summary', 'body_html', 'body_text', 'source_basis_json'] as $field) {
    $before = revision($id);
    $value = $field === 'source_basis_json' ? '{"source":"amended official agenda"}' : 'Changed ' . $field;
    $statement = $pdo->prepare('UPDATE stories SET ' . $field . ' = :value WHERE id = :id');
    $statement->execute([':value' => $value, ':id' => $id]);
    check(revision($id) !== $before, 'Changed ' . $field . ' did not change review fingerprint.');
}
newsroom_publication_decide($id, 'approve', revision($id), 'Publisher approved updated revision.');
check(visible($id), 'Reapproval of revised content failed.');
newsroom_publication_decide($id, 'withdraw', revision($id), 'Publisher withdrew this story.');
check(status($id) === 'suppressed', 'Withdrawal must suppress story.');
$pdo->exec('UPDATE stories SET publish_status = "published", summary = "Worker regenerated summary" WHERE id = 900001');
check(!visible($id), 'Worker rewrite revived a withdrawn story.');

denied(static fn() => newsroom_publication_decide($id, 'hold', revision($id), ''), 'Blank hold reason was accepted.');
denied(static fn() => newsroom_publication_decide($id, 'withdraw', revision($id), ''), 'Blank withdrawal reason was accepted.');
denied(static fn() => newsroom_publication_decide($id, 'invalid', revision($id), 'Invalid action'), 'Invalid decision action was accepted.');
check(!$pdo->inTransaction(), 'Rejected decision left an open transaction.');

echo "Publication review integration checks passed: legacy visibility, durable hold/withdrawal, exact-revision approval, edited-copy exclusion, stale rollback, and validation.\n";
