<?php

declare(strict_types=1);

require_once __DIR__ . '/db.php';

function newsroom_body_signal(?string $bodyName): array
{
    $name = trim((string) $bodyName);
    $palette = [
        ['bg' => '#eadfd1', 'fg' => '#53341d', 'border' => '#b17e45'],
        ['bg' => '#dbe7dc', 'fg' => '#214433', 'border' => '#5b8f73'],
        ['bg' => '#dfe3f1', 'fg' => '#283457', 'border' => '#6d7fba'],
        ['bg' => '#efe0df', 'fg' => '#5a2a28', 'border' => '#bd766d'],
        ['bg' => '#e7e0f0', 'fg' => '#47305c', 'border' => '#8c6bb0'],
        ['bg' => '#f0e8d7', 'fg' => '#5f4420', 'border' => '#c39748'],
        ['bg' => '#dae9ea', 'fg' => '#1f4850', 'border' => '#5c98a0'],
        ['bg' => '#ece2d4', 'fg' => '#5f3825', 'border' => '#c48b62'],
        ['bg' => '#e1e9d9', 'fg' => '#3c5327', 'border' => '#7e9d57'],
        ['bg' => '#e8dde8', 'fg' => '#5a355a', 'border' => '#9c6b9d'],
    ];

    if ($name === '') {
        return [
            'name' => 'Town Meeting',
            'slug' => 'town-meeting',
            'bg' => '#ece4d8',
            'fg' => '#47362b',
            'border' => '#a98767',
        ];
    }

    $index = abs(crc32(strtolower($name))) % count($palette);
    $slug = preg_replace('/[^a-z0-9]+/', '-', strtolower($name));
    $slug = trim((string) $slug, '-');

    return array_merge(
        [
            'name' => $name,
            'slug' => $slug !== '' ? $slug : 'body',
        ],
        $palette[$index]
    );
}

function newsroom_parse_json($value): array
{
    if (is_array($value)) {
        return $value;
    }

    if (!is_string($value) || $value === '') {
        return [];
    }

    $decoded = json_decode($value, true);
    return is_array($decoded) ? $decoded : [];
}

function newsroom_signal_summary($value): string
{
    $signals = newsroom_sorted_signals($value);
    if (!$signals) {
        return '';
    }

    $parts = [];
    foreach (array_slice($signals, 0, 4) as $signal) {
        if (!is_array($signal)) {
            continue;
        }
        $reason = trim((string) ($signal['reason'] ?? ''));
        $weight = (int) ($signal['weight'] ?? 0);
        if ($reason === '') {
            continue;
        }
        $parts[] = sprintf('%s (%+d)', $reason, $weight);
    }

    return implode('; ', $parts);
}

function newsroom_sorted_signals($value): array
{
    $signals = newsroom_parse_json($value);
    if (!$signals) {
        return [];
    }

    $filtered = [];
    foreach ($signals as $signal) {
        if (!is_array($signal)) {
            continue;
        }
        $reason = trim((string) ($signal['reason'] ?? ''));
        if ($reason === '') {
            continue;
        }
        $signal['reason'] = $reason;
        $signal['weight'] = (int) ($signal['weight'] ?? 0);
        $filtered[] = $signal;
    }

    usort($filtered, static function (array $a, array $b): int {
        $weightCompare = abs((int) $b['weight']) <=> abs((int) $a['weight']);
        if ($weightCompare !== 0) {
            return $weightCompare;
        }
        return strcmp((string) $a['reason'], (string) $b['reason']);
    });

    return $filtered;
}

function newsroom_parse_topics($value): array
{
    $topics = newsroom_parse_json($value);
    if (!$topics) {
        return [];
    }

    $parsed = [];
    foreach ($topics as $topic) {
        if (!is_array($topic)) {
            continue;
        }
        $slug = trim((string) ($topic['slug'] ?? ''));
        $label = trim((string) ($topic['label'] ?? ''));
        if ($slug === '' || $label === '') {
            continue;
        }
        $parsed[] = ['slug' => $slug, 'label' => $label];
    }
    return $parsed;
}

function newsroom_project_root(): ?string
{
    static $root = false;

    if ($root !== false) {
        return $root ?: null;
    }

    $candidates = [
        realpath(__DIR__ . '/../..'),
        realpath(__DIR__ . '/..'),
    ];

    foreach ($candidates as $candidate) {
        if (!is_string($candidate) || $candidate === '') {
            continue;
        }
        if (is_dir($candidate . DIRECTORY_SEPARATOR . 'worker') && is_dir($candidate . DIRECTORY_SEPARATOR . 'storage')) {
            $root = $candidate;
            return $candidate;
        }
    }

    $root = '';
    return null;
}

function newsroom_maybe_trigger_worker_refresh(): void
{
    static $attempted = false;

    if ($attempted) {
        return;
    }
    $attempted = true;

    if (PHP_OS_FAMILY === 'Windows') {
        return;
    }

    if (!newsroom_db_available()) {
        return;
    }

    $root = newsroom_project_root();
    if (!is_string($root) || $root === '') {
        return;
    }

    $logsDir = $root . DIRECTORY_SEPARATOR . 'storage' . DIRECTORY_SEPARATOR . 'logs';
    if (!is_dir($logsDir)) {
        return;
    }

    $statement = newsroom_db()->query(
        'SELECT run_status, started_at, finished_at
         FROM generation_runs
         ORDER BY id DESC
         LIMIT 1'
    );
    $latestRun = $statement ? $statement->fetch() : false;
    if (!$latestRun) {
        return;
    }

    $now = time();
    $runStatus = strtolower(trim((string) ($latestRun['run_status'] ?? '')));
    $startedAt = !empty($latestRun['started_at']) ? strtotime((string) $latestRun['started_at']) : false;
    $finishedAt = !empty($latestRun['finished_at']) ? strtotime((string) $latestRun['finished_at']) : false;

    if ($runStatus === 'running' && is_int($startedAt) && $startedAt > ($now - 7200)) {
        return;
    }

    if (is_int($finishedAt) && $finishedAt > ($now - 43200)) {
        return;
    }

    $kickFile = $logsDir . DIRECTORY_SEPARATOR . 'worker-kick.txt';
    if (is_file($kickFile)) {
        $lastKick = @filemtime($kickFile);
        if (is_int($lastKick) && $lastKick > ($now - 1800)) {
            return;
        }
    }

    @file_put_contents($kickFile, (string) $now, LOCK_EX);

    $envParts = [
        'PYTHONPATH=' . escapeshellarg($root . DIRECTORY_SEPARATOR . 'worker'),
        'PYTHONUSERBASE=' . escapeshellarg($root . DIRECTORY_SEPARATOR . '.pyuser'),
        'NEWSROOM_DB_HOST=' . escapeshellarg((string) newsroom_env('NEWSROOM_DB_HOST', 'localhost')),
        'NEWSROOM_DB_PORT=' . escapeshellarg((string) newsroom_env('NEWSROOM_DB_PORT', '3306')),
        'NEWSROOM_DB_NAME=' . escapeshellarg((string) newsroom_env('NEWSROOM_DB_NAME', 'bricoo10_newsroom')),
        'NEWSROOM_DB_USER=' . escapeshellarg((string) newsroom_env('NEWSROOM_DB_USER', '')),
        'NEWSROOM_DB_PASSWORD=' . escapeshellarg((string) newsroom_env('NEWSROOM_DB_PASSWORD', '')),
        'NEWSROOM_DB_UNIX_SOCKET=' . escapeshellarg((string) newsroom_env('NEWSROOM_DB_UNIX_SOCKET', '/run/mysqld/mysqld.sock')),
        'NEWSROOM_SOURCE_DISCOVERY_ENABLED=' . escapeshellarg((string) newsroom_env('NEWSROOM_SOURCE_DISCOVERY_ENABLED', '1')),
    ];

    $command = sprintf(
        'cd %s && nohup env %s python3 worker/scripts/run_daily.py >> %s 2>&1 &',
        escapeshellarg($root),
        implode(' ', $envParts),
        escapeshellarg($logsDir . DIRECTORY_SEPARATOR . 'run_daily.log')
    );

    if (function_exists('exec')) {
        @exec($command);
        return;
    }

    if (function_exists('shell_exec')) {
        @shell_exec($command);
    }
}

function newsroom_truncate_text(string $value, int $limit = 220): string
{
    $value = trim(preg_replace('/\s+/', ' ', $value));
    if ($value === '' || strlen($value) <= $limit) {
        return $value;
    }

    $truncated = substr($value, 0, $limit + 1);
    $lastSpace = strrpos($truncated, ' ');
    if ($lastSpace !== false) {
        $truncated = substr($truncated, 0, $lastSpace);
    }
    return rtrim($truncated, " ,.;:-") . '...';
}

function newsroom_sentence_list(array $items): string
{
    $items = array_values(array_filter(array_map(static function ($item): string {
        return trim((string) $item);
    }, $items)));

    $count = count($items);
    if ($count === 0) {
        return '';
    }
    if ($count === 1) {
        return $items[0];
    }
    if ($count === 2) {
        return $items[0] . ' and ' . $items[1];
    }

    $last = array_pop($items);
    return implode(', ', $items) . ', and ' . $last;
}

function newsroom_topic_url(string $slug): string
{
    return '/topics/' . rawurlencode(trim($slug));
}

function newsroom_workflow_options(): array
{
    return [
        'monitor' => 'Monitor',
        'preview_published' => 'Preview published',
        'watch_live' => 'Watch live',
        'recap_needed' => 'Recap needed',
        'minutes_reconcile' => 'Minutes reconcile',
        'follow_up_story' => 'Follow-up story',
        'draft' => 'Draft in progress',
        'assigned' => 'Assigned',
        'done' => 'Done',
    ];
}

function newsroom_normalize_workflow_status(?string $status, array $item = []): string
{
    $raw = trim((string) $status);
    if ($raw === 'watch') {
        return 'monitor';
    }
    if ($raw === 'follow_up') {
        return 'follow_up_story';
    }
    if ($raw === 'published') {
        if (($item['entity_type'] ?? '') === 'story' && ($item['item_type'] ?? '') === 'meeting_preview') {
            return 'preview_published';
        }
        return 'done';
    }
    if ($raw === '') {
        return ($item['entity_type'] ?? '') === 'community_event' ? 'monitor' : 'done';
    }
    return $raw;
}

function newsroom_workflow_label(string $status): string
{
    $options = newsroom_workflow_options();
    return $options[$status] ?? ucwords(str_replace('_', ' ', $status));
}

function newsroom_workflow_next_action(array $item): string
{
    $status = newsroom_normalize_workflow_status((string) ($item['workflow_status'] ?? ''), $item);
    switch ($status) {
        case 'monitor':
            return 'Keep this item on the desk and watch for a stronger reporting trigger.';
        case 'preview_published':
            return 'The preview is live. The next step is to watch the meeting and prepare a recap.';
        case 'watch_live':
            return 'This item is flagged for live monitoring or attendance.';
        case 'recap_needed':
            return 'Publish a quick post-meeting recap or decision brief.';
        case 'minutes_reconcile':
            return 'Compare the published coverage against posted minutes or the official record.';
        case 'follow_up_story':
            return 'A second-day or explanatory follow-up story is likely warranted.';
        case 'draft':
            return 'A draft is in progress and needs review or publication.';
        case 'assigned':
            return 'Reporting responsibility has been assigned.';
        case 'done':
        default:
            return 'No immediate desk action is queued.';
    }
}

function newsroom_editorial_queue_summary(array $items): array
{
    $summary = [
        'watch_live' => 0,
        'recap_needed' => 0,
        'minutes_reconcile' => 0,
        'follow_up_story' => 0,
        'must_cover' => 0,
    ];

    foreach ($items as $item) {
        $workflow = newsroom_normalize_workflow_status((string) ($item['workflow_status'] ?? ''), $item);
        if (!empty($item['watch_live'])) {
            $summary['watch_live']++;
        }
        if (isset($summary[$workflow])) {
            $summary[$workflow]++;
        }
        if ((string) ($item['effective_coverage_mode'] ?? '') === 'must_cover') {
            $summary['must_cover']++;
        }
    }

    return $summary;
}

