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

$config = newsroom_config();
$requestPath = trim((string) parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH), '/');
$slug = isset($_GET['slug']) ? (string) $_GET['slug'] : '';
if ($slug === '' && strpos($requestPath, 'topics/') === 0) {
    $slug = rawurldecode(substr($requestPath, strlen('topics/')));
}

$indexMode = $slug === '';
$topics = $indexMode ? newsroom_topics_index() : [];
$bundle = $indexMode ? ['topic' => null, 'stories' => [], 'events' => []] : newsroom_topic_bundle($slug);
$topic = $bundle['topic'] ?? null;
$overview = (!$indexMode && $topic) ? newsroom_topic_intro_text((string) $topic['slug'], (string) $topic['label'], $bundle) : '';
$storyGroups = (!$indexMode && $topic) ? newsroom_topic_story_groups($bundle['stories']) : ['upcoming' => [], 'recent' => [], 'all' => []];
$keyBodies = (!$indexMode && $topic) ? newsroom_topic_key_bodies($bundle) : [];
$watchText = (!$indexMode && $topic) ? newsroom_topic_watch_text($topic, $bundle) : '';

http_response_code($indexMode || $topic ? 200 : 404);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($indexMode ? 'Topics' : (($topic['label'] ?? 'Topic') . ' | ' . $config['site_name'])) ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Datatype:wght@400;500;700&family=Fira+Code:wght@400;500;700&family=Manufacturing+Consent&family=Merriweather:wght@300;400;700&family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<div class="page">
    <header class="masthead">
        <div class="masthead__rail">
            <div class="masthead__meta">Wareham, Massachusetts</div>
            <div class="masthead__meta"><?= date('l, F j, Y') ?></div>
        </div>
        <div class="masthead__core">
            <h1 class="masthead__title"><a href="/" class="masthead__home-link">The Wareham Times</a></h1>
            <div class="masthead__tagline">Coverage organized by issue, beat, and recurring local theme.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
        <a href="/opinion">Opinion</a>
        <a href="/bodies">Bodies</a>
        <a href="/archive">Archive</a>
    </nav>

    <?php if ($indexMode): ?>
        <h2 class="section-heading">Topics</h2>
        <p class="section-intro">Browse coverage by the recurring issues that keep surfacing in Wareham meetings, public records, and community-calendar items.</p>
        <section class="story-masonry">
            <?php foreach ($topics as $topicItem): ?>
                <article class="story-tease">
                    <h3><a href="<?= htmlspecialchars(newsroom_topic_url((string) $topicItem['slug'])) ?>"><?= htmlspecialchars((string) $topicItem['label']) ?></a></h3>
                    <p><?= htmlspecialchars(newsroom_topic_intro_text((string) $topicItem['slug'], (string) $topicItem['label'])) ?></p>
                    <p><?= htmlspecialchars((string) $topicItem['count']) ?> tagged items, including <?= htmlspecialchars((string) ($topicItem['story_count'] ?? 0)) ?> stories and <?= htmlspecialchars((string) ($topicItem['event_count'] ?? 0)) ?> events.</p>
                </article>
            <?php endforeach; ?>
        </section>
    <?php elseif ($topic): ?>
        <h2 class="section-heading"><?= htmlspecialchars((string) $topic['label']) ?></h2>
        <p class="section-intro"><?= htmlspecialchars($overview) ?></p>
        <section class="story-masonry story-masonry--tight">
            <article class="story-tease">
                <h3>What To Watch</h3>
                <p><?= htmlspecialchars($watchText) ?></p>
            </article>
            <article class="story-tease">
                <h3>At a Glance</h3>
                <p><?= htmlspecialchars((string) count($bundle['stories'])) ?> stories and <?= htmlspecialchars((string) count($bundle['events'])) ?> related events are currently tagged to this beat.</p>
            </article>
            <article class="story-tease">
                <h3>Recurring Bodies</h3>
                <?php if ($keyBodies): ?>
                    <p><?= htmlspecialchars(newsroom_sentence_list(array_map(static function (array $item): string { return $item['body']; }, $keyBodies))) ?></p>
                <?php else: ?>
                    <p class="empty-state">No recurring public body has surfaced clearly for this topic yet.</p>
                <?php endif; ?>
            </article>
        </section>
        <section class="front-page">
            <section class="lead-story">
                <div class="eyebrow">Lead Coverage</div>
                <?php if ($storyGroups['all']): ?>
                    <?php $lead = $storyGroups['all'][0]; ?>
                    <h2><a href="<?= htmlspecialchars(newsroom_story_url($lead)) ?>"><?= htmlspecialchars((string) $lead['headline']) ?></a></h2>
                    <div class="story-meta-row story-meta-row--compact">
                        <span class="signal-pill"><?= htmlspecialchars((string) $lead['label']) ?></span>
                        <span class="signal-pill" style="<?= htmlspecialchars(sprintf('--pill-bg:%s; --pill-fg:%s; --pill-border:%s;', $lead['meta']['body_signal']['bg'], $lead['meta']['body_signal']['fg'], $lead['meta']['body_signal']['border'])) ?>"><?= htmlspecialchars((string) $lead['meta']['body_name']) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars((string) $lead['meta']['meeting_datetime']) ?></span>
                    </div>
                    <p class="lead-story__summary"><?= htmlspecialchars((string) ($lead['meta']['summary_text'] ?? $lead['summary'] ?? '')) ?></p>
                <?php else: ?>
                    <p class="empty-state">No published stories are currently tagged to this topic.</p>
                <?php endif; ?>
            </section>
            <section class="news-rail">
                <h2 class="section-heading section-heading--tight">Upcoming Coverage</h2>
                <?php foreach ($storyGroups['upcoming'] as $story): ?>
                    <article class="rail-story">
                        <h3><a href="<?= htmlspecialchars(newsroom_story_url($story)) ?>"><?= htmlspecialchars((string) $story['headline']) ?></a></h3>
                        <div class="story-meta-row story-meta-row--compact">
                            <span class="signal-pill"><?= htmlspecialchars((string) $story['label']) ?></span>
                            <span class="signal-pill" style="<?= htmlspecialchars(sprintf('--pill-bg:%s; --pill-fg:%s; --pill-border:%s;', $story['meta']['body_signal']['bg'], $story['meta']['body_signal']['fg'], $story['meta']['body_signal']['border'])) ?>"><?= htmlspecialchars((string) $story['meta']['body_name']) ?></span>
                            <span class="story-card__meta"><?= htmlspecialchars((string) $story['meta']['meeting_datetime']) ?></span>
                        </div>
                        <p><?= htmlspecialchars((string) ($story['meta']['summary_text'] ?? $story['summary'] ?? '')) ?></p>
                    </article>
                <?php endforeach; ?>
                <?php if (!$storyGroups['upcoming']): ?>
                    <p class="empty-state">No upcoming preview stories are currently tagged to this topic.</p>
                <?php endif; ?>
            </section>
            <aside class="agenda-ledger">
                <h2 class="section-heading section-heading--tight">Upcoming Events</h2>
                <?php if ($bundle['events']): ?>
                    <?php foreach ($bundle['events'] as $event): ?>
                        <article class="event-item">
                            <div class="story-meta-row story-meta-row--compact">
                                <span class="signal-pill"><?= htmlspecialchars((string) ($event['label'] ?? 'Community Event')) ?></span>
                            </div>
                            <strong><a href="<?= htmlspecialchars((string) $event['local_url']) ?>"><?= htmlspecialchars((string) $event['title']) ?></a></strong>
                            <p class="event-item__datetime"><?= htmlspecialchars(date('M. j, Y g:i A', strtotime((string) $event['starts_at']))) ?></p>
                            <?php if (!empty($event['location_name'])): ?>
                                <p><?= htmlspecialchars((string) $event['location_name']) ?></p>
                            <?php endif; ?>
                            <?php if (!empty($event['description'])): ?>
                                <p class="event-item__summary"><?= htmlspecialchars(newsroom_truncate_text((string) $event['description'], 180)) ?></p>
                            <?php endif; ?>
                        </article>
                    <?php endforeach; ?>
                <?php else: ?>
                    <p class="empty-state">No upcoming community events are currently tagged to this topic.</p>
                <?php endif; ?>
            </aside>
        </section>
        <h2 class="section-heading">Recent Stories</h2>
        <section class="story-masonry">
            <?php foreach ($storyGroups['recent'] as $story): ?>
                <article class="story-tease">
                    <h3><a href="<?= htmlspecialchars(newsroom_story_url($story)) ?>"><?= htmlspecialchars((string) $story['headline']) ?></a></h3>
                    <div class="story-meta-row story-meta-row--compact">
                        <span class="signal-pill"><?= htmlspecialchars((string) $story['label']) ?></span>
                        <span class="signal-pill" style="<?= htmlspecialchars(sprintf('--pill-bg:%s; --pill-fg:%s; --pill-border:%s;', $story['meta']['body_signal']['bg'], $story['meta']['body_signal']['fg'], $story['meta']['body_signal']['border'])) ?>"><?= htmlspecialchars((string) $story['meta']['body_name']) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars((string) $story['meta']['meeting_datetime']) ?></span>
                    </div>
                    <p><?= htmlspecialchars((string) ($story['meta']['summary_text'] ?? $story['summary'] ?? '')) ?></p>
                </article>
            <?php endforeach; ?>
            <?php if (!$storyGroups['recent']): ?>
                <article class="story-tease">
                    <h3>No recent recap or follow-through stories yet</h3>
                    <p class="empty-state">This beat is currently dominated by advance coverage and upcoming items.</p>
                </article>
            <?php endif; ?>
        </section>
    <?php else: ?>
        <h2 class="section-heading">Topic not found</h2>
        <p class="empty-state">No stories or events were found for that topic.</p>
    <?php endif; ?>
</div>
</body>
</html>
