<?php

declare(strict_types=1);

require_once __DIR__ . '/../bootstrap.php';

function newsroom_db(bool $reconnect = false): PDO
{
    static $pdo = null;

    if ($reconnect) {
        $pdo = null;
    }

    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $config = newsroom_config()['db'];
    $dsn = sprintf(
        'mysql:host=%s;port=%s;dbname=%s;charset=%s',
        $config['host'],
        $config['port'],
        $config['name'],
        $config['charset']
    );

    $pdo = new PDO(
        $dsn,
        $config['user'],
        $config['password'],
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );

    return $pdo;
}

function newsroom_db_available(): bool
{
    try {
        newsroom_db();
        return true;
    } catch (Throwable $exception) {
        return false;
    }
}

/** Retry only idempotent reads, once, when MySQL drops the connection. */
function newsroom_db_read(string $sql, array $parameters): array
{
    for ($attempt = 0; $attempt < 2; $attempt++) {
        $pdo = newsroom_db($attempt > 0);
        try {
            $statement = $pdo->prepare($sql);
            foreach ($parameters as $name => $value) {
                $statement->bindValue($name, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
            }
            $statement->execute();
            return $statement->fetchAll();
        } catch (PDOException $exception) {
            $driverCode = (int) ($exception->errorInfo[1] ?? 0);
            if ($attempt > 0 || !in_array($driverCode, [2006, 2013], true) || $pdo->inTransaction()) {
                throw $exception;
            }
        }
    }
    return [];
}
