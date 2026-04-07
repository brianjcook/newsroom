INSERT INTO sources (
    name,
    slug,
    source_type,
    base_url,
    list_url,
    parser_key,
    poll_frequency,
    is_active
)
SELECT
    'Wareham Police Logs',
    'wareham-police-logs',
    'official_documents',
    'https://www.wareham.ma.us',
    'https://www.wareham.ma.us/DocumentCenter/Index/316',
    'wareham_police_logs',
    'daily',
    1
WHERE NOT EXISTS (
    SELECT 1 FROM sources WHERE slug = 'wareham-police-logs'
);

INSERT INTO sources (
    name,
    slug,
    source_type,
    base_url,
    list_url,
    parser_key,
    poll_frequency,
    is_active
)
SELECT
    'Buzzards Bay Coalition News',
    'buzzards-bay-coalition-news',
    'external_news',
    'https://www.savebuzzardsbay.org',
    'https://www.savebuzzardsbay.org/news/',
    'buzzards_bay_coalition_news',
    'daily',
    1
WHERE NOT EXISTS (
    SELECT 1 FROM sources WHERE slug = 'buzzards-bay-coalition-news'
);

INSERT INTO sources (
    name,
    slug,
    source_type,
    base_url,
    list_url,
    parser_key,
    poll_frequency,
    is_active
)
SELECT
    'Discover Wareham Events',
    'discover-wareham-events',
    'community_events',
    'https://discover-wareham.com',
    'https://discover-wareham.com/?post_type=tribe_events',
    'discover_wareham_events',
    'daily',
    1
WHERE NOT EXISTS (
    SELECT 1 FROM sources WHERE slug = 'discover-wareham-events'
);
