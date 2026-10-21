"""Validate the exact SQL shared by PHP and the scheduled Python publisher."""
import os
from pathlib import Path
import subprocess
import sys
import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'worker'))
from newsroom.publication import revision_hash_sql, hold_story, ensure_publication_schema

database = os.environ['NEWSROOM_DB_NAME']
assert database.endswith('_test')
connection = pymysql.connect(host=os.environ['NEWSROOM_DB_HOST'], port=int(os.environ['NEWSROOM_DB_PORT']), user=os.environ['NEWSROOM_DB_USER'], password=os.environ['NEWSROOM_DB_PASSWORD'], database=database, charset='utf8mb4', autocommit=False, cursorclass=pymysql.cursors.DictCursor)
php_expression = subprocess.check_output(['php', '-r', "require 'web/lib/publication.php'; echo newsroom_publication_revision_sql('s');"], cwd=ROOT, text=True)
try:
    ensure_publication_schema(connection)
    with connection.cursor() as cursor:
        cursor.execute('SELECT ' + php_expression + ' AS php_hash, ' + revision_hash_sql('s') + ' AS py_hash FROM stories s WHERE s.id=900001')
        values = cursor.fetchone()
        assert values['php_hash'] == values['py_hash'] and values['py_hash'], values
        before = values['py_hash']
        cursor.execute("INSERT INTO story_citations (story_id,citation_number,label,source_url,quote_text,note_text) VALUES (900001,1,'Official agenda','https://example.org/agenda','Budget vote','Source record')")
        cursor.execute('SELECT ' + php_expression + ' AS php_hash, ' + revision_hash_sql('s') + ' AS py_hash FROM stories s WHERE s.id=900001')
        values = cursor.fetchone()
        assert values['php_hash'] == values['py_hash'] and values['py_hash'] != before, values
        cursor.execute("UPDATE story_citations SET note_text='Changed source note' WHERE story_id=900001")
        cursor.execute('SELECT ' + revision_hash_sql() + ' AS py_hash FROM stories WHERE id=900001 FOR UPDATE')
        assert cursor.fetchone()['py_hash'] != values['py_hash']
    hold_story(connection, 900001, 'SQL worker hold integration')
    with connection.cursor() as cursor:
        cursor.execute('SELECT s.publish_status, pr.state, pr.revision_hash, ' + revision_hash_sql('s') + ' AS actual_hash FROM stories s JOIN publication_reviews pr ON pr.story_id=s.id WHERE s.id=900001')
        row = cursor.fetchone()
        assert row['publish_status'] == 'draft' and row['state'] == 'hold' and row['revision_hash'] == row['actual_hash'], row
        for number in range(2, 20):
            cursor.execute("INSERT INTO story_citations (story_id,citation_number,label,source_url) VALUES (900001,%s,'Source','https://example.org/source')", (number,))
        cursor.execute('SET SESSION group_concat_max_len=1024')
        cursor.execute('SELECT ' + php_expression + ' AS php_hash, ' + revision_hash_sql('s') + ' AS py_hash FROM stories s WHERE s.id=900001')
        row = cursor.fetchone()
        assert row['php_hash'] is None and row['py_hash'] is None, row
    hold_story(connection, 900001, 'Oversized evidence remains held')
    with connection.cursor() as cursor:
        cursor.execute('SELECT revision_hash,approved_hash FROM publication_reviews WHERE story_id=900001')
        row = cursor.fetchone()
        assert row['revision_hash'] == '0' * 64 and row['approved_hash'] is None, row
    connection.rollback()
finally:
    connection.close()
print('Shared PHP/Python SQL passed: citation-sensitive hash parity, worker hold, row locking and oversized evidence fail-closed.')
