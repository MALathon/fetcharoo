import unittest
import requests
from unittest.mock import patch, MagicMock
from fetcharoo.downloader import download_pdf

class TestDownloader(unittest.TestCase):
    @patch('requests.get')
    def test_download_content_success(self, mock_get):
        # Mock a successful response from requests.get
        mock_get.return_value = MagicMock(
            content=b'Successful Content',
            headers={'Content-Type': 'application/pdf'},
            raise_for_status=lambda: None
        )
        # Test the download_content function
        result = download_pdf('https://example.com/test.pdf')
        self.assertEqual(result, b'Successful Content')

    @patch('requests.get')
    def test_download_content_non_pdf(self, mock_get):
        # Mock a non-PDF response from requests.get
        mock_get.return_value = MagicMock(
            content=b'Not a PDF',
            headers={'Content-Type': 'text/html'},
            raise_for_status=lambda: None
        )
        # Test the download_content function
        result = download_pdf('https://example.com/test.html')
        self.assertIsNone(result)

    @patch('requests.get')
    def test_download_content_timeout(self, mock_get):
        # Mock a request timeout exception from requests.get
        mock_get.side_effect = requests.exceptions.RequestException('Request failed')
        # Test the download_content function
        result = download_pdf('https://example.com/test.pdf', timeout=1)
        self.assertIsNone(result)

    @patch('requests.get')
    def test_download_content_max_retries(self, mock_get):
        # Mock a series of request failures from requests.get
        mock_get.side_effect = [
            requests.exceptions.RequestException('Request failed'),
            requests.exceptions.RequestException('Request failed'),
            requests.exceptions.RequestException('Request failed')
        ]
        # Test the download_content function with max_retries=3
        result = download_pdf('https://example.com/test.pdf', timeout=1, max_retries=3)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