function newsroom_editorial_queue_presets(): array
{
    return [
        'watch_live' => [
            'label' => 'Watch Live',
            'description' => 'Meetings and events flagged for live attendance or monitoring.',
            'filters' => [
                'watch_live' => 'watching',
                'sort' => 'date_asc',
            ],
        ],
        'recap_needed' => [
            'label' => 'Recap Needed',
            'description' => 'Items that have likely happened and need a fast post-meeting story or brief.',
            'filters' => [
                'workflow' => 'recap_needed',
                'sort' => 'date_desc',
            ],
        ],
        'minutes_reconcile' => [
            'label' => 'Minutes Reconcile',
            'description' => 'Published items that should be checked against posted minutes or the official record.',
            'filters' => [
                'workflow' => 'minutes_reconcile',
                'sort' => 'date_desc',
            ],
        ],
        'follow_up_story' => [
            'label' => 'Follow-Up Story',
            'description' => 'Items likely to need a second-day or explanatory story.',
            'filters' => [
                'workflow' => 'follow_up_story',
                'sort' => 'score_desc',
            ],
        ],
        'must_cover' => [
            'label' => 'Must Cover',
            'description' => 'Items currently marked for the strongest level of editorial attention.',
            'filters' => [
                'coverage' => 'must_cover',
                'sort' => 'date_asc',
            ],
        ],
    ];
}

function newsroom_editorial_methodology(): array
{
    return [
        'score_bands' => [
            ['label' => 'Must-cover range', 'range' => '75-100', 'meaning' => 'Usually strong enough for a full story or high editorial attention.'],
            ['label' => 'Brief range', 'range' => '45-74', 'meaning' => 'Often suitable for a short preview, brief, or prominent listing.'],
            ['label' => 'Calendar-only range', 'range' => '0-44', 'meaning' => 'Usually useful as a listing unless other signals push it higher.'],
        ],
        'story_rules' => [
            ['signal' => 'Public hearing', 'weight' => '+28', 'note' => 'Formal public-hearing items get a strong civic-impact boost.'],
            ['signal' => 'Town Meeting matter', 'weight' => '+22', 'note' => 'Town Meeting articles and warrant items score high.'],
            ['signal' => 'Wastewater / sewer', 'weight' => '+22 / +18', 'note' => 'Infrastructure planning and utility items are elevated.'],
            ['signal' => 'Budget / appropriation', 'weight' => '+20', 'note' => 'Money and spending items rank higher.'],
            ['signal' => 'School choice / policy review', 'weight' => '+20 / +18', 'note' => 'School-governance issues are boosted.'],
            ['signal' => 'Tobacco violation', 'weight' => '+18', 'note' => 'Public-health enforcement issues are elevated.'],
            ['signal' => 'High-interest governing body', 'weight' => '+3 to +5', 'note' => 'Select Board, Planning Board, School Committee, and similar bodies get a body-priority bump.'],
            ['signal' => 'Why-it-matters context', 'weight' => '+4', 'note' => 'Stories with stronger framing get a modest context bonus.'],
            ['signal' => 'Appointment-only penalty', 'weight' => '-8', 'note' => 'Pure appointment agendas are pushed down unless they also carry stronger civic issues.'],
        ],
        'community_rules' => [
            ['signal' => 'Annual / recurring tradition', 'weight' => '+24 to +26', 'note' => 'Recurring local traditions are intentionally elevated.'],
            ['signal' => 'Contest / festival / concert / performance', 'weight' => '+16 to +24', 'note' => 'High-interest community and cultural events score better.'],
            ['signal' => 'Public hearing / vote / budget / zoning', 'weight' => '+22 to +32', 'note' => 'Civic-impact signals still apply to public-calendar events.'],
            ['signal' => 'Timeliness bonus', 'weight' => '+3 to +10', 'note' => 'Events happening soon score higher.'],
            ['signal' => 'Public-interest bonus', 'weight' => '+5 to +6', 'note' => 'Family, cultural, or broad-attendance cues lift the score.'],
            ['signal' => 'Routine official meeting penalty', 'weight' => '-10 to -18', 'note' => 'Routine recurring meetings get pushed down unless the agenda is notable.'],
            ['signal' => 'Recurring board meeting penalty', 'weight' => '-8', 'note' => 'Low-signal committee meetings do not automatically outrank community events.'],
        ],
        'workflow' => [
            ['status' => 'Monitor', 'note' => 'Keep on the desk and watch for a stronger reporting trigger.'],
            ['status' => 'Preview published', 'note' => 'The advance story is live; the next likely step is live monitoring or recap coverage.'],
            ['status' => 'Watch live', 'note' => 'Flagged for live attendance, Zoom observation, or recording review.'],
            ['status' => 'Recap needed', 'note' => 'The meeting or event likely happened and now needs a post-event write-up.'],
            ['status' => 'Minutes reconcile', 'note' => 'Published coverage should be checked against minutes or the official record.'],
            ['status' => 'Follow-up story', 'note' => 'A second-day, explanatory, or accountability story may be warranted.'],
            ['status' => 'Done', 'note' => 'No immediate desk action is queued.'],
        ],
    ];
}

function newsroom_editorial_score_band(int $score): array
{
    if ($score >= 75) {
        return ['label' => 'Must Cover', 'class' => 'must-cover'];
    }
    if ($score >= 60) {
        return ['label' => 'High Brief', 'class' => 'high-brief'];
    }
    if ($score >= 45) {
        return ['label' => 'Brief', 'class' => 'brief'];
    }
    return ['label' => 'Calendar', 'class' => 'calendar'];
}

function newsroom_story_url_from_slug(string $slug): string
{
    return '/stories/' . rawurlencode($slug);
}

function newsroom_story_url(array $story): string
{
    return newsroom_story_url_from_slug((string) ($story['slug'] ?? ''));
}

function newsroom_community_event_url_from_parts(int $id, string $slug): string
{
    $slug = trim($slug);
    if ($slug === '') {
        return '/events/' . $id;
    }
    return '/events/' . $id . '/' . rawurlencode($slug);
}

function newsroom_community_event_url(array $event): string
{
    return newsroom_community_event_url_from_parts((int) ($event['id'] ?? 0), (string) ($event['slug'] ?? ''));
}

function newsroom_format_story_type(string $storyType): string
{
    return ucwords(str_replace('_', ' ', $storyType));
}

function newsroom_story_label(array $story): string
{
    $custom = trim((string) ($story['public_label'] ?? ''));
    if ($custom !== '') {
        return $custom;
    }

    switch ((string) ($story['story_type'] ?? '')) {
        case 'meeting_preview':
            return 'Preview';
        case 'minutes_recap':
            return 'Recap';
        default:
            return 'Local Report';
    }
}

function newsroom_story_byline(array $story): array
{
    $name = trim((string) ($story['byline_name'] ?? ''));
    $title = trim((string) ($story['byline_title'] ?? ''));

    return [
        'name' => $name !== '' ? $name : 'Wareham Times News Desk',
        'title' => $title !== '' ? $title : 'Automated civic reporting',
    ];
}

function newsroom_event_tier_data(array $event): array
{
    $stored = trim((string) ($event['event_tier'] ?? ''));
    $mode = trim((string) ($event['effective_coverage_mode'] ?? $event['suggested_coverage_mode'] ?? 'calendar_only'));
    $score = (int) ($event['effective_score'] ?? $event['editorial_score'] ?? 0);

    $tier = $stored;
    if ($tier === '') {
        if ($mode === 'full_story' && $score >= 80) {
            $tier = 'spotlight';
        } elseif ($mode === 'full_story') {
            $tier = 'feature_brief';
        } elseif ($mode === 'brief') {
            $tier = 'community_brief';
        } else {
            $tier = 'listing';
        }
    }

    $map = [
        'spotlight' => ['label' => 'Event Spotlight', 'summary' => 'A high-interest event that merits prominent advance coverage.'],
        'feature_brief' => ['label' => 'Event Brief', 'summary' => 'A stronger community event that should read like a short local preview.'],
        'community_brief' => ['label' => 'Community Brief', 'summary' => 'A worthwhile local event that merits a concise first-party page.'],
        'listing' => ['label' => 'Calendar Listing', 'summary' => 'A useful public listing that is still being tracked on the desk.'],
    ];

    return array_merge(['key' => $tier], $map[$tier] ?? $map['listing']);
}

function newsroom_event_label(array $event): string
{
    $custom = trim((string) ($event['public_label'] ?? ''));
    if ($custom !== '') {
        return $custom;
    }

    $tier = newsroom_event_tier_data($event);
    return (string) $tier['label'];
}

function newsroom_event_byline(array $event): array
{
    $name = trim((string) ($event['byline_name'] ?? ''));
    $title = trim((string) ($event['byline_title'] ?? ''));

    return [
        'name' => $name !== '' ? $name : 'Wareham Times News Desk',
        'title' => $title !== '' ? $title : 'Community and civic listings desk',
    ];
}

function newsroom_topic_intro_text(string $slug, string $label, array $bundle = []): string
{
    $map = [
        'wastewater' => 'Wastewater coverage follows sewer expansion, financing, regulatory pressure, and the long-running decisions that shape where Wareham can grow.',
        'sewer' => 'Sewer coverage tracks bills, infrastructure planning, neighborhood impacts, and the routine governance decisions behind wastewater service.',
        'town-meeting' => 'Town Meeting coverage follows warrant articles, spending requests, bylaw changes, and the debates that shape the town’s formal decisions.',
        'budget' => 'Budget coverage tracks how Wareham plans to spend money, where departments make their case, and which votes move public dollars.',
        'policy' => 'Policy coverage tracks the rules, revisions, and governance changes that quietly reshape how town and school bodies operate.',
        'schools' => 'Schools coverage follows School Committee votes, district planning, policy changes, and the recurring issues that affect Wareham students and families.',
        'development' => 'Development coverage follows site plans, permits, and board reviews tied to new construction, redevelopment, and land-use change.',
        'zoning' => 'Zoning coverage follows permit requests, appeals, variances, and the regulatory decisions that determine what can be built where.',
        'housing' => 'Housing coverage follows affordable-housing plans, redevelopment, town-owned parcels, and public decisions that affect where people can live.',
        'public-health' => 'Public Health coverage tracks Board of Health hearings, enforcement actions, septic and tobacco cases, and other health-related local decisions.',
        'environment' => 'Environment coverage follows conservation hearings, stormwater issues, open-space decisions, and projects that affect Wareham’s land and water.',
        'community-life' => 'Community Life coverage highlights the local events, traditions, and civic gatherings that shape Wareham outside formal government meetings.',
        'arts-culture' => 'Arts & Culture coverage follows performances, festivals, and public programs that give Wareham’s civic life some texture.',
    ];

    if (isset($map[$slug])) {
        return $map[$slug];
    }

    return newsroom_topic_overview(['label' => $label, 'slug' => $slug], $bundle);
}

function newsroom_display_location(?string $locationName): ?string
{
    $location = trim((string) $locationName);
    if ($location === '') {
        return null;
    }

    if (strtoupper($location) === $location) {
        $location = ucwords(strtolower($location));
        $location = str_replace(['Ma ', 'Rm ', 'Po Box '], ['MA ', 'Rm. ', 'PO Box '], $location);
        $location = preg_replace('/\bMa\b/', 'MA', $location);
        $location = preg_replace('/\bFy(\d+)/', 'FY$1', $location);
    }

    return newsroom_normalize_street_types((string) preg_replace('/\s+/', ' ', $location));
}

