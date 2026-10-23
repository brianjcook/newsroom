<?php
/** Both homepage entry points must defer maintenance and share one callback. */
declare(strict_types=1);

$refreshes = 0;
function newsroom_db_available(): bool { return true; }
function newsroom_db_read(string $sql, array $parameters): array { return []; }
function newsroom_publication_visibility_sql(string $alias): string { return '1 = 1'; }
function newsroom_publication_meeting_visibility_sql(string $alias): string { return '1 = 1'; }
function newsroom_story_is_homepage_eligible(array $row): bool { return true; }
function newsroom_recent_story_presenter(array $row): array { return $row; }
function newsroom_event_presenter(array $row): array { return $row; }
function newsroom_maybe_trigger_worker_refresh(): void { $GLOBALS['refreshes']++; }

$source = file_get_contents(__DIR__ . '/../web/lib/content.php');
foreach (['newsroom_schedule_worker_refresh', 'newsroom_latest_stories', 'newsroom_upcoming_events'] as $name) {
    $start = strpos($source, 'function ' . $name . '(');
    if ($start === false) { throw new RuntimeException('Missing production function: ' . $name); }
    $end = strpos($source, "\nfunction ", $start + 1);
    eval(substr($source, $start, $end - $start));
}
// Run events first too: the calendar can be visited without the story listing.
newsroom_upcoming_events();
newsroom_latest_stories();
newsroom_upcoming_events();
if ($refreshes !== 0) { throw new RuntimeException('Maintenance ran during public reads.'); }
register_shutdown_function(static function (): void {
    if ($GLOBALS['refreshes'] !== 1) { throw new RuntimeException('Maintenance was not scheduled exactly once.'); }
    echo "Story and event reads defer maintenance to one shutdown callback.\n";
});
