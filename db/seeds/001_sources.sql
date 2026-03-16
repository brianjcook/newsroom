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
VALUES (
    'Wareham AgendaCenter',
    'wareham-agenda-center',
    'agenda_center_listing',
    'https://www.wareham.gov',
    'https://www.wareham.gov/AgendaCenter',
    'wareham_agenda_center',
    'daily',
    1
)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    list_url = VALUES(list_url),
    parser_key = VALUES(parser_key),
    poll_frequency = VALUES(poll_frequency),
    is_active = VALUES(is_active);