function newsroom_normalize_street_types(string $value): string
{
    $value = trim(preg_replace('/\s+/', ' ', $value));
    if ($value === '') {
        return '';
    }

    $patterns = [
        '/\bRd\.?(?=\s|,|$)/i' => 'Road',
        '/\bAve\.?(?=\s|,|$)/i' => 'Avenue',
        '/\bHwy\.?(?=\s|,|$)/i' => 'Highway',
        '/\bLn\.?(?=\s|,|$)/i' => 'Lane',
        '/\bBlvd\.?(?=\s|,|$)/i' => 'Boulevard',
        '/\bSt\.?(?=\s|,|$)/i' => 'Street',
        '/\bDr\.?(?=\s|,|$)/i' => 'Drive',
    ];

    $value = (string) preg_replace(array_keys($patterns), array_values($patterns), $value);
    $value = (string) preg_replace('/\b(Road|Avenue|Highway|Lane|Boulevard|Street|Drive)\.(?=\s|,|$)/i', '$1', $value);
    return trim($value, " ,.;:-");
}

function newsroom_format_meeting_datetime(?string $date, ?string $time, string $fallback = ''): string
{
    if (!$date) {
        return $fallback;
    }

    $stamp = trim($date . ' ' . ($time ?: '00:00:00'));
    $parsed = strtotime($stamp);
    if ($parsed === false) {
        return $fallback ?: $date;
    }

    if ($time && $time !== '00:00:00') {
        return date('F j, Y g:i A', $parsed);
    }

    return date('F j, Y', $parsed);
}

function newsroom_google_maps_url(?string $locationName): ?string
{
    $location = trim((string) $locationName);
    if ($location === '') {
        return null;
    }

    return 'https://www.google.com/maps/search/?api=1&query=' . rawurlencode($location);
}

function newsroom_remote_details(array $structured): array
{
    $sourceMeta = isset($structured['source_meta']) && is_array($structured['source_meta'])
        ? $structured['source_meta']
        : [];
    foreach (['remote_join_url', 'remote_webinar_id', 'remote_passcode', 'remote_phone_numbers'] as $key) {
        if ((!isset($sourceMeta[$key]) || $sourceMeta[$key] === '') && isset($structured[$key])) {
            $sourceMeta[$key] = $structured[$key];
        }
    }

    $phones = isset($sourceMeta['remote_phone_numbers']) && is_array($sourceMeta['remote_phone_numbers'])
        ? array_values(array_filter(array_map('strval', $sourceMeta['remote_phone_numbers'])))
        : [];

    $joinUrl = !empty($sourceMeta['remote_join_url']) ? (string) $sourceMeta['remote_join_url'] : null;
    $webinarId = !empty($sourceMeta['remote_webinar_id']) ? (string) $sourceMeta['remote_webinar_id'] : null;
    $passcode = !empty($sourceMeta['remote_passcode']) ? (string) $sourceMeta['remote_passcode'] : null;
    $hasActionable = $joinUrl !== null || $webinarId !== null || !empty($phones);

    return [
        'join_url' => $joinUrl,
        'webinar_id' => $webinarId,
        'passcode' => $hasActionable ? $passcode : null,
        'phones' => $phones,
    ];
}

function newsroom_story_meta_presenter(array $row): array
{
    $bodyName = (string) ($row['body_name'] ?? $row['governing_body'] ?? '');
    $signal = newsroom_body_signal($bodyName);
    $storyType = (string) ($row['story_type'] ?? '');
    $meetingDate = isset($row['meeting_date']) ? (string) $row['meeting_date'] : null;
    $meetingTime = isset($row['meeting_time']) ? (string) $row['meeting_time'] : null;
    $locationName = newsroom_display_location(isset($row['location_name']) ? (string) $row['location_name'] : null);
    $structured = newsroom_parse_json($row['artifact_structured_json'] ?? null);
    $sourceMeta = newsroom_parse_json($row['agenda_source_meta_json'] ?? null);
    if ($sourceMeta) {
        $structured['source_meta'] = array_merge(
            isset($structured['source_meta']) && is_array($structured['source_meta']) ? $structured['source_meta'] : [],
            $sourceMeta
        );
    }
    $remote = newsroom_remote_details($structured);

    return [
        'body_name' => $signal['name'],
        'body_signal' => $signal,
        'story_type_label' => newsroom_format_story_type($storyType),
        'meeting_datetime' => newsroom_format_meeting_datetime($meetingDate, $meetingTime, (string) ($row['display_date'] ?? $row['published_at'] ?? '')),
        'location_name' => $locationName,
        'location_map_url' => $storyType === 'meeting_preview' ? newsroom_google_maps_url($locationName) : null,
        'agenda_url' => !empty($row['agenda_url']) ? (string) $row['agenda_url'] : null,
        'minutes_url' => !empty($row['minutes_url']) ? (string) $row['minutes_url'] : null,
        'summary_text' => trim((string) ($row['summary'] ?? $row['dek'] ?? '')),
        'dek_text' => trim((string) ($row['dek'] ?? '')),
        'remote' => $remote,
    ];
}

function newsroom_event_presenter(array $row): array
{
    $bodyName = (string) ($row['body_name'] ?? '');
    $signal = newsroom_body_signal($bodyName);
    $structured = newsroom_parse_json($row['agenda_structured_json'] ?? null);
    $sourceMeta = newsroom_parse_json($row['agenda_source_meta_json'] ?? null);
    if ($sourceMeta) {
        $structured['source_meta'] = array_merge(
            isset($structured['source_meta']) && is_array($structured['source_meta']) ? $structured['source_meta'] : [],
            $sourceMeta
        );
    }
    $remote = newsroom_remote_details($structured);
    $locationName = newsroom_display_location(isset($row['location_name']) ? (string) $row['location_name'] : null);
    return [
        'id' => $row['id'],
        'title' => (string) $row['title'],
        'starts_at' => (string) $row['starts_at'],
        'body_name' => $signal['name'],
        'body_signal' => $signal,
        'location_name' => $locationName,
        'location_map_url' => newsroom_google_maps_url($locationName),
        'agenda_url' => !empty($row['agenda_url']) ? (string) $row['agenda_url'] : (string) ($row['source_url'] ?? ''),
        'minutes_url' => !empty($row['minutes_url']) ? (string) $row['minutes_url'] : null,
        'remote' => $remote,
        'summary_text' => trim((string) ($row['story_summary'] ?? $row['story_dek'] ?? $row['description'] ?? '')),
        'dek_text' => trim((string) ($row['story_dek'] ?? '')),
    ];
}

function newsroom_recent_story_presenter(array $row): array
{
    return array_merge($row, [
        'meta' => newsroom_story_meta_presenter($row),
        'topics' => newsroom_parse_topics($row['topic_tags_json'] ?? null),
        'label' => newsroom_story_label($row),
        'byline' => newsroom_story_byline($row),
    ]);
}

function newsroom_community_event_presenter(array $row): array
{
    $sourceType = trim((string) ($row['source_type'] ?? 'community_event'));
    $bodyName = trim((string) ($row['body_name'] ?? ''));
    $signal = newsroom_body_signal($bodyName !== '' ? $bodyName : ucwords(str_replace('_', ' ', $sourceType)));
    $locationName = newsroom_display_location((string) ($row['address_text'] ?? $row['location_name'] ?? ''));

    return [
        'id' => (int) $row['id'],
        'title' => (string) $row['title'],
        'slug' => (string) ($row['slug'] ?? ''),
        'local_url' => newsroom_community_event_url($row),
        'starts_at' => (string) $row['starts_at'],
        'ends_at' => (string) ($row['ends_at'] ?? ''),
        'location_name' => $locationName,
        'location_map_url' => newsroom_google_maps_url($locationName),
        'source_url' => (string) $row['source_url'],
        'source_category' => (string) ($row['source_category'] ?? ''),
        'source_type' => $sourceType,
        'body_name' => $bodyName,
        'body_signal' => $signal,
        'description' => trim((string) ($row['description'] ?? '')),
        'editorial_score' => (int) ($row['editorial_score'] ?? 0),
        'effective_score' => isset($row['effective_score']) ? (int) $row['effective_score'] : (int) ($row['score_override'] ?? $row['editorial_score'] ?? 0),
        'suggested_coverage_mode' => (string) ($row['suggested_coverage_mode'] ?? 'calendar_only'),
        'effective_coverage_mode' => (string) ($row['effective_coverage_mode'] ?? ($row['coverage_override'] ?? $row['suggested_coverage_mode'] ?? 'calendar_only')),
        'signal_summary' => newsroom_signal_summary($row['editorial_signals_json'] ?? null),
        'editorial_signals_json' => (string) ($row['editorial_signals_json'] ?? ''),
        'topics' => newsroom_parse_topics($row['topic_tags_json'] ?? null),
        'score_override' => isset($row['score_override']) ? (int) $row['score_override'] : null,
        'coverage_override' => (string) ($row['coverage_override'] ?? ''),
        'admin_notes' => (string) ($row['admin_notes'] ?? ''),
        'is_hidden' => !empty($row['is_hidden']),
        'label' => newsroom_event_label($row),
        'byline' => newsroom_event_byline($row),
        'event_tier' => newsroom_event_tier_data($row),
        'live_prep_notes' => (string) ($row['live_prep_notes'] ?? ''),
    ];
}

function newsroom_community_event_story_meta(array $event): array
{
    $parts = [];
    if (!empty($event['source_type'])) {
        $parts[] = ucwords(str_replace('_', ' ', (string) $event['source_type']));
    }
    if (!empty($event['source_category'])) {
        $parts[] = (string) $event['source_category'];
    }
    if (!empty($event['effective_coverage_mode'])) {
        $parts[] = 'Coverage: ' . str_replace('_', ' ', (string) $event['effective_coverage_mode']);
    }
    return $parts;
}

function newsroom_community_event_summary(array $event): string
{
    $description = trim((string) ($event['description'] ?? ''));
    if ($description !== '') {
        $description = newsroom_truncate_text($description, 220);
        $startsAt = strtotime((string) ($event['starts_at'] ?? ''));
        if ($startsAt !== false) {
            return $description . ' The event is scheduled for ' . date('F j, Y \a\t g:i A', $startsAt) . '.';
        }
        return $description;
    }

    $startsAt = strtotime((string) ($event['starts_at'] ?? ''));
    if ($startsAt === false) {
        return '';
    }

    $title = trim((string) ($event['title'] ?? 'The event'));
    $location = trim((string) ($event['location_name'] ?? ''));
    $summary = $title . ' is scheduled for ' . date('F j, Y \a\t g:i A', $startsAt) . '.';
    if ($location !== '') {
        $summary .= ' It is listed for ' . $location . '.';
    }
    return $summary;
}

function newsroom_community_event_focus(array $event): string
{
    $description = trim((string) ($event['description'] ?? ''));
    if ($description !== '') {
        return newsroom_truncate_text($description, 320);
    }

    $title = trim((string) ($event['title'] ?? 'The event'));
    $startsAt = strtotime((string) ($event['starts_at'] ?? ''));
    $location = trim((string) ($event['location_name'] ?? ''));
    $parts = [];
    if ($startsAt !== false) {
        $parts[] = 'is scheduled for ' . date('F j, Y \a\t g:i A', $startsAt);
    }
    if ($location !== '') {
        $parts[] = 'will take place at ' . $location;
    }
    return $title . ($parts ? ' ' . newsroom_sentence_list($parts) . '.' : '.');
}

function newsroom_community_event_signal_items(array $event, int $limit = 4): array
{
    $signals = newsroom_sorted_signals($event['editorial_signals_json'] ?? null);
    $items = [];
    foreach ($signals as $signal) {
        $weight = (int) ($signal['weight'] ?? 0);
        $reason = trim((string) ($signal['reason'] ?? ''));
        if ($weight <= 0 || $reason === '') {
            continue;
        }
        $items[] = [
            'reason' => $reason,
            'weight' => $weight,
        ];
    }

    usort($items, static function (array $a, array $b): int {
        return $b['weight'] <=> $a['weight'];
    });

    return array_slice($items, 0, $limit);
}

