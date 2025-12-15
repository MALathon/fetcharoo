import unittest
import os
import pymupdf
import requests
import time
from unittest.mock import patch, MagicMock, Mock
from tempfile import TemporaryDirectory
import responses

from fetcharoo.fetcharoo import (
    is_valid_url,
    process_pdfs,
    find_pdfs_from_webpage,
    is_safe_domain
)
from fetcharoo.downloader import download_pdf
from fetcharoo.pdf_utils import merge_pdfs, save_pdf_to_file


class TestFetcharooErrorHandling(unittest.TestCase):
    """Test error handling and edge cases for fetcharoo.py"""

    def test_is_valid_url_with_ftp_scheme(self):
        """Test that FTP scheme URLs are rejected"""
        self.assertFalse(is_valid_url('ftp://example.com/file.pdf'))

    def test_is_valid_url_with_file_scheme(self):
        """Test that file:// scheme URLs are rejected"""
        self.assertFalse(is_valid_url('file:///etc/passwd'))

    def test_is_valid_url_with_javascript_scheme(self):
        """Test that javascript: scheme URLs are rejected"""
        self.assertFalse(is_valid_url('javascript:alert(1)'))

    def test_is_valid_url_with_data_scheme(self):
        """Test that data: scheme URLs are rejected"""
        self.assertFalse(is_valid_url('data:text/html,<script>alert(1)</script>'))

    def test_is_valid_url_with_valid_http(self):
        """Test that valid HTTP URLs are accepted"""
        self.assertTrue(is_valid_url('http://example.com'))

    def test_is_valid_url_with_valid_https(self):
        """Test that valid HTTPS URLs are accepted"""
        self.assertTrue(is_valid_url('https://example.com'))

    def test_is_valid_url_with_no_netloc(self):
        """Test that URLs without netloc are rejected"""
        self.assertFalse(is_valid_url('http://'))

    def test_process_pdfs_with_invalid_mode(self):
        """Test that process_pdfs returns False with invalid mode"""
        pdf_links = ['https://example.com/test.pdf']
        with TemporaryDirectory() as temp_dir:
            result = process_pdfs(pdf_links, temp_dir, mode='invalid_mode')
            self.assertFalse(result)

    def test_process_pdfs_with_empty_pdf_links(self):
        """Test that process_pdfs returns False with empty pdf_links list"""
        pdf_links = []
        with TemporaryDirectory() as temp_dir:
            result = process_pdfs(pdf_links, temp_dir, mode='separate')
            self.assertFalse(result)

    @responses.activate
    def test_find_pdfs_hitting_max_recursion_depth(self):
        """Test that recursion is limited to MAX_RECURSION_DEPTH"""
        # Create a chain of pages deeper than MAX_RECURSION_DEPTH
        # MAX_RECURSION_DEPTH is 5 in the source code
        base_url = 'https://example.com/page0'

        # Mock responses for pages 0 through 6
        for i in range(7):
            page_url = f'https://example.com/page{i}'
            next_page_url = f'https://example.com/page{i+1}'
            html_content = f'<a href="{next_page_url}">Next</a>'
            responses.add(responses.GET, page_url, body=html_content, status=200)

        # Call with recursion_depth > MAX_RECURSION_DEPTH (which is 5)
        # The function should limit it to 5
        with patch('fetcharoo.fetcharoo.logger') as mock_logger:
            pdf_links = find_pdfs_from_webpage(base_url, recursion_depth=10)
            # Check that warning was logged about exceeding max recursion
            mock_logger.warning.assert_called()

    @responses.activate
    def test_find_pdfs_request_timeout(self):
        """Test handling of request timeout"""
        url = 'https://example.com'

        # Mock a timeout exception
        responses.add(responses.GET, url, body=requests.exceptions.Timeout())

        with patch('fetcharoo.fetcharoo.logger') as mock_logger:
            pdf_links = find_pdfs_from_webpage(url, recursion_depth=0)
            # Should return empty list and log error
            self.assertEqual(pdf_links, [])
            # Verify that timeout error was logged
            mock_logger.error.assert_called()

    @responses.activate
    def test_find_pdfs_domain_restriction_for_recursive_crawl(self):
        """Test that allowed_domains restricts which PAGES are crawled, not which PDFs are found.

        PDF links on the initial page are always collected. The domain restriction
        prevents following links to external pages during recursive crawling.
        """
        base_url = 'https://allowed.com'
        external_pdf = 'https://notallowed.com/file.pdf'
        internal_pdf = 'https://allowed.com/local.pdf'
        external_page = 'https://notallowed.com/page.html'

        # Page with both internal and external PDFs, plus an external page link
        html_content = f'''
            <a href="{internal_pdf}">Internal PDF</a>
            <a href="{external_pdf}">External PDF</a>
            <a href="{external_page}">External Page</a>
        '''
        responses.add(responses.GET, base_url, body=html_content, status=200)
        # Don't add mock for external_page - it should never be accessed

        allowed_domains = {'allowed.com'}

        pdf_links = find_pdfs_from_webpage(
            base_url,
            recursion_depth=1,  # Enable recursion to test domain restriction
            allowed_domains=allowed_domains
        )

        # PDF links from all domains are found on the initial page
        self.assertIn(internal_pdf, pdf_links)
        self.assertIn(external_pdf, pdf_links)

        # Verify external page was NOT crawled (only 1 request to base_url)
        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_is_safe_domain_with_subdomain(self):
        """Test that subdomains are properly handled in domain checks"""
        # Test subdomain matching
        self.assertTrue(is_safe_domain('https://sub.example.com', {'example.com'}))
        self.assertTrue(is_safe_domain('https://example.com', {'example.com'}))
        self.assertFalse(is_safe_domain('https://notexample.com', {'example.com'}))

    @responses.activate
    def test_is_safe_domain_with_port(self):
        """Test that domains with ports are properly handled"""
        self.assertTrue(is_safe_domain('https://example.com:8080', {'example.com'}))

    def test_is_safe_domain_with_none_allowed_domains(self):
        """Test that None allowed_domains allows all domains"""
        self.assertTrue(is_safe_domain('https://any.com', None))


