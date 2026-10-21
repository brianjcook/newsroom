"""Regression checks for publisher holds; runs without a production database."""
import datetime
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'worker'))
# PyMySQL is used only for a type annotation in publish.py; the SQL fake below
# intentionally avoids a driver/network dependency for these policy tests.
try:
    import pymysql.connections
except ImportError:
    driver = types.ModuleType('pymysql')
    connections = types.ModuleType('pymysql.connections')
    connections.Connection = object
    driver.connections = connections
    sys.modules['pymysql'] = driver
    sys.modules['pymysql.connections'] = connections

from newsroom import publication, publish


class PolicyTests(unittest.TestCase):
    def test_initial_sensitive_requires_hold(self):
        reasons = publication.sensitive_reasons('Board will discuss allegations of misconduct')
        self.assertTrue(reasons)
        self.assertEqual('hold', publication.publication_decision(None, None, False, reasons)[0])

    def test_revision_hash_covers_public_metadata_and_ordered_citations(self):
        sql = publication.revision_hash_sql('s')
        for field in ('byline_name', 'byline_title', 'public_label', 'story_type', 'slug', 'topic_tags_json', 'display_date', 'sort_date'):
            self.assertIn('s.' + field, sql)
        self.assertIn('sc.story_id=s.id', sql)
        self.assertIn('ORDER BY sc.citation_number', sql)
        self.assertIn('@@session.group_concat_max_len,NULL', sql)
        for field in ('citation_number', 'label', 'source_url', 'quote_text', 'note_text'):
            self.assertIn('sc.' + field, sql)
        with self.assertRaises(ValueError):
            publication.revision_hash_sql('s;DROP TABLE stories')

    def test_ordinary_budget_can_publish(self):
        reasons = publication.sensitive_reasons('Board to consider FY2027 capital budget')
        self.assertFalse(reasons)
        self.assertEqual('publish', publication.publication_decision(None, None, False, reasons)[0])

    def test_holds_withdrawals_and_manual_suppression_survive(self):
        for state in ('hold', 'withdrawn'):
            self.assertEqual('preserve', publication.publication_decision({'publish_status': 'published'}, {'state': state}, True, [])[0])
        self.assertEqual('preserve', publication.publication_decision({'publish_status': 'suppressed'}, None, True, [])[0])

    def test_changed_approved_revision_is_held(self):
        existing = {'publish_status': 'published', 'revision_hash': 'a' * 64}
        review = {'state': 'approved', 'approved_hash': 'a' * 64}
        self.assertEqual('hold', publication.publication_decision(existing, review, True, [])[0])
        self.assertEqual('preserve', publication.publication_decision(existing, review, False, ['sensitive'])[0])
        review['approved_hash'] = 'b' * 64
        self.assertEqual('hold', publication.publication_decision(existing, review, False, [])[0])

    def test_unknown_review_fails_closed(self):
        self.assertEqual('hold', publication.publication_decision({'publish_status': 'published'}, {'state': 'unexpected'}, False, [])[0])

    def test_material_source_change_not_render_version(self):
        story = {'headline': 'Budget', 'dek': '', 'summary': 'Summary', 'body_html': '<p>Record</p>'}
        basis = {'source_url': 'https://example.test/source', 'extraction_id': 7, 'render_version': 'old'}
        later = dict(basis, render_version='new')
        self.assertFalse(publication.material_revision_changed(story, story, basis, later))
        later['extraction_id'] = 8
        self.assertTrue(publication.material_revision_changed(story, story, basis, later))

    def test_nested_evidence_and_privacy_are_screened(self):
        for text in ('An arrest was recorded', 'Student disciplinary records', '123-45-6789', 'Pending litigation', 'Tobacco violations'):
            self.assertTrue(publication.sensitive_reasons('ordinary headline', text), text)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.lastrowid = 42
        self.rows = []
        self.row = None
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, params=None):
        if params is not None:
            if sql.count('%s') != len(params):
                raise AssertionError('SQL binding mismatch: ' + sql)
        self.connection.calls.append((sql, params))
        self.rows, self.row = [], None
        if 'm.id AS meeting_id' in sql:
            self.rows = [self.connection.source]
        elif 'FROM stories WHERE meeting_id' in sql:
            self.row = self.connection.existing
            if 'FOR UPDATE' not in sql: raise AssertionError('Story must lock before review')
        elif 'FROM meetings m' in sql:
            self.rows = getattr(self.connection, 'meetings', [])
        elif 'FROM calendar_events WHERE' in sql:
            self.row = {'id': 77}
        elif 'FROM stories s LEFT JOIN publication_reviews' in sql:
            self.row = {'id': 42} if getattr(self.connection, 'calendar_blocked', False) else None
        elif 'FROM publication_reviews WHERE' in sql:
            self.row = self.connection.review
            if 'FOR UPDATE' not in sql: raise AssertionError('Review must use current locking read')
        return 1
    def fetchall(self): return self.rows
    def fetchone(self): return self.row