function newsroom_community_event_brief_intro(array $event): string
{
    $title = trim((string) ($event['title'] ?? 'This event'));
    $startsAt = strtotime((string) ($event['starts_at'] ?? ''));
    $location = trim((string) ($event['location_name'] ?? ''));
    $lead = $title;

    if ($startsAt !== false) {
        $lead .= ' is scheduled for ' . date('F j, Y \a\t g:i A', $startsAt);
    }
    if ($location !== '') {
        $lead .= ' at ' . $location;
    }

    $focus = trim((string) ($event['description'] ?? ''));
    if ($focus !== '') {
        return $lead . '. ' . newsroom_truncate_text($focus, 240);
    }

    return $lead . '.';
}

function newsroom_community_event_editorial_note(array $event): string
{
    $signals = newsroom_community_event_signal_items($event, 3);
    if (!$signals) {
        return 'The editorial desk flagged this listing as a potentially worthwhile local item to watch.';
    }

    $reasons = array_map(static function (array $signal): string {
        return strtolower((string) $signal['reason']);
    }, $signals);

    return 'The editorial desk elevated this event because it suggests ' . newsroom_sentence_list($reasons) . '.';
}

function newsroom_topic_overview(array $topic, array $bundle): string
{
    $storyCount = count($bundle['stories'] ?? []);
    $eventCount = count($bundle['events'] ?? []);
    $label = (string) ($topic['label'] ?? 'This topic');

    $parts = [];
    if ($storyCount > 0) {
        $parts[] = $storyCount . ' recent story' . ($storyCount === 1 ? '' : 'ies');
    }
    if ($eventCount > 0) {
        $parts[] = $eventCount . ' upcoming event' . ($eventCount === 1 ? '' : 's');
    }

    if ($parts) {
        return $label . ' coverage currently includes ' . newsroom_sentence_list($parts) . '.';
    }

    return $label . ' is tracked as a recurring local coverage area.';
}

function newsroom_story_next_steps(array $story): string
{
    $storyType = (string) ($story['story_type'] ?? '');
    $meetingDate = trim((string) ($story['meeting_date'] ?? ''));
    $meetingTime = trim((string) ($story['meeting_time'] ?? ''));
    $bodyName = trim((string) ($story['meta']['body_name'] ?? $story['body_name'] ?? 'the board'));
    $when = newsroom_format_meeting_datetime($meetingDate !== '' ? $meetingDate : null, $meetingTime !== '' ? $meetingTime : null, '');

    if ($storyType === 'meeting_preview') {
        if ($when !== '') {
            return 'The next step is the meeting itself: ' . $bodyName . ' is scheduled for ' . $when . '. After that, the newsroom can compare the discussion, votes, and any posted minutes against the preview.';
        }
        return 'The next step is the meeting itself, followed by any votes, follow-up actions, and posted minutes.';
    }

    if ($storyType === 'minutes_recap') {
        return 'The next step is to watch for follow-up votes, implementation steps, or agenda items that bring the issue back before ' . $bodyName . '.';
    }

    return 'The next step is to watch for follow-up actions, later agenda items, or posted records that advance the issue.';
}

function newsroom_story_related_bundle(array $story, int $storyLimit = 4, int $eventLimit = 4): array
{
    $topics = newsroom_parse_topics($story['topic_tags_json'] ?? null);
    if (!$topics || !newsroom_db_available()) {
        return ['topic' => null, 'stories' => [], 'events' => []];
    }

    $primaryTopic = $topics[0];
    $bundle = newsroom_topic_bundle((string) $primaryTopic['slug'], $storyLimit + 1, $eventLimit);
    $relatedStories = array_values(array_filter($bundle['stories'], static function (array $candidate) use ($story): bool {
        return (int) ($candidate['id'] ?? 0) !== (int) ($story['id'] ?? 0);
    }));

    return [
        'topic' => $primaryTopic,
        'stories' => array_slice($relatedStories, 0, $storyLimit),
        'events' => array_slice($bundle['events'], 0, $eventLimit),
    ];
}

function newsroom_event_related_bundle(array $event, int $storyLimit = 4, int $eventLimit = 4): array
{
    $topics = newsroom_parse_topics($event['topic_tags_json'] ?? null);
    if (!$topics || !newsroom_db_available()) {
        return ['topic' => null, 'stories' => [], 'events' => []];
    }

    $primaryTopic = $topics[0];
    $bundle = newsroom_topic_bundle((string) $primaryTopic['slug'], $storyLimit, $eventLimit + 1);
    $relatedEvents = array_values(array_filter($bundle['events'], static function (array $candidate) use ($event): bool {
        return (int) ($candidate['id'] ?? 0) !== (int) ($event['id'] ?? 0);
    }));

    return [
        'topic' => $primaryTopic,
        'stories' => array_slice($bundle['stories'], 0, $storyLimit),
        'events' => array_slice($relatedEvents, 0, $eventLimit),
    ];
}

function newsroom_latest_stories(int $limit = 8): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    newsroom_maybe_trigger_worker_refresh();

    $baseSelect = 'SELECT
            s.id,
            s.slug,
            s.story_type,
            s.headline,
            s.dek,
            s.summary,
            s.topic_tags_json,
            s.published_at,
            s.display_date,
            s.sort_date,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            COALESCE(gb.normalized_name, m.governing_body) AS body_name,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_url,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS artifact_structured_json,
            (
                SELECT si.raw_meta_json
                FROM meeting_artifacts ma
                INNER JOIN source_items si ON si.id = ma.source_item_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_source_meta_json
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE publish_status = :status';

    $orderedTail = '
         ORDER BY
            CASE
                WHEN s.story_type = "meeting_preview" AND m.meeting_date IS NOT NULL AND TIMESTAMP(m.meeting_date, COALESCE(m.meeting_time, "00:00:00")) >= NOW() THEN 0
                ELSE 1
            END ASC,
            CASE
                WHEN s.story_type = "meeting_preview" AND m.meeting_date IS NOT NULL AND TIMESTAMP(m.meeting_date, COALESCE(m.meeting_time, "00:00:00")) >= NOW()
                THEN TIMESTAMP(m.meeting_date, COALESCE(m.meeting_time, "00:00:00"))
                ELSE NULL
            END ASC,
            COALESCE(s.sort_date, s.display_date, s.published_at, TIMESTAMP(m.meeting_date, COALESCE(m.meeting_time, "00:00:00"))) DESC,
            s.id DESC
         LIMIT :limit';

    $statement = newsroom_db()->prepare(
        $baseSelect . '
           AND NOT (
                s.story_type = "meeting_preview"
                AND m.meeting_date IS NOT NULL
                AND m.meeting_date < DATE_SUB(CURDATE(), INTERVAL 2 DAY)
            )' . $orderedTail
    );
    $statement->bindValue(':status', 'published');
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    $rows = $statement->fetchAll();
    if ($rows) {
        return array_map('newsroom_recent_story_presenter', $rows);
    }

    $fallbackStatement = newsroom_db()->prepare(
        $baseSelect . $orderedTail
    );
    $fallbackStatement->bindValue(':status', 'published');
    $fallbackStatement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $fallbackStatement->execute();

    return array_map('newsroom_recent_story_presenter', $fallbackStatement->fetchAll());
}

function newsroom_story_by_slug(string $slug): ?array
{
    if (!newsroom_db_available()) {
        return null;
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.story_type,
            s.public_label,
            s.byline_name,
            s.byline_title,
            s.headline,
            s.dek,
            s.summary,
            s.body_html,
            s.topic_tags_json,
            s.published_at,
            s.display_date,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            COALESCE(gb.normalized_name, m.governing_body) AS body_name,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_url,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id
                  AND ma.artifact_type = CASE WHEN s.story_type = "minutes_recap" THEN "minutes" ELSE "agenda" END
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS artifact_structured_json
            ,
            (
                SELECT si.raw_meta_json
                FROM meeting_artifacts ma
                INNER JOIN source_items si ON si.id = ma.source_item_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_source_meta_json
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE s.slug = :slug AND s.publish_status = :status
         LIMIT 1'
    );
    $statement->execute([
        ':slug' => $slug,
        ':status' => 'published',
    ]);

    $story = $statement->fetch();
    if (!$story) {
        return null;
    }

    $story['meta'] = newsroom_story_meta_presenter($story);
    $story['topics'] = newsroom_parse_topics($story['topic_tags_json'] ?? null);
    $story['label'] = newsroom_story_label($story);
    $story['byline'] = newsroom_story_byline($story);
    return $story;
}

function newsroom_story_citations(int $storyId): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT citation_number, label, source_url, quote_text, note_text
         FROM story_citations
         WHERE story_id = :story_id
         ORDER BY citation_number ASC'
    );
    $statement->execute([':story_id' => $storyId]);

    return $statement->fetchAll();
}

function newsroom_upcoming_events(int $limit = 10): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    newsroom_maybe_trigger_worker_refresh();

    $statement = newsroom_db()->prepare(
        'SELECT
            ce.id,
            ce.title,
            ce.starts_at,
            ce.location_name,
            ce.body_name,
            ce.source_url,
            ce.description,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = ce.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_url,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = ce.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT s.dek
                FROM stories s
                WHERE s.meeting_id = ce.meeting_id AND s.story_type = "meeting_preview" AND s.publish_status = "published"
                LIMIT 1
            ) AS story_dek,
            (
                SELECT s.summary
                FROM stories s
                WHERE s.meeting_id = ce.meeting_id AND s.story_type = "meeting_preview" AND s.publish_status = "published"
                LIMIT 1
            ) AS story_summary,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = ce.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_structured_json
            ,
            (
                SELECT si.raw_meta_json
                FROM meeting_artifacts ma
                INNER JOIN source_items si ON si.id = ma.source_item_id
                WHERE ma.meeting_id = ce.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_source_meta_json
         FROM calendar_events ce
         WHERE ce.starts_at >= NOW() AND ce.status = :status
         ORDER BY ce.starts_at ASC
         LIMIT :limit'
    );
    $statement->bindValue(':status', 'scheduled');
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return array_map('newsroom_event_presenter', $statement->fetchAll());
}

function newsroom_storyworthy_community_events(int $limit = 6): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            ce.*,
            COALESCE(ce.score_override, ce.editorial_score) AS effective_score,
            COALESCE(NULLIF(ce.coverage_override, ""), ce.suggested_coverage_mode) AS effective_coverage_mode
         FROM community_events ce
         WHERE ce.is_hidden = 0
           AND ce.starts_at >= NOW()
           AND COALESCE(NULLIF(ce.coverage_override, ""), ce.suggested_coverage_mode) IN ("brief", "full_story")
         ORDER BY COALESCE(ce.score_override, ce.editorial_score) DESC, ce.starts_at ASC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return array_map('newsroom_community_event_presenter', $statement->fetchAll());
}

function newsroom_upcoming_community_events(int $limit = 20): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            ce.*,
            COALESCE(ce.score_override, ce.editorial_score) AS effective_score,
            COALESCE(NULLIF(ce.coverage_override, ""), ce.suggested_coverage_mode) AS effective_coverage_mode
         FROM community_events ce
         WHERE ce.is_hidden = 0
           AND ce.starts_at >= NOW()
         ORDER BY ce.starts_at ASC, COALESCE(ce.score_override, ce.editorial_score) DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return array_map('newsroom_community_event_presenter', $statement->fetchAll());
}

function newsroom_community_event_by_id(int $id): ?array
{
    if (!newsroom_db_available() || $id <= 0) {
        return null;
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            ce.*,
            COALESCE(ce.score_override, ce.editorial_score) AS effective_score,
            COALESCE(NULLIF(ce.coverage_override, ""), ce.suggested_coverage_mode) AS effective_coverage_mode
         FROM community_events ce
         WHERE ce.id = :id AND ce.is_hidden = 0
         LIMIT 1'
    );
    $statement->execute([':id' => $id]);
    $row = $statement->fetch();
    if (!$row) {
        return null;
    }

    return newsroom_community_event_presenter($row);
}

