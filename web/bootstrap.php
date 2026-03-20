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
        'editorial_auth' => [
            'user' => newsroom_env('NEWSROOM_EDITORIAL_USER', ''),
            'password' => newsroom_env('NEWSROOM_EDITORIAL_PASSWORD', ''),
            'session_days' => (int) newsroom_env('NEWSROOM_EDITORIAL_SESSION_DAYS', '365'),
        ],
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

function newsroom_require_basic_auth(string $realm = 'Restricted Area'): void
{
    $config = newsroom_config();
    $expectedUser = (string) ($config['editorial_auth']['user'] ?? '');
    $expectedPassword = (string) ($config['editorial_auth']['password'] ?? '');

    if ($expectedUser === '' || $expectedPassword === '') {
        return;
    }

    $providedUser = isset($_SERVER['PHP_AUTH_USER']) ? (string) $_SERVER['PHP_AUTH_USER'] : '';
    $providedPassword = isset($_SERVER['PHP_AUTH_PW']) ? (string) $_SERVER['PHP_AUTH_PW'] : '';

    if ($providedUser === '' && $providedPassword === '') {
        $authorization = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '';
        if (is_string($authorization) && stripos($authorization, 'basic ') === 0) {
            $decoded = base64_decode(substr($authorization, 6), true);
            if (is_string($decoded) && strpos($decoded, ':') !== false) {
                [$providedUser, $providedPassword] = explode(':', $decoded, 2);
            }
        }
    }

    if (hash_equals($expectedUser, $providedUser) && hash_equals($expectedPassword, $providedPassword)) {
        return;
    }

    header('WWW-Authenticate: Basic realm="' . addslashes($realm) . '"');
    header('HTTP/1.1 401 Unauthorized');
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Authentication required.';
    exit;
}

function newsroom_start_session(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }

    $config = newsroom_config();
    $lifetimeDays = max(1, (int) ($config['editorial_auth']['session_days'] ?? 30));
    $lifetime = $lifetimeDays * 86400;

    session_set_cookie_params([
        'lifetime' => $lifetime,
        'path' => '/',
        'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off',
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
    session_name('newsroomdesk');
    session_start();
}

function newsroom_render_editorial_login(string $message = ''): void
{
    $config = newsroom_config();
    http_response_code(401);
    header('Content-Type: text/html; charset=utf-8');
    ?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Editorial Login | <?= htmlspecialchars($config['site_name']) ?></title>
    <style>
        body { margin: 0; background: #f4efe5; color: #171412; font-family: Georgia, serif; }
        .login-shell { max-width: 420px; margin: 80px auto; padding: 28px; background: #fbf7ef; border-top: 6px solid #1f1a16; border-bottom: 3px solid #1f1a16; }
        h1 { margin: 0 0 12px; font-size: 2rem; line-height: 1; }
        p { line-height: 1.6; }
        label { display: block; margin-top: 14px; font-family: monospace; font-size: 0.8rem; letter-spacing: 0.05em; text-transform: uppercase; }
        input { width: 100%; margin-top: 6px; padding: 10px 12px; border: 1px solid #c6b7a6; background: #fffdf8; font: inherit; }
        button { margin-top: 18px; padding: 10px 14px; border: 1px solid #1f1a16; background: #f0e8dc; color: #171412; font-family: monospace; font-size: 0.78rem; letter-spacing: 0.05em; text-transform: uppercase; cursor: pointer; }
        .login-note { color: #60574f; }
        .login-error { color: #8f2817; }
    </style>
</head>
<body>
<div class="login-shell">
    <p class="login-note"><?= htmlspecialchars($config['site_name']) ?></p>
    <h1>Editorial News Desk</h1>
    <p>Sign in to view and manage newsroom workflow, rankings, and overrides.</p>
    <p class="login-note">This login can stay active for several weeks on the same browser unless you explicitly log out.</p>
    <?php if ($message !== ''): ?>
        <p class="login-error"><?= htmlspecialchars($message) ?></p>
    <?php endif; ?>
    <form method="post">
        <input type="hidden" name="auth_action" value="login">
        <label>
            Username
            <input type="text" name="editorial_user" autocomplete="username" required>
        </label>
        <label>
            Password
            <input type="password" name="editorial_password" autocomplete="current-password" required>
        </label>
        <button type="submit">Enter Desk</button>
    </form>
</div>
</body>
</html>
<?php
    exit;
}

function newsroom_require_editorial_login(): void
{
    $config = newsroom_config();
    $expectedUser = (string) ($config['editorial_auth']['user'] ?? '');
    $expectedPassword = (string) ($config['editorial_auth']['password'] ?? '');

    if ($expectedUser === '' || $expectedPassword === '') {
        return;
    }

    newsroom_start_session();

    if (isset($_GET['logout']) && $_GET['logout'] === '1') {
        $_SESSION = [];
        if (ini_get('session.use_cookies')) {
            $params = session_get_cookie_params();
            setcookie(session_name(), '', time() - 42000, $params['path'], $params['domain'], (bool) $params['secure'], (bool) $params['httponly']);
        }
        session_destroy();
        header('Location: /desk');
        exit;
    }

    if (!empty($_SESSION['newsroom_editorial_authenticated'])) {
        return;
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST' && (string) ($_POST['auth_action'] ?? '') === 'login') {
        $providedUser = trim((string) ($_POST['editorial_user'] ?? ''));
        $providedPassword = (string) ($_POST['editorial_password'] ?? '');

        if (hash_equals($expectedUser, $providedUser) && hash_equals($expectedPassword, $providedPassword)) {
            $_SESSION['newsroom_editorial_authenticated'] = true;
            header('Location: /desk');
            exit;
        }

        newsroom_render_editorial_login('Incorrect username or password.');
    }

    newsroom_render_editorial_login();
}
