"""Tests for concurrent PDF downloading."""

import unittest
from unittest.mock import patch, MagicMock

from fetcharoo.async_downloader import download_pdfs_concurrent, RateLimiter


class TestRateLimiter(unittest.TestCase):
    """Test the thread-safe rate limiter."""

    def test_rate_limiter_creates_with_interval(self):
        limiter = RateLimiter(min_interval=1.0)
        self.assertEqual(limiter._min_interval, 1.0)

    def test_rate_limiter_wait_does_not_error(self):
        limiter = RateLimiter(min_interval=0.0)
        limiter.wait()  # Should not raise


class TestDownloadPdfsConcurrent(unittest.TestCase):
    """Test concurrent download functionality."""

    def test_empty_list_returns_empty(self):
        result = download_pdfs_concurrent([])
        self.assertEqual(result, [])

    @patch('fetcharoo.async_downloader.download_pdf')
    def test_downloads_all_urls(self, mock_download):
        mock_download.return_value = b'%PDF-1.4 fake content'
        urls = [
            'https://example.com/a.pdf',
            'https://example.com/b.pdf',
            'https://example.com/c.pdf',
        ]
        results = download_pdfs_concurrent(urls, max_workers=3, request_delay=0.0)

        self.assertEqual(len(results), 3)
        for content, url in results:
            self.assertEqual(content, b'%PDF-1.4 fake content')
            self.assertIn(url, urls)

    @patch('fetcharoo.async_downloader.download_pdf')
    def test_preserves_order(self, mock_download):
        def side_effect(url, **kwargs):
            return url.encode()

        mock_download.side_effect = side_effect
        urls = ['https://example.com/1.pdf', 'https://example.com/2.pdf']
        results = download_pdfs_concurrent(urls, max_workers=2, request_delay=0.0)

        self.assertEqual(results[0][1], urls[0])
        self.assertEqual(results[1][1], urls[1])

    @patch('fetcharoo.async_downloader.download_pdf')
    def test_handles_failures_gracefully(self, mock_download):
        mock_download.side_effect = [b'%PDF content', None, b'%PDF content']
        urls = ['https://example.com/a.pdf', 'https://example.com/b.pdf', 'https://example.com/c.pdf']
        results = download_pdfs_concurrent(urls, max_workers=3, request_delay=0.0)

        self.assertEqual(len(results), 3)
        self.assertIsNotNone(results[0][0])
        self.assertIsNone(results[1][0])
        self.assertIsNotNone(results[2][0])

    @patch('fetcharoo.async_downloader.download_pdf')
    def test_progress_callback_called(self, mock_download):
        mock_download.return_value = b'%PDF content'
        callback = MagicMock()
        urls = ['https://example.com/a.pdf', 'https://example.com/b.pdf']
        download_pdfs_concurrent(urls, max_workers=2, request_delay=0.0, progress_callback=callback)

        self.assertEqual(callback.call_count, 2)

    @patch('fetcharoo.async_downloader.download_pdf')
    def test_caps_workers_to_url_count(self, mock_download):
        mock_download.return_value = b'%PDF content'
        urls = ['https://example.com/a.pdf', 'https://example.com/b.pdf']
        # max_workers=100 but only 2 URLs, so only 2 workers should be used
        results = download_pdfs_concurrent(urls, max_workers=100, request_delay=0.0)
        self.assertEqual(len(results), 2)


if __name__ == '__main__':
    unittest.main()