function newsroom_recent_meeting_recaps(int $limit = 12): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.story_type,
            s.headline,
            s.dek,
            s.summary,
            s.published_at,
            s.display_date,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            COALESCE(gb.normalized_name, m.governing_body) AS body_name,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS artifact_structured_json
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE s.publish_status = "published" AND s.story_type = "minutes_recap"
         ORDER BY COALESCE(s.sort_date, s.display_date, s.published_at) DESC, s.id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return array_map('newsroom_recent_story_presenter', $statement->fetchAll());
}

function newsroom_recent_runs(int $limit = 20): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT id, started_at, finished_at, run_status, items_discovered, documents_fetched, extractions_created, meetings_normalized, stories_published, stories_updated, events_created, events_updated
         FROM generation_runs
         ORDER BY started_at DESC, id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return $statement->fetchAll();
}

function newsroom_diagnostic_items(int $limit = 20): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            si.id,
            si.title,
            si.canonical_url,
            si.status,
            MAX(de.confidence_score) AS confidence_score,
            MAX(de.warnings_json) AS warnings_json,
            MAX(de.structured_json) AS structured_json
         FROM source_items si
         LEFT JOIN documents d ON d.source_item_id = si.id
         LEFT JOIN document_extractions de ON de.document_id = d.id
         WHERE (
                si.status IN ("needs_review", "extracted")
                OR (de.confidence_score IS NOT NULL AND de.confidence_score < 0.60)
           )
           AND LOWER(COALESCE(si.title, "")) NOT LIKE "%packet%"
           AND LOWER(COALESCE(si.title, "")) NOT LIKE "%previous version%"
           AND LOWER(COALESCE(si.title, "")) NOT LIKE "%html%"
           AND LOWER(COALESCE(si.title, "")) NOT IN ("notify meÂ®", "notify me", "rss")
           AND LOWER(COALESCE(si.canonical_url, "")) NOT LIKE "%/list.aspx#agendacenter%"
           AND LOWER(COALESCE(si.canonical_url, "")) NOT LIKE "%/rss.aspx#agendacenter%"
         GROUP BY si.id, si.title, si.canonical_url, si.status
         ORDER BY si.updated_at DESC, si.id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return $statement->fetchAll();
}

function newsroom_editorial_items(int $limit = 120): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT * FROM (
            SELECT
                "story" AS entity_type,
                s.id AS entity_id,
                s.headline AS title,
                s.story_type AS item_type,
                COALESCE(gb.normalized_name, m.governing_body, "") AS body_name,
                COALESCE(s.sort_date, s.display_date, s.published_at) AS occurs_at,
                s.editorial_score,
                s.editorial_signals_json,
            s.suggested_coverage_mode,
            s.score_override,
            s.coverage_override,
            s.admin_notes,
            s.workflow_status,
            s.watch_live,
            s.follow_up_needed,
            s.topic_tags_json,
            0 AS is_hidden,
                s.publish_status AS status_label,
                s.slug AS public_slug,
                "" AS public_url
            FROM stories s
            LEFT JOIN meetings m ON m.id = s.meeting_id
            LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
            UNION ALL
            SELECT
                "community_event" AS entity_type,
                ce.id AS entity_id,
                ce.title AS title,
                ce.source_type AS item_type,
                COALESCE(ce.body_name, ce.source_category, "") AS body_name,
                ce.starts_at AS occurs_at,
                ce.editorial_score,
                ce.editorial_signals_json,
                ce.suggested_coverage_mode,
                ce.score_override,
                ce.coverage_override,
                ce.admin_notes,
                ce.workflow_status,
                ce.watch_live,
                ce.follow_up_needed,
                ce.topic_tags_json,
                ce.is_hidden AS is_hidden,
                ce.source_category AS status_label,
                ce.slug AS public_slug,
                ce.source_url AS public_url
            FROM community_events ce
        ) editorial_items
        ORDER BY COALESCE(score_override, editorial_score) DESC, occurs_at ASC, entity_type ASC
        LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    $rows = $statement->fetchAll();
    foreach ($rows as &$row) {
        if ((string) ($row['entity_type'] ?? '') === 'story' && !empty($row['public_slug'])) {
            $row['public_url'] = newsroom_story_url_from_slug((string) $row['public_slug']);
        }
        if ((string) ($row['entity_type'] ?? '') === 'community_event') {
            $row['public_url'] = newsroom_community_event_url_from_parts((int) ($row['entity_id'] ?? 0), (string) ($row['public_slug'] ?? ''));
        }
        $row['effective_score'] = isset($row['score_override']) && $row['score_override'] !== null
            ? (int) $row['score_override']
            : (int) $row['editorial_score'];
        $row['effective_coverage_mode'] = trim((string) ($row['coverage_override'] ?? '')) !== ''
            ? (string) $row['coverage_override']
            : (string) $row['suggested_coverage_mode'];
        $row['workflow_status'] = newsroom_normalize_workflow_status((string) ($row['workflow_status'] ?? ''), $row);
        $row['workflow_label'] = newsroom_workflow_label((string) $row['workflow_status']);
        $row['next_action'] = newsroom_workflow_next_action($row);
        $row['signal_summary'] = newsroom_signal_summary($row['editorial_signals_json'] ?? null);
    }
    unset($row);

    return $rows;
}

function newsroom_recap_queue_items(int $limit = 60): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.headline,
            s.summary,
            s.draft_headline,
            s.draft_dek,
            s.draft_body,
            s.draft_updated_at,
            s.story_type,
            s.workflow_status,
            s.watch_live,
            s.follow_up_needed,
            s.admin_notes,
            s.display_date,
            s.published_at,
            COALESCE(s.sort_date, s.display_date, s.published_at) AS occurs_at,
            COALESCE(gb.normalized_name, m.governing_body, "") AS body_name,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_url,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_structured_json,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_structured_json
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE s.publish_status = "published"
           AND s.workflow_status IN ("recap_needed", "minutes_reconcile")
         ORDER BY
            CASE s.workflow_status
                WHEN "recap_needed" THEN 0
                WHEN "minutes_reconcile" THEN 1
                ELSE 2
            END,
            COALESCE(s.sort_date, s.display_date, s.published_at) DESC,
            s.id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    $rows = $statement->fetchAll();
    foreach ($rows as &$row) {
        $row['public_url'] = newsroom_story_url_from_slug((string) ($row['slug'] ?? ''));
        $row['workflow_status'] = newsroom_normalize_workflow_status((string) ($row['workflow_status'] ?? ''), [
            'entity_type' => 'story',
            'item_type' => (string) ($row['story_type'] ?? ''),
        ]);
        $row['workflow_label'] = newsroom_workflow_label((string) $row['workflow_status']);
        $row['next_action'] = newsroom_workflow_next_action($row);
        $row['recap_scaffold'] = newsroom_recap_scaffold($row);
    }
    unset($row);

    return $rows;
}

function newsroom_recap_queue_item(int $id): ?array
{
    if (!newsroom_db_available() || $id <= 0) {
        return null;
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.headline,
            s.summary,
            s.draft_headline,
            s.draft_dek,
            s.draft_body,
            s.draft_updated_at,
            s.story_type,
            s.workflow_status,
            s.watch_live,
            s.follow_up_needed,
            s.admin_notes,
            s.display_date,
            s.published_at,
            COALESCE(s.sort_date, s.display_date, s.published_at) AS occurs_at,
            COALESCE(gb.normalized_name, m.governing_body, "") AS body_name,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_url,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_url,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_structured_json,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "minutes"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS minutes_structured_json
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE s.id = :id AND s.publish_status = "published"
         LIMIT 1'
    );
    $statement->bindValue(':id', $id, PDO::PARAM_INT);
    $statement->execute();
    $row = $statement->fetch();
    if (!$row) {
        return null;
    }

    $row['public_url'] = newsroom_story_url_from_slug((string) ($row['slug'] ?? ''));
    $row['workflow_status'] = newsroom_normalize_workflow_status((string) ($row['workflow_status'] ?? ''), [
        'entity_type' => 'story',
        'item_type' => (string) ($row['story_type'] ?? ''),
    ]);
    $row['workflow_label'] = newsroom_workflow_label((string) $row['workflow_status']);
    $row['next_action'] = newsroom_workflow_next_action($row);
    $row['recap_scaffold'] = newsroom_recap_scaffold($row);
    $row['draft_workspace'] = newsroom_recap_draft_workspace($row);

    return $row;
}

function newsroom_recap_scaffold(array $row): array
{
    $agendaStructured = newsroom_parse_json($row['agenda_structured_json'] ?? null);
    $minutesStructured = newsroom_parse_json($row['minutes_structured_json'] ?? null);
    $agendaHighlights = [];
    foreach ((array) ($agendaStructured['agenda_highlights'] ?? []) as $item) {
        $text = trim((string) $item);
        if ($text !== '') {
            $agendaHighlights[] = $text;
        }
    }

    $minutesHighlights = [];
    foreach ((array) ($minutesStructured['agenda_highlights'] ?? []) as $item) {
        $text = trim((string) $item);
        if ($text !== '') {
            $minutesHighlights[] = $text;
        }
    }

    $agendaSections = [];
    foreach ((array) ($agendaStructured['agenda_sections'] ?? []) as $section) {
        if (!is_array($section)) {
            continue;
        }
        $title = trim((string) ($section['title'] ?? ''));
        $items = [];
        foreach ((array) ($section['items'] ?? []) as $item) {
            $text = trim((string) $item);
            if ($text !== '') {
                $items[] = $text;
            }
        }
        if ($title !== '' || $items) {
            $agendaSections[] = ['title' => $title, 'items' => $items];
        }
    }

    $minutesSections = [];
    foreach ((array) ($minutesStructured['agenda_sections'] ?? []) as $section) {
        if (!is_array($section)) {
            continue;
        }
        $title = trim((string) ($section['title'] ?? ''));
        $items = [];
        foreach ((array) ($section['items'] ?? []) as $item) {
            $text = trim((string) $item);
            if ($text !== '') {
                $items[] = $text;
            }
        }
        if ($title !== '' || $items) {
            $minutesSections[] = ['title' => $title, 'items' => $items];
        }
    }

    $leadItems = array_slice($minutesHighlights ?: $agendaHighlights, 0, 3);
    $bodyName = trim((string) ($row['body_name'] ?? 'The board'));
    $meetingDate = trim((string) ($row['meeting_date'] ?? ''));
    $meetingTime = trim((string) ($row['meeting_time'] ?? ''));
    $location = trim((string) ($row['location_name'] ?? ''));

    $timePhrase = '';
    if ($meetingDate !== '') {
        $stamp = strtotime($meetingDate . ($meetingTime !== '' ? ' ' . $meetingTime : ''));
        if ($stamp !== false) {
            $timePhrase = date($meetingTime !== '' ? 'F j, Y \a\t g:i A' : 'F j, Y', $stamp);
        }
    }

    $workflow = (string) ($row['workflow_status'] ?? '');
    $lede = '';
    if ($workflow === 'minutes_reconcile' && $minutesHighlights) {
        $lede = $bodyName . ' minutes indicate discussion or action on ' . newsroom_sentence_list(array_map(static function (string $item): string {
            return strtolower($item);
        }, array_slice($minutesHighlights, 0, 2))) . '.';
    } elseif ($leadItems) {
        $lede = $bodyName . ' is expected to focus on ' . newsroom_sentence_list(array_map(static function (string $item): string {
            return strtolower($item);
        }, array_slice($leadItems, 0, 2))) . '.';
    } elseif ($timePhrase !== '') {
        $lede = $bodyName . ' is scheduled to meet ' . $timePhrase . '.';
    } else {
        $lede = $bodyName . ' remains in the recap queue and needs a post-meeting summary.';
    }

    $verification = [];
    if ($workflow === 'recap_needed') {
        $verification[] = 'Confirm whether any votes or decisions actually happened.';
        $verification[] = 'Check whether the top agenda items were discussed, continued, or amended.';
    } else {
        $verification[] = 'Compare the published story against the posted minutes.';
        $verification[] = 'Check whether any motions, votes, or attendance details need correction.';
    }
    if ($location !== '') {
        $verification[] = 'Verify location details remain correct: ' . $location . '.';
    }

    $angle = '';
    if ($workflow === 'minutes_reconcile' && $minutesHighlights) {
        $angle = 'Lead with the clearest confirmed action from the minutes: ' . $minutesHighlights[0] . '.';
    } elseif ($leadItems) {
        $angle = 'Start with the most consequential item: ' . $leadItems[0] . '.';
    } else {
        $angle = 'Use the official record to identify the most consequential action taken.';
    }

    $publishPlan = [];
    if ($workflow === 'recap_needed') {
        $publishPlan[] = 'Open with the clearest confirmed action or outcome, not the meeting schedule.';
        $publishPlan[] = 'If no vote occurred, say the board discussed or continued the matter rather than implying action.';
        $publishPlan[] = 'Keep one paragraph focused on what happens next: a continued hearing, future vote, or implementation step.';
    } else {
        $publishPlan[] = 'Use the minutes to confirm whether the current public story needs a factual correction or only a wording update.';
        $publishPlan[] = 'If the minutes confirm a major vote or decision, update the story lede and dek before marking the item done.';
        $publishPlan[] = 'If the minutes materially expand the story, queue a follow-up rather than silently revising the preview.';
    }

    $recordStatus = [
        'agenda_available' => !empty($row['agenda_url']),
        'minutes_available' => !empty($row['minutes_url']),
        'agenda_highlight_count' => count($agendaHighlights),
        'minutes_highlight_count' => count($minutesHighlights),
    ];

    return [
        'lede' => $lede,
        'angle' => $angle,
        'highlights' => $leadItems,
        'verification' => $verification,
        'agenda_highlights' => array_slice($agendaHighlights, 0, 6),
        'minutes_highlights' => array_slice($minutesHighlights, 0, 6),
        'agenda_sections' => array_slice($agendaSections, 0, 4),
        'minutes_sections' => array_slice($minutesSections, 0, 4),
        'publish_plan' => $publishPlan,
        'record_status' => $recordStatus,
    ];
}

