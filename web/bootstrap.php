<?php

declare(strict_types=1);

function newsroom_env(string $key, ?string $default = null): ?string
{
    $value = getenv($key);

    if ($value === false || $value === '') {
        return $default;
    }

    return $value;
}

function newsroom_config(): array
{
    return [
        'site_name' => newsroom_env('NEWSROOM_SITE_NAME', 'Wareham Newsroom'),
        'site_url' => newsroom_env('NEWSROOM_SITE_URL', ''),
        'db' => [
            'host' => newsroom_env('NEWSROOM_DB_HOST', 'localhost'),
            'port' => newsroom_env('NEWSROOM_DB_PORT', '3306'),
            'name' => newsroom_env('NEWSROOM_DB_NAME', 'bricoo10_newsroom'),
            'user' => newsroom_env('NEWSROOM_DB_USER', ''),
            'password' => newsroom_env('NEWSROOM_DB_PASSWORD', ''),
            'charset' => 'utf8mb4',
        ],
    ];
}
