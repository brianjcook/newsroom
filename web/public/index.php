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
$stories = newsroom_latest_stories();
$events = newsroom_upcoming_events();
$communityEvents = newsroom_storyworthy_community_events(4);
$topics = newsroom_topics_index(6);
$lead = $stories[0] ?? null;
$secondaryStories = array_slice($stories, 1);

function newsroom_pill_style(array $signal): string
{
    return sprintf(
        '--pill-bg:%s; --pill-fg:%s; --pill-border:%s;',
        $signal['bg'] ?? '#ece4d8',
        $signal['fg'] ?? '#47362b',
        $signal['border'] ?? '#a98767'
    );
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= htmlspecialchars($config['site_name']) ?></title>
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
            <h1 class="masthead__title">The Wareham Times</h1>
            <div class="masthead__tagline">Civic reporting, meeting coverage, and the public record.</div>
        </div>
    </header>

    <nav class="nav">
        <a href="/">Home</a>
        <a href="/calendar">Calendar</a>
        <a href="/topics">Topics</a>
    </nav>

    <section class="front-page">
        <article class="lead-story">
            <div class="eyebrow">Lead Story</div>
            <?php if ($lead): ?>
                <h2><a href="<?= htmlspecialchars(newsroom_story_url($lead)) ?>"><?= htmlspecialchars($lead['headline']) ?></a></h2>
                <div class="story-meta-row">
                    <span class="signal-pill" style="<?= htmlspecialchars(newsroom_pill_style($lead['meta']['body_signal'])) ?>"><?= htmlspecialchars($lead['meta']['body_name']) ?></span>
                    <span class="story-meta-row__date"><?= htmlspecialchars($lead['meta']['meeting_datetime']) ?></span>
                </div>
                <p class="lead-story__summary"><?= htmlspecialchars((string) ($lead['meta']['summary_text'] ?? $lead['summary'] ?? $lead['dek'] ?? '')) ?></p>
                <div class="story-link-row">
                    <?php if (!empty($lead['meta']['agenda_url'])): ?>
                        <a href="<?= htmlspecialchars($lead['meta']['agenda_url']) ?>">Agenda</a>
                    <?php elseif (!empty($lead['meta']['minutes_url'])): ?>
                        <a href="<?= htmlspecialchars($lead['meta']['minutes_url']) ?>">Minutes</a>
                    <?php endif; ?>
                </div>
            <?php else: ?>
                <h2>Newsroom scaffold is live.</h2>
                <p class="empty-state">Published stories will appear here once the worker discovers and processes Wareham source material.</p>
            <?php endif; ?>
        </article>

        <section class="news-rail">
            <h2 class="section-heading section-heading--tight">Latest Coverage</h2>
            <?php if ($secondaryStories): ?>
                <?php foreach (array_slice($secondaryStories, 0, 3) as $story): ?>
                    <article class="rail-story">
                        <h3><a href="<?= htmlspecialchars(newsroom_story_url($story)) ?>"><?= htmlspecialchars($story['headline']) ?></a></h3>
                        <div class="story-meta-row story-meta-row--compact">
                            <span class="signal-pill" style="<?= htmlspecialchars(newsroom_pill_style($story['meta']['body_signal'])) ?>"><?= htmlspecialchars($story['meta']['body_name']) ?></span>
                            <span class="story-card__meta"><?= htmlspecialchars($story['meta']['meeting_datetime']) ?></span>
                        </div>
                        <p><?= htmlspecialchars((string) ($story['meta']['summary_text'] ?? $story['summary'] ?? $story['dek'] ?? '')) ?></p>
                    </article>
                <?php endforeach; ?>
            <?php else: ?>
                <article class="rail-story">
                    <div class="story-card__meta">Status</div>
                    <h3>Initial site scaffold</h3>
                    <p>The public site is connected to the database schema and ready for published stories and official meeting listings.</p>
                </article>
            <?php endif; ?>
        </section>

        <aside class="agenda-ledger">
            <h2 class="section-heading section-heading--tight">Upcoming Meetings</h2>
            <div class="event-list">
                <?php if ($events): ?>
                    <?php foreach ($events as $event): ?>
                        <article class="event-item">
                            <strong><?= htmlspecialchars($event['title']) ?></strong>
                            <div class="story-meta-row story-meta-row--compact">
                                <span class="signal-pill" style="<?= htmlspecialchars(newsroom_pill_style($event['body_signal'])) ?>"><?= htmlspecialchars($event['body_name']) ?></span>
                            </div>
                            <p class="event-item__datetime"><?= htmlspecialchars(date('M. j, Y g:i A', strtotime((string) $event['starts_at']))) ?></p>
                            <?php if (!empty($event['location_name'])): ?>
                                <p><?= htmlspecialchars((string) $event['location_name']) ?></p>
                            <?php endif; ?>
                            <?php if (!empty($event['remote']['join_url'])): ?>
                                <p><a href="<?= htmlspecialchars((string) $event['remote']['join_url']) ?>">Zoom</a><?php if (!empty($event['remote']['webinar_id'])): ?> · ID <?= htmlspecialchars((string) $event['remote']['webinar_id']) ?><?php endif; ?></p>
                            <?php endif; ?>
                            <?php if (!empty($event['summary_text'])): ?>
                                <p class="event-item__summary"><?= htmlspecialchars((string) $event['summary_text']) ?></p>
                            <?php endif; ?>
                            <?php if (!empty($event['agenda_url'])): ?>
                                <p><a href="<?= htmlspecialchars((string) $event['agenda_url']) ?>">Agenda</a></p>
                            <?php endif; ?>
                        </article>
                    <?php endforeach; ?>
                <?php else: ?>
                    <p class="empty-state">No calendar entries yet.</p>
                <?php endif; ?>
            </div>
        </aside>
    </section>

    <h2 class="section-heading">More Meeting Coverage</h2>
    <p class="section-intro">Recent automated coverage drawn from Wareham agendas, minutes, and other town meeting records.</p>
    <section class="story-masonry">
        <?php if ($secondaryStories): ?>
            <?php foreach ($secondaryStories as $story): ?>
                <article class="story-tease">
                    <h3><a href="<?= htmlspecialchars(newsroom_story_url($story)) ?>"><?= htmlspecialchars($story['headline']) ?></a></h3>
                    <div class="story-meta-row story-meta-row--compact">
                        <span class="signal-pill" style="<?= htmlspecialchars(newsroom_pill_style($story['meta']['body_signal'])) ?>"><?= htmlspecialchars($story['meta']['body_name']) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars($story['meta']['meeting_datetime']) ?></span>
                    </div>
                    <p><?= htmlspecialchars((string) ($story['meta']['summary_text'] ?? $story['summary'] ?? $story['dek'] ?? '')) ?></p>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="story-tease">
                <div class="story-card__meta">Status</div>
                <h3>Initial site scaffold</h3>
                <p>The public site is connected to the database schema and ready for published stories and official meeting listings.</p>
            </article>
        <?php endif; ?>
    </section>

    <h2 class="section-heading">Around Town</h2>
    <p class="section-intro">Events from the Wareham public calendar that the editorial desk currently ranks as especially newsworthy or broadly interesting.</p>
    <section class="story-masonry story-masonry--events">
        <?php if ($communityEvents): ?>
            <?php foreach ($communityEvents as $event): ?>
                <article class="story-tease">
                    <h3><a href="<?= htmlspecialchars($event['local_url']) ?>"><?= htmlspecialchars($event['title']) ?></a></h3>
                    <div class="story-meta-row story-meta-row--compact">
                        <span class="signal-pill" style="<?= htmlspecialchars(newsroom_pill_style($event['body_signal'])) ?>"><?= htmlspecialchars($event['source_type'] === 'community_event' ? 'Community Event' : ucwords(str_replace('_', ' ', $event['source_type']))) ?></span>
                        <span class="story-card__meta"><?= htmlspecialchars(date('M. j, Y g:i A', strtotime((string) $event['starts_at']))) ?></span>
                    </div>
                    <?php if (!empty($event['location_name'])): ?>
                        <p><?= htmlspecialchars((string) $event['location_name']) ?></p>
                    <?php endif; ?>
                    <?php if (!empty($event['description'])): ?>
                        <p><?= htmlspecialchars((string) $event['description']) ?></p>
                    <?php endif; ?>
                    <p><a href="<?= htmlspecialchars((string) $event['source_url']) ?>" target="_blank" rel="noopener noreferrer">Official listing</a></p>
                </article>
            <?php endforeach; ?>
        <?php else: ?>
            <article class="story-tease">
                <h3>No community events ranked yet</h3>
                <p class="empty-state">Story-worthy public-calendar events will appear here once the editorial scoring sync has run.</p>
            </article>
        <?php endif; ?>
    </section>

    <h2 class="section-heading">Topics</h2>
    <section class="story-masonry">
        <?php foreach ($topics as $topic): ?>
            <article class="story-tease">
                <h3><a href="<?= htmlspecialchars(newsroom_topic_url((string) $topic['slug'])) ?>"><?= htmlspecialchars((string) $topic['label']) ?></a></h3>
                <p><?= htmlspecialchars((string) $topic['count']) ?> tagged items, including <?= htmlspecialchars((string) ($topic['story_count'] ?? 0)) ?> stories and <?= htmlspecialchars((string) ($topic['event_count'] ?? 0)) ?> events.</p>
            </article>
        <?php endforeach; ?>
    </section>
</div>
</body>
</html>
