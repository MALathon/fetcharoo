"""Tests for the persistent document catalog."""

import os
import json
import tempfile
import unittest

from fetcharoo.catalog import (
    DocumentCatalog,
    DocumentRecord,
    DiffResult,
    extract_pdf_metadata,
    _url_id,
    _content_hash,
)


class TestHelpers(unittest.TestCase):
    """Test catalog helper functions."""

    def test_url_id_deterministic(self):
        id1 = _url_id('https://example.com/doc.pdf')
        id2 = _url_id('https://example.com/doc.pdf')
        self.assertEqual(id1, id2)

    def test_url_id_different_for_different_urls(self):
        id1 = _url_id('https://example.com/a.pdf')
        id2 = _url_id('https://example.com/b.pdf')
        self.assertNotEqual(id1, id2)

    def test_content_hash_deterministic(self):
        h1 = _content_hash(b'%PDF-1.4 content')
        h2 = _content_hash(b'%PDF-1.4 content')
        self.assertEqual(h1, h2)

    def test_content_hash_different_for_different_content(self):
        h1 = _content_hash(b'%PDF-1.4 content A')
        h2 = _content_hash(b'%PDF-1.4 content B')
        self.assertNotEqual(h1, h2)


class TestDocumentCatalog(unittest.TestCase):
    """Test the DocumentCatalog class."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        self.catalog = DocumentCatalog(db_path=self.tmp)

    def tearDown(self):
        self.catalog.close()
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_empty_catalog(self):
        self.assertEqual(self.catalog.document_count, 0)
        self.assertEqual(self.catalog.active_count, 0)

    def test_record_discovery(self):
        doc = self.catalog.record_discovery(
            'https://example.com/test.pdf',
            source_page='https://example.com',
            filename='test.pdf'
        )
        self.assertEqual(doc.url, 'https://example.com/test.pdf')
        self.assertEqual(doc.filename, 'test.pdf')
        self.assertEqual(doc.status, 'active')
        self.assertEqual(self.catalog.document_count, 1)

    def test_upsert_with_content(self):
        content = b'%PDF-1.4 test content'
        doc = self.catalog.upsert_document(
            'https://example.com/test.pdf',
            content=content,
            filename='test.pdf'
        )
        self.assertIsNotNone(doc.content_hash)
        self.assertEqual(doc.size_bytes, len(content))
        self.assertIsNotNone(doc.first_seen)
        self.assertIsNotNone(doc.last_seen)

    def test_upsert_updates_existing(self):
        self.catalog.record_discovery('https://example.com/test.pdf', filename='test.pdf')
        doc = self.catalog.upsert_document(
            'https://example.com/test.pdf',
            content=b'%PDF-1.4 new content',
            filename='test.pdf'
        )
        self.assertEqual(self.catalog.document_count, 1)
        self.assertIsNotNone(doc.content_hash)

    def test_get_document(self):
        self.catalog.record_discovery('https://example.com/test.pdf', filename='test.pdf')
        doc = self.catalog.get_document('https://example.com/test.pdf')
        self.assertIsNotNone(doc)
        self.assertEqual(doc.url, 'https://example.com/test.pdf')

    def test_get_document_not_found(self):
        doc = self.catalog.get_document('https://example.com/nonexistent.pdf')
        self.assertIsNone(doc)

    def test_mark_removed(self):
        self.catalog.record_discovery('https://example.com/test.pdf')
        self.catalog.mark_removed('https://example.com/test.pdf')
        doc = self.catalog.get_document('https://example.com/test.pdf')
        self.assertEqual(doc.status, 'removed')

    def test_get_active_documents(self):
        self.catalog.record_discovery('https://example.com/a.pdf')
        self.catalog.record_discovery('https://example.com/b.pdf')
        self.catalog.mark_removed('https://example.com/b.pdf')

        active = self.catalog.get_active_documents()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].url, 'https://example.com/a.pdf')

    def test_get_active_documents_by_source(self):
        self.catalog.record_discovery('https://example.com/a.pdf', source_page='https://example.com')
        self.catalog.record_discovery('https://other.com/b.pdf', source_page='https://other.com')

        docs = self.catalog.get_active_documents(source_page='https://example.com')
        self.assertEqual(len(docs), 1)

    def test_diff_new_documents(self):
        current_urls = ['https://example.com/a.pdf', 'https://example.com/b.pdf']
        diff = self.catalog.diff(current_urls)
        self.assertEqual(len(diff.new), 2)
        self.assertEqual(len(diff.unchanged), 0)
        self.assertEqual(len(diff.removed), 0)

    def test_diff_unchanged_documents(self):
        self.catalog.record_discovery('https://example.com/a.pdf')
        diff = self.catalog.diff(['https://example.com/a.pdf'])
        self.assertEqual(len(diff.new), 0)
        self.assertEqual(len(diff.unchanged), 1)
        self.assertEqual(len(diff.removed), 0)

    def test_diff_removed_documents(self):
        self.catalog.record_discovery('https://example.com/a.pdf')
        diff = self.catalog.diff([])
        self.assertEqual(len(diff.new), 0)
        self.assertEqual(len(diff.removed), 1)

    def test_diff_mixed(self):
        self.catalog.record_discovery('https://example.com/old.pdf')
        diff = self.catalog.diff(['https://example.com/old.pdf', 'https://example.com/new.pdf'])
        self.assertEqual(len(diff.new), 1)
        self.assertEqual(len(diff.unchanged), 1)
        self.assertEqual(len(diff.removed), 0)

    def test_record_run(self):
        diff = DiffResult(
            new=[DocumentRecord(id='1', url='https://example.com/a.pdf')],
            unchanged=[DocumentRecord(id='2', url='https://example.com/b.pdf')],
        )
        run = self.catalog.record_run('https://example.com', diff)
        self.assertIsNotNone(run.id)
        self.assertEqual(run.documents_new, 1)
        self.assertEqual(run.documents_found, 2)

    def test_get_runs(self):
        diff = DiffResult()
        self.catalog.record_run('https://example.com', diff)
        runs = self.catalog.get_runs()
        self.assertEqual(len(runs), 1)

    def test_search(self):
        self.catalog.record_discovery('https://example.com/report_2024.pdf', filename='report_2024.pdf')
        self.catalog.record_discovery('https://example.com/invoice.pdf', filename='invoice.pdf')

        results = self.catalog.search('report')
        self.assertEqual(len(results), 1)
        self.assertIn('report', results[0].url)

    def test_search_no_results(self):
        results = self.catalog.search('nonexistent')
        self.assertEqual(len(results), 0)

    def test_find_duplicates(self):
        content = b'%PDF-1.4 identical content'
        self.catalog.upsert_document('https://site-a.com/doc.pdf', content=content)
        self.catalog.upsert_document('https://site-b.com/doc.pdf', content=content)

        dupes = self.catalog.find_duplicates()
        self.assertEqual(len(dupes), 1)

    def test_export_json(self):
        self.catalog.record_discovery('https://example.com/test.pdf', filename='test.pdf')
        json_str = self.catalog.export_json()
        data = json.loads(json_str)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['url'], 'https://example.com/test.pdf')

    def test_export_csv(self):
        self.catalog.record_discovery('https://example.com/test.pdf', filename='test.pdf')
        csv_str = self.catalog.export_csv()
        self.assertIn('url', csv_str)
        self.assertIn('example.com', csv_str)


class TestExtractPdfMetadata(unittest.TestCase):
    """Test PDF metadata extraction."""

    def test_invalid_content_returns_empty(self):
        metadata = extract_pdf_metadata(b'not a pdf')
        self.assertEqual(metadata, {})


if __name__ == '__main__':
    unittest.main()
