<?php

declare(strict_types=1);

function newsroom_local_config(): array
{
    static $config = null;

    if (is_array($config)) {
        return $config;
    }

    $configPath = __DIR__ . '/config.local.php';
    if (!file_exists($configPath)) {
        $config = [];
        return $config;
    }

    $loaded = require $configPath;
    $config = is_array($loaded) ? $loaded : [];

    return $config;
}

function newsroom_env(string $key, ?string $default = null): ?string
{
    $localConfig = newsroom_local_config();
    if (array_key_exists($key, $localConfig) && $localConfig[$key] !== '') {
        return (string) $localConfig[$key];
    }

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
