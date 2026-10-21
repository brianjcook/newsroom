<?php
// Exercise the production read helper with controlled disconnects, without MySQL.
declare(strict_types=1);

class TestConnection extends PDO
{
    public bool $transaction = false;
    public function __construct() {}
    public function prepare(string $query, array $options = []): PDOStatement|false
    {
        return new TestStatement();
    }
    public function inTransaction(): bool { return $this->transaction; }
}
class TestStatement extends PDOStatement
{
    public function bindValue(string|int $param, mixed $value, int $type = PDO::PARAM_STR): bool
    {
        $GLOBALS['bindings'][$param] = $type;
        return true;
    }
    public function execute(?array $params = null): bool
    {
        $GLOBALS['executions']++;
        $code = array_shift($GLOBALS['failures']);
        if ($code) {
            $exception = new PDOException('Simulated database failure');
            $exception->errorInfo = ['HY000', $code, 'Simulated database failure'];
            throw $exception;
        }
        return true;
    }
    public function fetchAll(int $mode = PDO::FETCH_DEFAULT, mixed ...$args): array
    {
        return [['id' => 1]];
    }
}
function newsroom_db(bool $reconnect = false): PDO
{
    if ($reconnect) { $GLOBALS['reconnections']++; }
    return $GLOBALS['connection'];
}
$source = file_get_contents(__DIR__ . '/../web/lib/db.php');
$start = strpos($source, 'function newsroom_db_read(');
if ($start === false) { throw new RuntimeException('Missing production read helper'); }
eval(substr($source, $start));
foreach ([[[], false, false, 1, 0], [[2006], false, false, 2, 1], [[2013], false, false, 2, 1], [[2006, 2006], false, true, 2, 1], [[1064], false, true, 1, 0], [[2006], true, true, 1, 0]] as $case) {
    [$failures, $transaction, $shouldThrow, $expectedExecutions, $expectedReconnections] = $case;
    $connection = new TestConnection();
    $connection->transaction = $transaction;
    $executions = $reconnections = 0;
    $bindings = [];
    $threw = false;
    try {
        $rows = newsroom_db_read('SELECT id FROM stories LIMIT :limit', [':limit' => 24, ':status' => 'published']);
        if ($rows !== [['id' => 1]]) { throw new RuntimeException('Rows changed'); }
    } catch (PDOException $exception) { $threw = true; }
    if ($threw !== $shouldThrow || $executions !== $expectedExecutions || $reconnections !== $expectedReconnections || $bindings !== [':limit' => PDO::PARAM_INT, ':status' => PDO::PARAM_STR]) {
        throw new RuntimeException('Connection recovery regression');
    }
}
echo "Six connection recovery scenarios passed.\n";