class FakeConnection:
    def __init__(self, existing=None, review=None):
        self.calls, self.existing, self.review = [], existing, review
        self.source = {
            'auto_publish_allowed': 1, 'meeting_id': 9, 'governing_body_id': 2,
            'governing_body': 'Select Board', 'meeting_type': 'regular',
            'meeting_date': datetime.date(2026, 10, 21), 'meeting_time': '18:00:00',
            'location_name': 'Town Hall', 'agenda_posted_at': None, 'minutes_posted_at': None,
            'status': 'scheduled', 'artifact_type': 'agenda', 'source_item_id': 3,
            'resolved_document_url': 'https://example.test/agenda', 'canonical_url': 'https://example.test/agenda',
            'source_title': 'Agenda', 'extraction_id': 5, 'extraction_title': 'Agenda',
            'body_text': 'Allegations of misconduct', 'structured_json': '{}',
            'confidence_score': 1, 'warnings_json': '[]', 'artifact_posted_at': None, 'is_amended': 0,
        }
    def cursor(self): return FakeCursor(self)


class PublisherWiringTests(unittest.TestCase):
    def run_publisher(self, connection):
        copy = ('Board agenda', 'Details', 'Summary', '<p>Details</p>', 'Details', [])
        with patch.object(publish, '_build_story_copy', return_value=copy), \
             patch.object(publish, '_story_slug', return_value='board-agenda'), \
             patch.object(publish, 'score_story', return_value={'score': 60, 'signals': {}, 'coverage_mode': 'brief'}), \
             patch.object(publish, 'derive_story_dates', return_value=('2026-10-21', '2026-10-21')), \
             patch.object(publish, '_should_publish_story', return_value=True), \
             patch.object(publish, '_sync_story_citations'), \
             patch.object(publish, '_sync_workflow_states'):
            return publish.publish_stories_and_events(connection)

    def test_sensitive_initial_draft_records_hold_not_published(self):
        connection = FakeConnection()
        result = self.run_publisher(connection)
        inserts = [(sql, args) for sql, args in connection.calls if 'INSERT INTO stories (' in sql]
        self.assertEqual(1, len(inserts))
        self.assertIn('draft', inserts[0][1])
        self.assertTrue(any('INSERT INTO publication_reviews' in sql for sql, _ in connection.calls))
        self.assertFalse(any("UPDATE source_items SET status = 'published'" in sql for sql, _ in connection.calls))
        self.assertEqual(0, result.stories_published)

    def test_existing_hold_never_regenerated(self):
        connection = FakeConnection({'id': 42, 'slug': 'old', 'publish_status': 'published', 'source_basis_json': '{}'}, {'state': 'hold'})
        self.run_publisher(connection)
        self.assertFalse(any('UPDATE stories' in sql or 'INSERT INTO stories' in sql for sql, _ in connection.calls))

    def test_approved_material_change_stores_new_draft_before_hash(self):
        existing = {'id': 42, 'slug': 'old', 'publish_status': 'published', 'source_basis_json': '{}',
                    'revision_hash': 'a' * 64, 'headline': 'Old headline', 'body_html': '<p>Old</p>', 'published_at': None}
        connection = FakeConnection(existing, {'state': 'approved', 'approved_hash': 'a' * 64})
        self.run_publisher(connection)
        updates = [(i, sql, args) for i, (sql, args) in enumerate(connection.calls) if 'UPDATE stories\n' in sql]
        self.assertEqual(1, len(updates))
        self.assertIn('Board agenda', updates[0][2])
        self.assertIn('draft', updates[0][2])
        hash_insert = next(i for i, (sql, _) in enumerate(connection.calls) if 'INSERT INTO publication_reviews' in sql)
        self.assertGreater(hash_insert, updates[0][0])

    def test_unchanged_sensitive_existing_story_cannot_bypass_hold(self):
        connection = FakeConnection()
        extraction = {'id': 5, 'structured_json': '{}', 'body_text': 'Allegations of misconduct'}
        basis_json = publish._story_basis_json({'source_item_id': 3, 'canonical_url': 'https://example.test/agenda'}, extraction, 'agenda', None, False, publish._story_content_signature('Board agenda', 'Details', 'Summary', 'Details'))
        connection.existing = {'id': 42, 'slug': 'board-agenda', 'publish_status': 'published', 'source_basis_json': basis_json,
                               'revision_hash': 'a' * 64, 'headline': 'Board agenda', 'dek': 'Details', 'summary': 'Summary',
                               'body_html': '<p>Details</p>', 'published_at': None, 'editorial_score': 60,
                               'suggested_coverage_mode': 'brief', 'editorial_signals_json': '{}', 'topic_tags_json': '[]'}
        self.run_publisher(connection)
        self.assertTrue(any('INSERT INTO publication_reviews' in sql for sql, _ in connection.calls))

    def test_stale_approval_holds_manual_edit_without_overwrite(self):
        existing = {'id': 42, 'slug': 'old', 'publish_status': 'published', 'source_basis_json': '{}',
                    'revision_hash': 'b' * 64, 'headline': 'Manual edit', 'body_html': '<p>Manual</p>'}
        connection = FakeConnection(existing, {'state': 'approved', 'approved_hash': 'a' * 64})
        self.run_publisher(connection)
        self.assertFalse(any('SET governing_body_id' in sql for sql, _ in connection.calls))
        self.assertTrue(any('INSERT INTO publication_reviews' in sql for sql, _ in connection.calls))

    def test_holding_increments_decision_version_and_handles_unhashable_revision(self):
        connection = FakeConnection()
        publication.hold_story(connection, 42, 'Review needed')
        sql = next(sql for sql, _ in connection.calls if 'INSERT INTO publication_reviews' in sql)
        self.assertIn('decision_version=decision_version+1', sql)
        self.assertIn("REPEAT('0',64)", sql)

    def test_held_meeting_calendar_stays_suppressed(self):
        connection = FakeConnection({'id': 42, 'slug': 'old', 'publish_status': 'draft', 'source_basis_json': '{}'}, {'state': 'hold'})
        connection.calendar_blocked = True
        connection.meetings = [{'id': 9, 'auto_publish_allowed': 1, 'governing_body': 'Select Board',
                                'meeting_date': datetime.date(2026, 10, 21), 'meeting_time': None,
                                'status': 'scheduled', 'artifact_type': 'agenda', 'is_amended': 0}]
        self.run_publisher(connection)
        self.assertTrue(any("UPDATE calendar_events SET status='suppressed'" in sql for sql, _ in connection.calls))
        self.assertFalse(any("status = 'scheduled'" in sql for sql, _ in connection.calls))

    def test_routine_initial_story_still_publishes(self):
        connection = FakeConnection()
        connection.source['body_text'] = 'Consider the capital budget.'
        result = self.run_publisher(connection)
        self.assertEqual(1, result.stories_published)
        self.assertFalse(any('INSERT INTO publication_reviews' in sql for sql, _ in connection.calls))


if __name__ == '__main__':
    unittest.main()