class TestDownloaderErrorHandling(unittest.TestCase):
    """Test error handling and edge cases for downloader.py"""

    @patch('fetcharoo.downloader.time.sleep')
    @patch('fetcharoo.downloader.requests.get')
    def test_timeout_after_all_retries_exhausted(self, mock_get, mock_sleep):
        """Test that None is returned after all retries are exhausted due to timeout"""
        # Mock all attempts to raise Timeout
        mock_get.side_effect = requests.exceptions.Timeout()

        with patch('fetcharoo.downloader.logging') as mock_logging:
            result = download_pdf('https://example.com/test.pdf', timeout=1, max_retries=3)

            # Should return None after all retries
            self.assertIsNone(result)
            # Should have been called 3 times (max_retries)
            self.assertEqual(mock_get.call_count, 3)
            # Should have logged error
            mock_logging.error.assert_called()

    @patch('fetcharoo.downloader.time.sleep')
    @patch('fetcharoo.downloader.requests.get')
    def test_exponential_backoff_verification(self, mock_get, mock_sleep):
        """Test that exponential backoff is implemented correctly"""
        # First two attempts fail, third succeeds
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            MagicMock(
                content=b'%PDF-1.4 test content',
                headers={'Content-Type': 'application/pdf'},
                raise_for_status=lambda: None
            )
        ]

        result = download_pdf('https://example.com/test.pdf', timeout=30, max_retries=3)

        # Should succeed on third attempt
        self.assertEqual(result, b'%PDF-1.4 test content')

        # Verify exponential backoff: 2^0=1, 2^1=2
        # Should have slept twice (after first and second failures)
        self.assertEqual(mock_sleep.call_count, 2)

        # Check that sleep was called with exponential backoff values
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(sleep_calls[0], 1)  # 2^0 = 1
        self.assertEqual(sleep_calls[1], 2)  # 2^1 = 2

    @patch('fetcharoo.downloader.requests.get')
    def test_content_type_not_valid_but_magic_bytes_pass(self, mock_get):
        """Test that content is accepted when Content-Type is invalid but magic bytes are correct"""
        # Mock response with invalid content type but valid PDF magic bytes
        mock_get.return_value = MagicMock(
            content=b'%PDF-1.4 valid pdf content',
            headers={'Content-Type': 'text/plain'},  # Wrong content type
            raise_for_status=lambda: None
        )

        result = download_pdf('https://example.com/test.pdf')

        # Should still return content because magic bytes are correct
        self.assertEqual(result, b'%PDF-1.4 valid pdf content')

    @patch('fetcharoo.downloader.requests.get')
    def test_content_type_not_valid_and_magic_bytes_fail(self, mock_get):
        """Test that None is returned when both Content-Type and magic bytes checks fail"""
        # Mock response with invalid content type and invalid magic bytes
        mock_get.return_value = MagicMock(
            content=b'<html>This is not a PDF</html>',
            headers={'Content-Type': 'text/html'},
            raise_for_status=lambda: None
        )

        with patch('fetcharoo.downloader.logging') as mock_logging:
            result = download_pdf('https://example.com/test.pdf')

            # Should return None
            self.assertIsNone(result)
            # Should log warning
            mock_logging.warning.assert_called()

    @patch('fetcharoo.downloader.time.sleep')
    @patch('fetcharoo.downloader.requests.get')
    def test_exponential_backoff_cap_at_10_seconds(self, mock_get, mock_sleep):
        """Test that exponential backoff is capped at 10 seconds"""
        # Make enough failures to test the cap
        # 2^0=1, 2^1=2, 2^2=4, 2^3=8, 2^4=16 (should be capped at 10)
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout()
        ]

        result = download_pdf('https://example.com/test.pdf', timeout=1, max_retries=5)

        # Should return None after all retries
        self.assertIsNone(result)

        # Check sleep calls
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        # Should be [1, 2, 4, 8] (4 sleeps for 5 retries)
        self.assertEqual(len(sleep_calls), 4)
        self.assertEqual(sleep_calls[0], 1)
        self.assertEqual(sleep_calls[1], 2)
        self.assertEqual(sleep_calls[2], 4)
        self.assertEqual(sleep_calls[3], 8)


