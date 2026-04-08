"""Tests for watch mode and document change monitoring."""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from fetcharoo.catalog import DocumentCatalog, DiffResult, DocumentRecord
from fetcharoo.watcher import DocumentWatcher, diff_once
from fetcharoo.notifications import (
    format_diff_text,
    format_diff_json,
    has_changes,
)


class TestNotifications(unittest.TestCase):
    """Test notification formatting."""

    def _make_diff(self, new=0, changed=0, removed=0, unchanged=0):
        return DiffResult(
            new=[DocumentRecord(id=str(i), url=f'https://example.com/new{i}.pdf') for i in range(new)],
            changed=[DocumentRecord(id=str(i), url=f'https://example.com/changed{i}.pdf') for i in range(changed)],
            removed=[DocumentRecord(id=str(i), url=f'https://example.com/removed{i}.pdf') for i in range(removed)],
            unchanged=[DocumentRecord(id=str(i), url=f'https://example.com/unchanged{i}.pdf') for i in range(unchanged)],
        )

    def test_has_changes_with_new(self):
        diff = self._make_diff(new=1)
        self.assertTrue(has_changes(diff))

    def test_has_changes_with_removed(self):
        diff = self._make_diff(removed=1)
        self.assertTrue(has_changes(diff))

    def test_has_changes_no_changes(self):
        diff = self._make_diff(unchanged=3)
        self.assertFalse(has_changes(diff))

    def test_format_diff_text_new(self):
        diff = self._make_diff(new=1)
        text = format_diff_text(diff, 'https://example.com')
        self.assertIn('+', text)
        self.assertIn('new0.pdf', text)

    def test_format_diff_text_removed(self):
        diff = self._make_diff(removed=1)
        text = format_diff_text(diff, 'https://example.com')
        self.assertIn('-', text)
        self.assertIn('removed0.pdf', text)

    def test_format_diff_text_no_changes(self):
        diff = self._make_diff(unchanged=1)
        text = format_diff_text(diff, 'https://example.com')
        self.assertIn('No changes', text)

    def test_format_diff_json(self):
        import json
        diff = self._make_diff(new=2, removed=1)
        result = json.loads(format_diff_json(diff, 'https://example.com'))
        self.assertEqual(result['summary']['new'], 2)
        self.assertEqual(result['summary']['removed'], 1)
        self.assertEqual(len(result['new']), 2)


class TestDocumentWatcher(unittest.TestCase):
    """Test the DocumentWatcher class."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        self.catalog = DocumentCatalog(db_path=self.tmp)

    def tearDown(self):
        self.catalog.close()
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    @patch('fetcharoo.watcher.find_pdfs_from_webpage')
    def test_check_once_detects_new(self, mock_find):
        mock_find.return_value = ['https://example.com/a.pdf', 'https://example.com/b.pdf']

        watcher = DocumentWatcher('https://example.com', self.catalog)
        diff = watcher.check_once()

        self.assertEqual(len(diff.new), 2)
        self.assertEqual(len(diff.removed), 0)

    @patch('fetcharoo.watcher.find_pdfs_from_webpage')
    def test_check_once_detects_removed(self, mock_find):
        # First: discover a doc
        self.catalog.record_discovery('https://example.com/old.pdf')

        # Then: it's gone
        mock_find.return_value = []
        watcher = DocumentWatcher('https://example.com', self.catalog)
        diff = watcher.check_once()

        self.assertEqual(len(diff.removed), 1)

    @patch('fetcharoo.watcher.find_pdfs_from_webpage')
    def test_check_once_records_run(self, mock_find):
        mock_find.return_value = ['https://example.com/a.pdf']

        watcher = DocumentWatcher('https://example.com', self.catalog)
        watcher.check_once()

        runs = self.catalog.get_runs()
        self.assertEqual(len(runs), 1)

    @patch('fetcharoo.watcher.find_pdfs_from_webpage')
    def test_check_once_updates_catalog(self, mock_find):
        mock_find.return_value = ['https://example.com/new.pdf']

        watcher = DocumentWatcher('https://example.com', self.catalog)
        watcher.check_once()

        doc = self.catalog.get_document('https://example.com/new.pdf')
        self.assertIsNotNone(doc)
        self.assertEqual(doc.status, 'active')


class TestDiffOnce(unittest.TestCase):
    """Test the one-shot diff function."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        self.catalog = DocumentCatalog(db_path=self.tmp)

    def tearDown(self):
        self.catalog.close()
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    @patch('fetcharoo.watcher.find_pdfs_from_webpage')
    def test_diff_once_text_output(self, mock_find):
        mock_find.return_value = ['https://example.com/a.pdf']
        diff = diff_once('https://example.com', self.catalog, output_format='text')
        self.assertEqual(len(diff.new), 1)

    @patch('fetcharoo.watcher.find_pdfs_from_webpage')
    def test_diff_once_json_output(self, mock_find):
        mock_find.return_value = ['https://example.com/a.pdf']
        diff = diff_once('https://example.com', self.catalog, output_format='json')
        self.assertEqual(len(diff.new), 1)


if __name__ == '__main__':
    unittest.main()