function newsroom_recap_draft_workspace(array $row): array
{
    $scaffold = $row['recap_scaffold'] ?? newsroom_recap_scaffold($row);
    $bodyName = trim((string) ($row['body_name'] ?? 'Board'));
    $meetingDate = trim((string) ($row['meeting_date'] ?? ''));
    $meetingTime = trim((string) ($row['meeting_time'] ?? ''));
    $location = trim((string) ($row['location_name'] ?? ''));

    $datetimeLine = '';
    if ($meetingDate !== '') {
        $stamp = strtotime($meetingDate . ($meetingTime !== '' ? ' ' . $meetingTime : ''));
        if ($stamp !== false) {
            $datetimeLine = date($meetingTime !== '' ? 'F j, Y \a\t g:i A' : 'F j, Y', $stamp);
        }
    }

    $headline = trim((string) ($row['headline'] ?? ''));
    if (!empty($scaffold['minutes_highlights'][0])) {
        $headline = $bodyName . ' recap: ' . (string) $scaffold['minutes_highlights'][0];
    } elseif ($headline !== '') {
        $headline = preg_replace('/\bto (Discuss|Review|Hear|Meet and Consider|Consider)\b/i', 'holds', $headline) ?: $headline;
    }
    if ($headline === '') {
        $headline = $bodyName . ' meeting recap';
    }

    $dekParts = [];
    if (!empty($scaffold['minutes_highlights'])) {
        $dekParts[] = newsroom_sentence_list(array_slice((array) $scaffold['minutes_highlights'], 0, 2));
    } elseif ($datetimeLine !== '') {
        $dekParts[] = $bodyName . ' met ' . strtolower($datetimeLine);
    }
    if ($location !== '') {
        $dekParts[] = 'at ' . $location;
    }
    $dek = ucfirst(trim(implode(' ', $dekParts))) . '.';
    if ($dek === '.') {
        $dek = 'Use the official record to confirm the key outcome from this meeting.';
    }

    $bodySections = [];
    $bodySections[] = "Lede\n" . trim((string) ($scaffold['lede'] ?? ''));
    $bodySections[] = "Reporting Angle\n" . trim((string) ($scaffold['angle'] ?? ''));
    $bodySections[] = "What happened\n- Confirm the main action taken.\n- Note whether the board voted, continued the matter, or only discussed it.";
    if (!empty($scaffold['highlights'])) {
        $bodySections[] = "Top items to cover\n- " . implode("\n- ", array_map('strval', (array) $scaffold['highlights']));
    }
    if (!empty($scaffold['minutes_highlights'])) {
        $bodySections[] = "What the minutes appear to confirm\n- " . implode("\n- ", array_map('strval', (array) $scaffold['minutes_highlights']));
    }
    if (!empty($scaffold['verification'])) {
        $bodySections[] = "What to verify\n- " . implode("\n- ", array_map('strval', (array) $scaffold['verification']));
    }
    if (!empty($scaffold['publish_plan'])) {
        $bodySections[] = "Publish plan\n- " . implode("\n- ", array_map('strval', (array) $scaffold['publish_plan']));
    }
    $bodySections[] = "What happens next\n- Note any continued hearing, follow-up vote, future meeting date, or implementation step.";

    return [
        'headline' => $headline,
        'dek' => $dek,
        'body' => implode("\n\n", $bodySections),
    ];
}

function newsroom_update_recap_draft(int $storyId, string $headline, string $dek, string $body): void
{
    if (!newsroom_db_available() || $storyId <= 0) {
        return;
    }

    $statement = newsroom_db()->prepare(
        'UPDATE stories
         SET draft_headline = :headline,
             draft_dek = :dek,
             draft_body = :body,
             draft_updated_at = NOW()
         WHERE id = :id'
    );
    $statement->bindValue(':headline', trim($headline) !== '' ? trim($headline) : null, trim($headline) !== '' ? PDO::PARAM_STR : PDO::PARAM_NULL);
    $statement->bindValue(':dek', trim($dek) !== '' ? trim($dek) : null, trim($dek) !== '' ? PDO::PARAM_STR : PDO::PARAM_NULL);
    $statement->bindValue(':body', trim($body) !== '' ? trim($body) : null, trim($body) !== '' ? PDO::PARAM_STR : PDO::PARAM_NULL);
    $statement->bindValue(':id', $storyId, PDO::PARAM_INT);
    $statement->execute();
}

function newsroom_update_editorial_override(array $payload): void
{
    if (!newsroom_db_available()) {
        return;
    }

    $entityType = (string) ($payload['entity_type'] ?? '');
    $entityId = (int) ($payload['entity_id'] ?? 0);
    $scoreOverrideRaw = trim((string) ($payload['score_override'] ?? ''));
    $coverageOverride = trim((string) ($payload['coverage_override'] ?? ''));
    $adminNotes = trim((string) ($payload['admin_notes'] ?? ''));
    $isHidden = !empty($payload['is_hidden']) ? 1 : 0;
    $workflowStatus = trim((string) ($payload['workflow_status'] ?? ''));
    $watchLive = !empty($payload['watch_live']) ? 1 : 0;
    $followUpNeeded = !empty($payload['follow_up_needed']) ? 1 : 0;
    $scoreOverride = $scoreOverrideRaw === '' ? null : (int) $scoreOverrideRaw;

    if ($entityId <= 0) {
        return;
    }

    if ($entityType === 'story') {
        $statement = newsroom_db()->prepare(
            'UPDATE stories
             SET score_override = :score_override,
                 coverage_override = :coverage_override,
                 admin_notes = :admin_notes,
                 workflow_status = :workflow_status,
                 watch_live = :watch_live,
                 follow_up_needed = :follow_up_needed
             WHERE id = :id'
        );
        $statement->bindValue(':score_override', $scoreOverride, $scoreOverride === null ? PDO::PARAM_NULL : PDO::PARAM_INT);
        $statement->bindValue(':coverage_override', $coverageOverride !== '' ? $coverageOverride : null, $coverageOverride !== '' ? PDO::PARAM_STR : PDO::PARAM_NULL);
        $statement->bindValue(':admin_notes', $adminNotes !== '' ? $adminNotes : null, $adminNotes !== '' ? PDO::PARAM_STR : PDO::PARAM_NULL);
        $statement->bindValue(':workflow_status', $workflowStatus !== '' ? $workflowStatus : 'done', PDO::PARAM_STR);
        $statement->bindValue(':watch_live', $watchLive, PDO::PARAM_INT);
        $statement->bindValue(':follow_up_needed', $followUpNeeded, PDO::PARAM_INT);
        $statement->bindValue(':id', $entityId, PDO::PARAM_INT);
        $statement->execute();
        return;
    }

    if ($entityType === 'community_event') {
        $statement = newsroom_db()->prepare(
            'UPDATE community_events
             SET score_override = :score_override,
                 coverage_override = :coverage_override,
                 admin_notes = :admin_notes,
                 workflow_status = :workflow_status,
                 watch_live = :watch_live,
                 follow_up_needed = :follow_up_needed,
                 is_hidden = :is_hidden
             WHERE id = :id'
        );
        $statement->bindValue(':score_override', $scoreOverride, $scoreOverride === null ? PDO::PARAM_NULL : PDO::PARAM_INT);
        $statement->bindValue(':coverage_override', $coverageOverride !== '' ? $coverageOverride : null, $coverageOverride !== '' ? PDO::PARAM_STR : PDO::PARAM_NULL);
        $statement->bindValue(':admin_notes', $adminNotes !== '' ? $adminNotes : null, $adminNotes !== '' ? PDO::PARAM_STR : PDO::PARAM_NULL);
        $statement->bindValue(':workflow_status', $workflowStatus !== '' ? $workflowStatus : 'monitor', PDO::PARAM_STR);
        $statement->bindValue(':watch_live', $watchLive, PDO::PARAM_INT);
        $statement->bindValue(':follow_up_needed', $followUpNeeded, PDO::PARAM_INT);
        $statement->bindValue(':is_hidden', $isHidden, PDO::PARAM_INT);
        $statement->bindValue(':id', $entityId, PDO::PARAM_INT);
        $statement->execute();
    }
}

function newsroom_topics_index(int $limit = 40): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT "story" AS entity_type, topic_tags_json FROM stories WHERE publish_status = "published"
         UNION ALL
         SELECT "community_event" AS entity_type, topic_tags_json FROM community_events WHERE is_hidden = 0'
    );
    $statement->execute();

    $counts = [];
    foreach ($statement->fetchAll() as $row) {
        foreach (newsroom_parse_topics($row['topic_tags_json'] ?? null) as $topic) {
            $slug = $topic['slug'];
            if (!isset($counts[$slug])) {
                $counts[$slug] = ['slug' => $slug, 'label' => $topic['label'], 'count' => 0, 'story_count' => 0, 'event_count' => 0];
            }
            $counts[$slug]['count']++;
            if (($row['entity_type'] ?? '') === 'community_event') {
                $counts[$slug]['event_count']++;
            } else {
                $counts[$slug]['story_count']++;
            }
        }
    }

    usort($counts, static function (array $a, array $b): int {
        if ($a['count'] === $b['count']) {
            return strcmp($a['label'], $b['label']);
        }
        return $b['count'] <=> $a['count'];
    });

    return array_slice($counts, 0, $limit);
}