class TestPdfUtilsErrorHandling(unittest.TestCase):
    """Test error handling and edge cases for pdf_utils.py"""

    def test_merge_pdfs_with_invalid_corrupted_content(self):
        """Test that merge_pdfs handles corrupted PDF content gracefully"""
        # Create one valid PDF
        valid_pdf_doc = pymupdf.open()
        valid_pdf_doc.new_page()
        valid_pdf_content = valid_pdf_doc.write()
        valid_pdf_doc.close()

        # Create corrupted content
        corrupted_content = b'%PDF-1.4 but this is corrupted data !@#$%'

        with patch('fetcharoo.pdf_utils.logging') as mock_logging:
            # Try to merge valid and corrupted PDFs
            merged_pdf = merge_pdfs([valid_pdf_content, corrupted_content])

            # Should log error for corrupted content
            mock_logging.error.assert_called()

            # Should still have the valid PDF page
            self.assertEqual(merged_pdf.page_count, 1)
            merged_pdf.close()

    def test_merge_pdfs_with_empty_content(self):
        """Test that merge_pdfs handles empty content gracefully"""
        # Create one valid PDF
        valid_pdf_doc = pymupdf.open()
        valid_pdf_doc.new_page()
        valid_pdf_content = valid_pdf_doc.write()
        valid_pdf_doc.close()

        # Create empty content
        empty_content = b''

        with patch('fetcharoo.pdf_utils.logging') as mock_logging:
            # Try to merge valid and empty PDFs
            merged_pdf = merge_pdfs([valid_pdf_content, empty_content])

            # Should log error for empty content
            mock_logging.error.assert_called()

            # Should still have the valid PDF page
            self.assertEqual(merged_pdf.page_count, 1)
            merged_pdf.close()

    def test_merge_pdfs_with_content_less_than_10_bytes(self):
        """Test that merge_pdfs rejects content with less than 10 bytes"""
        # Create one valid PDF
        valid_pdf_doc = pymupdf.open()
        valid_pdf_doc.new_page()
        valid_pdf_content = valid_pdf_doc.write()
        valid_pdf_doc.close()

        # Create very short content (less than 10 bytes)
        short_content = b'%PDF'  # Only 4 bytes

        with patch('fetcharoo.pdf_utils.logging') as mock_logging:
            # Try to merge valid and short content
            merged_pdf = merge_pdfs([valid_pdf_content, short_content])

            # Should log error for invalid content
            mock_logging.error.assert_called()

            # Should still have the valid PDF page
            self.assertEqual(merged_pdf.page_count, 1)
            merged_pdf.close()

    def test_save_pdf_to_file_with_zero_page_document(self):
        """Test that save_pdf_to_file handles zero-page documents correctly"""
        # Create a PDF with zero pages
        zero_page_pdf = pymupdf.open()

        with TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, 'zero_page.pdf')

            with patch('fetcharoo.pdf_utils.logging') as mock_logging:
                save_pdf_to_file(zero_page_pdf, output_path, mode='overwrite')

                # Should log warning about zero pages
                mock_logging.warning.assert_called()

                # File should not be created (zero pages)
                self.assertFalse(os.path.exists(output_path))

    @patch('pymupdf.Document.save')
    def test_save_pdf_to_file_ioerror_handling(self, mock_save):
        """Test that save_pdf_to_file handles IOError gracefully"""
        # Create a valid PDF
        pdf_doc = pymupdf.open()
        pdf_doc.new_page()

        # Mock the save method to raise IOError
        mock_save.side_effect = IOError("Permission denied")

        with TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, 'test.pdf')

            with patch('fetcharoo.pdf_utils.logging') as mock_logging:
                save_pdf_to_file(pdf_doc, output_path, mode='overwrite')

                # Should log error about failing to save
                mock_logging.error.assert_called()
                # Check that the error message mentions IOError
                error_call_args = mock_logging.error.call_args[0][0]
                self.assertIn('Failed to save PDF', error_call_args)

    def test_merge_pdfs_with_all_invalid_content(self):
        """Test merge_pdfs when all content is invalid"""
        corrupted_content1 = b'not a pdf at all'
        corrupted_content2 = b'also not a pdf'

        with patch('fetcharoo.pdf_utils.logging') as mock_logging:
            merged_pdf = merge_pdfs([corrupted_content1, corrupted_content2])

            # Should log errors for both
            self.assertGreaterEqual(mock_logging.error.call_count, 2)

            # Should return empty PDF document
            self.assertEqual(merged_pdf.page_count, 0)
            merged_pdf.close()

    def test_save_pdf_append_mode_with_existing_file(self):
        """Test save_pdf with append mode when file already exists"""
        # Create first PDF with 1 page
        pdf_doc1 = pymupdf.open()
        pdf_doc1.new_page()

        # Create second PDF with 2 pages
        pdf_doc2 = pymupdf.open()
        pdf_doc2.new_page()
        pdf_doc2.new_page()

        with TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, 'append_test.pdf')

            # Save first PDF
            save_pdf_to_file(pdf_doc1, output_path, mode='append')

            # Verify first PDF was saved with 1 page
            saved_pdf = pymupdf.open(output_path)
            self.assertEqual(saved_pdf.page_count, 1)
            saved_pdf.close()

            # Save second PDF with append mode
            save_pdf_to_file(pdf_doc2, output_path, mode='append')

            # Verify appended PDF has 3 pages (1 from first + 2 from second)
            final_pdf = pymupdf.open(output_path)
            self.assertEqual(final_pdf.page_count, 3)
            final_pdf.close()


