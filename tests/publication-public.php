<?php
/** Exercise real public query paths against the full application schema. */
declare(strict_types=1);
if (!str_ends_with((string) getenv('NEWSROOM_DB_NAME'), '_test')) { throw new RuntimeException('Disposable test database required.'); }
$setup = new PDO('mysql:host=' . getenv('NEWSROOM_DB_HOST') . ';port=' . getenv('NEWSROOM_DB_PORT') . ';charset=utf8mb4', getenv('NEWSROOM_DB_USER'), getenv('NEWSROOM_DB_PASSWORD'), [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$setup->exec('CREATE DATABASE newsroom_public_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');
$setup->exec('USE newsroom_public_test');
foreach (glob(__DIR__ . '/../db/migrations/*.sql') as $migration) { $setup->exec(file_get_contents($migration)); }
putenv('NEWSROOM_DB_NAME=newsroom_public_test');
require_once __DIR__ . '/../web/lib/content.php';
$db = newsroom_db();
$db->exec('INSERT INTO sources (name,slug,source_type,base_url,list_url,parser_key) VALUES ("Fixture source","fixture","official","https://example.org","https://example.org","fixture")');
$source = (int) $db->lastInsertId();
$db->exec('INSERT INTO source_items (source_id, canonical_url, item_type) VALUES (' . $source . ', "https://example.org/fixture", "agenda")');
$sourceItem = (int) $db->lastInsertId();
$db->exec('INSERT INTO governing_bodies (municipality_id,name,normalized_name,slug) VALUES ((SELECT id FROM municipalities LIMIT 1),"Fixture Board","Fixture Board","fixture-board")');
$board = (int) $db->lastInsertId();
$db->exec('INSERT INTO meetings (source_item_id, governing_body_id, governing_body, meeting_date, meeting_time, location_name) VALUES (' . $sourceItem . ',' . $board . ',"Fixture Board",DATE_ADD(CURDATE(),INTERVAL 1 DAY),"18:00:00","Town Hall")');
$meeting = (int) $db->lastInsertId();
$db->exec('INSERT INTO stories (meeting_id,governing_body_id,story_type,slug,headline,summary,body_html,body_text,publish_status,published_at,display_date,sort_date,editorial_score,topic_tags_json) VALUES (' . $meeting . ',' . $board . ',"meeting_preview","fixture-review","Fixture budget meeting","Source-backed budget details","<p>Budget details</p>","Budget details","published",NOW(),NOW(),NOW(),80,JSON_ARRAY(JSON_OBJECT("slug","budget","label","Budget")))');
$id = (int) $db->lastInsertId();
$db->exec('INSERT INTO calendar_events (meeting_id,title,starts_at,source_url,description) VALUES (' . $meeting . ',"Fixture meeting",DATE_ADD(NOW(),INTERVAL 1 DAY),"https://example.org/fixture","Fixture budget details")');
function require_true(bool $condition, string $message): void { if (!$condition) { throw new RuntimeException($message); } }
function public_hash(int $id): string { return (string) newsroom_db()->query('SELECT ' . newsroom_publication_revision_sql('s') . ' FROM stories s WHERE s.id=' . $id)->fetchColumn(); }
require_true(newsroom_story_by_slug('fixture-review') !== null, 'Legacy detail missing.');
require_true(count(newsroom_latest_stories()) === 1, 'Homepage failed to list the fixture.');
require_true(count(newsroom_upcoming_events()) === 1, 'Calendar fixture missing.');
newsroom_publication_decide($id, 'hold', public_hash($id), 'Sensitive fixture');
$db->exec('UPDATE stories SET publish_status="published" WHERE id=' . $id);
require_true(newsroom_story_by_slug('fixture-review') === null, 'Held detail leaked.');
require_true(newsroom_latest_stories() === [], 'Held homepage story leaked.');
require_true(newsroom_upcoming_events() === [], 'Calendar leaked held meeting copy.');
require_true(newsroom_topics_index() === [], 'Held topic count leaked.');
require_true(newsroom_homepage_priority_stories() === [], 'Held priority story leaked.');
require_true(newsroom_archive_results() === [], 'Held archive story leaked.');
$bundle = newsroom_governing_body_bundle('fixture-board');
require_true(($bundle['stories'] ?? []) === [], 'Held body coverage leaked.');
newsroom_archive_filter_options(); // Execute all nested public filter/count SQL.
newsroom_publication_decide($id, 'approve', public_hash($id), 'Exact approval');
require_true(newsroom_story_by_slug('fixture-review') !== null, 'Approved detail did not return.');
$db->exec('UPDATE stories SET byline_name="Unreviewed author" WHERE id=' . $id);
require_true(newsroom_story_by_slug('fixture-review') === null, 'Unapproved byline changed the public revision.');
echo "Full-schema public route checks passed: detail, homepage, calendar, topics, priorities, archive, bodies and revised authorship.\n";