function newsroom_topic_bundle(string $slug, int $storyLimit = 20, int $eventLimit = 20): array
{
    if (!newsroom_db_available()) {
        return ['topic' => null, 'stories' => [], 'events' => []];
    }

    $normalizedNeedle = '%"slug":"' . str_replace(['%', '_'], ['\\%', '\\_'], $slug) . '"%';

    $storyStatement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.story_type,
            s.headline,
            s.dek,
            s.summary,
            s.topic_tags_json,
            s.published_at,
            s.display_date,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            COALESCE(gb.normalized_name, m.governing_body) AS body_name
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE s.publish_status = "published"
           AND REPLACE(CAST(s.topic_tags_json AS CHAR(4000)), " ", "") LIKE :needle
         ORDER BY COALESCE(s.sort_date, s.display_date, s.published_at) DESC
         LIMIT :limit'
    );
    $storyStatement->bindValue(':needle', $normalizedNeedle, PDO::PARAM_STR);
    $storyStatement->bindValue(':limit', $storyLimit, PDO::PARAM_INT);
    $storyStatement->execute();
    $stories = array_map('newsroom_recent_story_presenter', $storyStatement->fetchAll());

    $eventStatement = newsroom_db()->prepare(
        'SELECT
            ce.*,
            COALESCE(ce.score_override, ce.editorial_score) AS effective_score,
            COALESCE(NULLIF(ce.coverage_override, ""), ce.suggested_coverage_mode) AS effective_coverage_mode
         FROM community_events ce
         WHERE ce.is_hidden = 0
           AND REPLACE(CAST(ce.topic_tags_json AS CHAR(4000)), " ", "") LIKE :needle
         ORDER BY ce.starts_at ASC, COALESCE(ce.score_override, ce.editorial_score) DESC
         LIMIT :limit'
    );
    $eventStatement->bindValue(':needle', $normalizedNeedle, PDO::PARAM_STR);
    $eventStatement->bindValue(':limit', $eventLimit, PDO::PARAM_INT);
    $eventStatement->execute();
    $events = array_map('newsroom_community_event_presenter', $eventStatement->fetchAll());

    $topic = null;
    if ($stories) {
        foreach ($stories[0]['topics'] as $candidate) {
            if ($candidate['slug'] === $slug) {
                $topic = $candidate;
                break;
            }
        }
    }
    if ($topic === null && $events) {
        foreach ($events[0]['topics'] as $candidate) {
            if ($candidate['slug'] === $slug) {
                $topic = $candidate;
                break;
            }
        }
    }
    if ($topic === null) {
        foreach (newsroom_topics_index() as $candidate) {
            if ((string) ($candidate['slug'] ?? '') === $slug) {
                $topic = [
                    'slug' => (string) $candidate['slug'],
                    'label' => (string) $candidate['label'],
                ];
                break;
            }
        }
    }

    return ['topic' => $topic, 'stories' => $stories, 'events' => $events];
}

function newsroom_topic_story_groups(array $stories): array
{
    $leadId = isset($stories[0]['id']) ? (int) $stories[0]['id'] : 0;
    $upcoming = [];
    $recent = [];
    foreach ($stories as $story) {
        if ($leadId > 0 && (int) ($story['id'] ?? 0) === $leadId) {
            continue;
        }
        $type = (string) ($story['story_type'] ?? '');
        if ($type === 'meeting_preview') {
            $upcoming[] = $story;
        } else {
            $recent[] = $story;
        }
    }

    return [
        'upcoming' => array_slice($upcoming, 0, 4),
        'recent' => array_slice($recent, 0, 4),
        'all' => $stories,
    ];
}

function newsroom_topic_key_bodies(array $bundle, int $limit = 4): array
{
    $counts = [];
    foreach (($bundle['stories'] ?? []) as $story) {
        $body = trim((string) ($story['meta']['body_name'] ?? $story['body_name'] ?? ''));
        if ($body === '') {
            continue;
        }
        if (!isset($counts[$body])) {
            $counts[$body] = 0;
        }
        $counts[$body]++;
    }
    foreach (($bundle['events'] ?? []) as $event) {
        $body = trim((string) ($event['body_name'] ?? ''));
        if ($body === '') {
            continue;
        }
        if (!isset($counts[$body])) {
            $counts[$body] = 0;
        }
        $counts[$body]++;
    }

    arsort($counts);
    $result = [];
    foreach (array_slice($counts, 0, $limit, true) as $body => $count) {
        $result[] = ['body' => $body, 'count' => $count];
    }
    return $result;
}

function newsroom_topic_watch_text(array $topic, array $bundle): string
{
    $upcomingStories = newsroom_topic_story_groups($bundle['stories'] ?? [])['upcoming'];
    $upcomingEvents = array_slice($bundle['events'] ?? [], 0, 2);
    $parts = [];
    if ($upcomingStories) {
        $parts[] = count($upcomingStories) . ' upcoming meeting preview' . (count($upcomingStories) === 1 ? '' : 's');
    }
    if ($upcomingEvents) {
        $parts[] = count($upcomingEvents) . ' related event' . (count($upcomingEvents) === 1 ? '' : 's');
    }
    if (!$parts) {
        return 'There are no immediate upcoming items tagged to this beat, but the archive below tracks the ongoing issue.';
    }
    return 'What to watch next: ' . newsroom_sentence_list($parts) . '.';
}

function newsroom_homepage_priority_stories(int $limit = 4): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.story_type,
            s.public_label,
            s.byline_name,
            s.byline_title,
            s.headline,
            s.dek,
            s.summary,
            s.topic_tags_json,
            s.editorial_score,
            s.score_override,
            s.coverage_override,
            s.suggested_coverage_mode,
            s.workflow_status,
            s.watch_live,
            s.follow_up_needed,
            s.published_at,
            s.display_date,
            s.sort_date,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            COALESCE(gb.normalized_name, m.governing_body) AS body_name
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE s.publish_status = "published"
           AND (
                s.watch_live = 1
                OR s.follow_up_needed = 1
                OR COALESCE(s.score_override, s.editorial_score) >= 72
           )
         ORDER BY
            CASE WHEN s.watch_live = 1 THEN 0 ELSE 1 END,
            CASE WHEN s.follow_up_needed = 1 THEN 0 ELSE 1 END,
            COALESCE(s.score_override, s.editorial_score) DESC,
            COALESCE(s.sort_date, s.display_date, s.published_at) DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    return array_map('newsroom_recent_story_presenter', $statement->fetchAll());
}

function newsroom_topic_spotlights(int $limit = 6): array
{
    $topics = newsroom_topics_index($limit);
    foreach ($topics as &$topic) {
        $bundle = newsroom_topic_bundle((string) $topic['slug'], 1, 1);
        $topic['intro'] = newsroom_topic_intro_text((string) $topic['slug'], (string) $topic['label'], $bundle);
    }
    unset($topic);

    return array_slice($topics, 0, $limit);
}

function newsroom_archive_filter_options(): array
{
    $topics = newsroom_topics_index();
    $topicOptions = [];
    foreach ($topics as $topic) {
        $topicOptions[(string) $topic['slug']] = (string) $topic['label'];
    }
    asort($topicOptions);

    $bodyOptions = [];
    if (newsroom_db_available()) {
        $statement = newsroom_db()->query(
            'SELECT body_name FROM (
                SELECT COALESCE(gb.normalized_name, m.governing_body, "") AS body_name
                FROM stories s
                LEFT JOIN meetings m ON m.id = s.meeting_id
                LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
                WHERE s.publish_status = "published"
                UNION
                SELECT COALESCE(body_name, source_category, "") AS body_name
                FROM community_events
                WHERE is_hidden = 0
            ) options
            WHERE body_name <> ""
            ORDER BY body_name ASC'
        );
        foreach ($statement->fetchAll() as $row) {
            $bodyOptions[(string) $row['body_name']] = (string) $row['body_name'];
        }
    }

    return [
        'topics' => $topicOptions,
        'bodies' => $bodyOptions,
        'story_types' => [
            'meeting_preview' => 'Meeting preview',
            'minutes_recap' => 'Minutes recap',
            'community_event' => 'Community event',
        ],
    ];
}

function newsroom_archive_results(array $filters = [], int $limit = 100): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $query = trim((string) ($filters['q'] ?? ''));
    $entity = trim((string) ($filters['entity'] ?? 'all'));
    $topic = trim((string) ($filters['topic'] ?? 'all'));
    $body = trim((string) ($filters['body'] ?? 'all'));
    $storyType = trim((string) ($filters['story_type'] ?? 'all'));

    $sql = '
        SELECT * FROM (
            SELECT
                "story" AS entity_type,
                s.id AS entity_id,
                s.slug AS slug,
                s.headline AS title,
                s.story_type AS item_type,
                s.public_label,
                s.byline_name,
                s.byline_title,
                s.summary AS summary_text,
                COALESCE(gb.normalized_name, m.governing_body, "") AS body_name,
                COALESCE(s.sort_date, s.display_date, s.published_at) AS occurs_at,
                s.topic_tags_json,
                s.editorial_score,
                s.score_override,
                COALESCE(NULLIF(s.coverage_override, ""), s.suggested_coverage_mode) AS effective_coverage_mode
            FROM stories s
            LEFT JOIN meetings m ON m.id = s.meeting_id
            LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
            WHERE s.publish_status = "published"
            UNION ALL
            SELECT
                "community_event" AS entity_type,
                ce.id AS entity_id,
                ce.slug AS slug,
                ce.title AS title,
                "community_event" AS item_type,
                ce.public_label,
                ce.byline_name,
                ce.byline_title,
                ce.description AS summary_text,
                COALESCE(ce.body_name, ce.source_category, "") AS body_name,
                ce.starts_at AS occurs_at,
                ce.topic_tags_json,
                ce.editorial_score,
                ce.score_override,
                COALESCE(NULLIF(ce.coverage_override, ""), ce.suggested_coverage_mode) AS effective_coverage_mode
            FROM community_events ce
            WHERE ce.is_hidden = 0
        ) archive_items
        WHERE 1 = 1';

    $params = [];
    if ($entity !== 'all') {
        $sql .= ' AND entity_type = :entity';
        $params[':entity'] = $entity;
    }
    if ($storyType !== 'all') {
        if ($storyType === 'community_event') {
            $sql .= ' AND entity_type = "community_event"';
        } else {
            $sql .= ' AND item_type = :story_type';
            $params[':story_type'] = $storyType;
        }
    }
    if ($body !== 'all') {
        $sql .= ' AND body_name = :body';
        $params[':body'] = $body;
    }
    if ($topic !== 'all') {
        $sql .= ' AND REPLACE(CAST(topic_tags_json AS CHAR(4000)), " ", "") LIKE :topic';
        $params[':topic'] = '%"slug":"' . str_replace(['%', '_'], ['\\%', '\\_'], $topic) . '"%';
    }
    if ($query !== '') {
        $sql .= ' AND (title LIKE :query OR summary_text LIKE :query OR body_name LIKE :query)';
        $params[':query'] = '%' . $query . '%';
    }

    $sql .= ' ORDER BY occurs_at DESC, COALESCE(score_override, editorial_score) DESC LIMIT :limit';
    $statement = newsroom_db()->prepare($sql);
    foreach ($params as $key => $value) {
        $statement->bindValue($key, $value, PDO::PARAM_STR);
    }
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();

    $rows = $statement->fetchAll();
    foreach ($rows as &$row) {
        $row['effective_score'] = isset($row['score_override']) && $row['score_override'] !== null ? (int) $row['score_override'] : (int) $row['editorial_score'];
        $row['topics'] = newsroom_parse_topics($row['topic_tags_json'] ?? null);
        $rank = $row['effective_score'];
        $occursAt = strtotime((string) ($row['occurs_at'] ?? ''));
        if ($occursAt !== false) {
            $daysOld = max(0, (time() - $occursAt) / 86400);
            $rank += max(0, 24 - min(24, $daysOld * 1.1));
        }
        if ((string) ($row['entity_type'] ?? '') === 'story') {
            $rank += 12;
        }
        if ((string) ($row['item_type'] ?? '') === 'minutes_recap') {
            $rank += 6;
        }
        if ((string) ($row['item_type'] ?? '') === 'meeting_preview') {
            $rank += 4;
        }
        if ($query !== '') {
            $haystacks = [
                strtolower((string) ($row['title'] ?? '')),
                strtolower((string) ($row['summary_text'] ?? '')),
                strtolower((string) ($row['body_name'] ?? '')),
            ];
            $queryNeedle = strtolower($query);
            foreach ($haystacks as $haystack) {
                if ($haystack === '') {
                    continue;
                }
                if (strpos($haystack, $queryNeedle) !== false) {
                    $rank += 18;
                    break;
                }
            }
        }
        $row['editorial_rank'] = $rank;
        if ((string) $row['entity_type'] === 'story') {
            $row['public_url'] = newsroom_story_url_from_slug((string) $row['slug']);
            $row['label'] = newsroom_story_label($row);
            $row['byline'] = newsroom_story_byline($row);
        } else {
            $row['public_url'] = newsroom_community_event_url_from_parts((int) $row['entity_id'], (string) $row['slug']);
            $row['label'] = newsroom_event_label($row);
            $row['byline'] = newsroom_event_byline($row);
            $row['event_tier'] = newsroom_event_tier_data($row);
        }
    }
    unset($row);

    usort($rows, static function (array $a, array $b): int {
        $rankCompare = ((float) ($b['editorial_rank'] ?? 0)) <=> ((float) ($a['editorial_rank'] ?? 0));
        if ($rankCompare !== 0) {
            return $rankCompare;
        }
        return strcmp((string) ($b['occurs_at'] ?? ''), (string) ($a['occurs_at'] ?? ''));
    });

    return $rows;
}