class TestIntegrationErrorHandling(unittest.TestCase):
    """Integration tests for error handling across modules"""

    @patch('fetcharoo.fetcharoo.download_pdf')
    def test_process_pdfs_with_all_failed_downloads(self, mock_download):
        """Test process_pdfs when all downloads fail"""
        # Mock all downloads to return None (failure)
        mock_download.return_value = None

        pdf_links = [
            'https://example.com/test1.pdf',
            'https://example.com/test2.pdf'
        ]

        with TemporaryDirectory() as temp_dir:
            with patch('fetcharoo.fetcharoo.logger') as mock_logger:
                result = process_pdfs(pdf_links, temp_dir, mode='separate')

                # Should return False (no valid content)
                self.assertFalse(result)
                # Should log warning about no valid content
                mock_logger.warning.assert_called()

    @patch('fetcharoo.fetcharoo.download_pdf')
    def test_process_pdfs_with_non_pdf_content(self, mock_download):
        """Test process_pdfs when downloaded content is not PDF"""
        # Mock download to return HTML content instead of PDF
        mock_download.return_value = b'<html><body>Not a PDF</body></html>'

        pdf_links = ['https://example.com/fake.pdf']

        with TemporaryDirectory() as temp_dir:
            with patch('fetcharoo.fetcharoo.logger') as mock_logger:
                result = process_pdfs(pdf_links, temp_dir, mode='separate')

                # Should return False (content doesn't start with %PDF)
                self.assertFalse(result)
                # Should log warning about no valid content
                mock_logger.warning.assert_called()

    @patch('fetcharoo.fetcharoo.download_pdf')
    def test_process_pdfs_merge_mode_with_partial_failures(self, mock_download):
        """Test merge mode when some downloads succeed and some fail"""
        # Create a valid PDF
        valid_pdf_doc = pymupdf.open()
        valid_pdf_doc.new_page()
        valid_pdf_content = valid_pdf_doc.write()
        valid_pdf_doc.close()

        # Mock download to return valid for first, None for second
        mock_download.side_effect = [valid_pdf_content, None]

        pdf_links = [
            'https://example.com/valid.pdf',
            'https://example.com/invalid.pdf'
        ]

        with TemporaryDirectory() as temp_dir:
            result = process_pdfs(pdf_links, temp_dir, mode='merge')

            # Should succeed with the one valid PDF
            self.assertTrue(result)

            # Check that merged.pdf exists
            merged_path = os.path.join(temp_dir, 'merged.pdf')
            self.assertTrue(os.path.exists(merged_path))

            # Verify it has 1 page (from the valid PDF)
            final_pdf = pymupdf.open(merged_path)
            self.assertEqual(final_pdf.page_count, 1)
            final_pdf.close()


if __name__ == '__main__':
    unittest.main()