function newsroom_follow_up_slug(string $title, int $id = 0): string
{
    $slug = strtolower(trim(preg_replace('/[^a-z0-9]+/i', '-', $title), '-'));
    if ($slug === '') {
        $slug = 'follow-up';
    }
    return $id > 0 ? $slug . '-' . $id : $slug;
}

function newsroom_upsert_follow_up_from_story(int $storyId, string $priority = 'normal'): ?int
{
    if (!newsroom_db_available() || $storyId <= 0) {
        return null;
    }

    $check = newsroom_db()->prepare(
        'SELECT id FROM follow_up_items
         WHERE source_story_id = :story_id
           AND workflow_status <> "done"
         ORDER BY id DESC
         LIMIT 1'
    );
    $check->execute([':story_id' => $storyId]);
    $existing = $check->fetch();
    if ($existing) {
        return (int) $existing['id'];
    }

    $story = newsroom_recap_queue_item($storyId);
    if (!$story) {
        $storyStatement = newsroom_db()->prepare(
            'SELECT id, slug, headline, topic_tags_json FROM stories WHERE id = :id LIMIT 1'
        );
        $storyStatement->execute([':id' => $storyId]);
        $story = $storyStatement->fetch() ?: null;
    }
    if (!$story) {
        return null;
    }

    $title = trim((string) ($story['headline'] ?? '')) . ' follow-up';
    $topicTagsJson = isset($story['topic_tags_json']) ? (string) $story['topic_tags_json'] : json_encode($story['topics'] ?? []);

    $insert = newsroom_db()->prepare(
        'INSERT INTO follow_up_items (
            source_story_id,
            source_story_slug,
            title,
            slug,
            topic_tags_json,
            workflow_status,
            priority,
            notes,
            draft_body
        ) VALUES (
            :source_story_id,
            :source_story_slug,
            :title,
            :slug,
            :topic_tags_json,
            "draft",
            :priority,
            :notes,
            :draft_body
        )'
    );
    $insert->execute([
        ':source_story_id' => $storyId,
        ':source_story_slug' => (string) ($story['slug'] ?? ''),
        ':title' => $title,
        ':slug' => newsroom_follow_up_slug($title),
        ':topic_tags_json' => $topicTagsJson ?: json_encode([]),
        ':priority' => $priority,
        ':notes' => 'Generated from recap workspace.',
        ':draft_body' => "Follow-up angle\n- What changed after the meeting?\n- Who is affected?\n- What comes next?\n",
    ]);

    return (int) newsroom_db()->lastInsertId();
}

function newsroom_follow_up_items(int $limit = 60): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            fu.*,
            s.headline AS source_headline,
            s.slug AS source_slug,
            s.summary AS source_summary,
            s.workflow_status AS source_workflow_status
         FROM follow_up_items fu
         INNER JOIN stories s ON s.id = fu.source_story_id
         ORDER BY
            CASE fu.workflow_status
                WHEN "watch_live" THEN 0
                WHEN "assigned" THEN 1
                WHEN "draft" THEN 2
                WHEN "done" THEN 4
                ELSE 3
            END,
            CASE fu.priority
                WHEN "must_cover" THEN 0
                WHEN "high" THEN 1
                ELSE 2
            END,
            fu.updated_at DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();
    $rows = $statement->fetchAll();
    foreach ($rows as &$row) {
        $row['public_url'] = newsroom_story_url_from_slug((string) ($row['source_slug'] ?? ''));
        $row['topics'] = newsroom_parse_topics($row['topic_tags_json'] ?? null);
    }
    unset($row);

    return $rows;
}

function newsroom_follow_up_item(int $id): ?array
{
    if (!newsroom_db_available() || $id <= 0) {
        return null;
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            fu.*,
            s.headline AS source_headline,
            s.slug AS source_slug,
            s.summary AS source_summary,
            s.workflow_status AS source_workflow_status
         FROM follow_up_items fu
         INNER JOIN stories s ON s.id = fu.source_story_id
         WHERE fu.id = :id
         LIMIT 1'
    );
    $statement->execute([':id' => $id]);
    $row = $statement->fetch();
    if (!$row) {
        return null;
    }
    $row['public_url'] = newsroom_story_url_from_slug((string) ($row['source_slug'] ?? ''));
    $row['topics'] = newsroom_parse_topics($row['topic_tags_json'] ?? null);
    return $row;
}

function newsroom_save_follow_up_item(int $id, array $payload): void
{
    if (!newsroom_db_available() || $id <= 0) {
        return;
    }

    $title = trim((string) ($payload['title'] ?? ''));
    $status = trim((string) ($payload['workflow_status'] ?? 'draft'));
    $priority = trim((string) ($payload['priority'] ?? 'normal'));
    $notes = trim((string) ($payload['notes'] ?? ''));
    $draftBody = trim((string) ($payload['draft_body'] ?? ''));

    $statement = newsroom_db()->prepare(
        'UPDATE follow_up_items
         SET title = :title,
             slug = :slug,
             workflow_status = :workflow_status,
             priority = :priority,
             notes = :notes,
             draft_body = :draft_body
         WHERE id = :id'
    );
    $statement->execute([
        ':title' => $title !== '' ? $title : 'Follow-up story',
        ':slug' => newsroom_follow_up_slug($title !== '' ? $title : 'Follow-up story', $id),
        ':workflow_status' => $status !== '' ? $status : 'draft',
        ':priority' => $priority !== '' ? $priority : 'normal',
        ':notes' => $notes !== '' ? $notes : null,
        ':draft_body' => $draftBody !== '' ? $draftBody : null,
        ':id' => $id,
    ]);
}

function newsroom_apply_recap_action(int $storyId, string $action): ?int
{
    if (!newsroom_db_available() || $storyId <= 0) {
        return null;
    }

    switch ($action) {
        case 'mark_done':
            newsroom_db()->prepare(
                'UPDATE stories
                 SET workflow_status = "done", follow_up_needed = 0
                 WHERE id = :id'
            )->execute([':id' => $storyId]);
            return null;
        case 'minutes_reconciled':
            newsroom_db()->prepare(
                'UPDATE stories
                 SET workflow_status = "done"
                 WHERE id = :id'
            )->execute([':id' => $storyId]);
            return null;
        case 'queue_watch':
            newsroom_db()->prepare(
                'UPDATE stories
                 SET watch_live = 1,
                     follow_up_needed = 1,
                     workflow_status = "follow_up_story"
                 WHERE id = :id'
            )->execute([':id' => $storyId]);
            return newsroom_upsert_follow_up_from_story($storyId, 'must_cover');
        case 'create_follow_up':
            newsroom_db()->prepare(
                'UPDATE stories
                 SET follow_up_needed = 1,
                     workflow_status = "follow_up_story"
                 WHERE id = :id'
            )->execute([':id' => $storyId]);
            return newsroom_upsert_follow_up_from_story($storyId, 'high');
        default:
            return null;
    }
}

function newsroom_live_watch_queue(int $limit = 40): array
{
    if (!newsroom_db_available()) {
        return [];
    }

    $statement = newsroom_db()->prepare(
        'SELECT
            s.id,
            s.slug,
            s.headline,
            s.summary,
            s.story_type,
            s.public_label,
            s.byline_name,
            s.byline_title,
            s.live_prep_notes,
            s.workflow_status,
            s.watch_live,
            s.follow_up_needed,
            m.meeting_date,
            TIME_FORMAT(m.meeting_time, "%H:%i:%s") AS meeting_time,
            m.location_name,
            COALESCE(gb.normalized_name, m.governing_body) AS body_name,
            (
                SELECT COALESCE(d.document_url, ma.source_url)
                FROM meeting_artifacts ma
                LEFT JOIN documents d ON d.id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_url,
            (
                SELECT de.structured_json
                FROM meeting_artifacts ma
                INNER JOIN (
                    SELECT de1.*
                    FROM document_extractions de1
                    INNER JOIN (
                        SELECT document_id, MAX(id) AS max_id
                        FROM document_extractions
                        GROUP BY document_id
                    ) latest_extraction ON latest_extraction.max_id = de1.id
                ) de ON de.document_id = ma.document_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_structured_json,
            (
                SELECT si.raw_meta_json
                FROM meeting_artifacts ma
                INNER JOIN source_items si ON si.id = ma.source_item_id
                WHERE ma.meeting_id = s.meeting_id AND ma.artifact_type = "agenda"
                ORDER BY ma.is_primary DESC, ma.posted_at DESC, ma.id DESC
                LIMIT 1
            ) AS agenda_source_meta_json
         FROM stories s
         LEFT JOIN meetings m ON m.id = s.meeting_id
         LEFT JOIN governing_bodies gb ON gb.id = s.governing_body_id
         WHERE s.publish_status = "published"
           AND s.watch_live = 1
         ORDER BY m.meeting_date ASC, m.meeting_time ASC, s.id DESC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', $limit, PDO::PARAM_INT);
    $statement->execute();
    $rows = array_map('newsroom_recent_story_presenter', $statement->fetchAll());
    foreach ($rows as &$row) {
        $row['live_prep'] = newsroom_live_watch_prep($row);
    }
    unset($row);
    return $rows;
}

function newsroom_live_watch_prep(array $story): array
{
    $remote = $story['meta']['remote'] ?? [];
    $location = trim((string) ($story['meta']['location_name'] ?? ''));
    $sourceType = 'Official website';
    if (!empty($remote['join_url'])) {
        $sourceType = 'Zoom';
    } elseif (!empty($story['meta']['agenda_url']) && stripos((string) $story['meta']['agenda_url'], 'youtube') !== false) {
        $sourceType = 'YouTube';
    }

    $checks = [
        'Verify the meeting start time and any room or venue change.',
        'Open the agenda before the meeting starts and note the top issues.',
        'Watch for motions, votes, continuances, and explicit next steps.',
    ];
    if (!empty($remote['join_url'])) {
        $checks[] = 'Join the public Zoom a few minutes early and confirm the posted ID and passcode work.';
    }
    if ($location !== '') {
        $checks[] = 'Confirm whether the meeting is hybrid and whether the posted location still matches the agenda.';
    }

    return [
        'source_type' => $sourceType,
        'checklist' => $checks,
    ];
}

function newsroom_save_live_prep_notes(string $entityType, int $id, string $notes): void
{
    if (!newsroom_db_available() || $id <= 0) {
        return;
    }

    if ($entityType === 'story') {
        $statement = newsroom_db()->prepare('UPDATE stories SET live_prep_notes = :notes WHERE id = :id');
        $statement->execute([':notes' => trim($notes) !== '' ? trim($notes) : null, ':id' => $id]);
        return;
    }

    if ($entityType === 'community_event') {
        $statement = newsroom_db()->prepare('UPDATE community_events SET live_prep_notes = :notes WHERE id = :id');
        $statement->execute([':notes' => trim($notes) !== '' ? trim($notes) : null, ':id' => $id]);
    }
}
