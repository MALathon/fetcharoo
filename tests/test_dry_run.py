import os
import unittest
from unittest.mock import patch, MagicMock
from tempfile import TemporaryDirectory
import pymupdf
import responses
from fetcharoo.fetcharoo import download_pdfs_from_webpage, find_pdfs_from_webpage


class TestDryRunMode(unittest.TestCase):
    """Test suite for dry-run mode functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a small PDF document in memory for testing
        pdf_doc = pymupdf.open()
        pdf_doc.new_page()
        self.mock_pdf_content = pdf_doc.write()
        pdf_doc.close()

    @responses.activate
    @patch('fetcharoo.fetcharoo.download_pdf')
    def test_dry_run_returns_urls_without_downloading(self, mock_download_pdf):
        """Test that dry_run=True returns URLs but doesn't download files."""
        # Set up mock HTML with PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/test1.pdf">Test PDF 1</a>
                <a href="https://example.com/test2.pdf">Test PDF 2</a>
            </body>
        </html>
        """
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        # Call with dry_run=True
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url='https://example.com',
                recursion_depth=0,
                mode='separate',
                write_dir=temp_dir,
                dry_run=True
            )

            # Assert the result is a dict with urls and count
            self.assertIsInstance(result, dict)
            self.assertIn('urls', result)
            self.assertIn('count', result)

            # Assert correct URLs are returned
            expected_urls = ['https://example.com/test1.pdf', 'https://example.com/test2.pdf']
            self.assertEqual(result['urls'], expected_urls)
            self.assertEqual(result['count'], 2)

            # Assert download_pdf was NOT called
            mock_download_pdf.assert_not_called()

    @responses.activate
    @patch('fetcharoo.fetcharoo.download_pdf')
    def test_dry_run_does_not_create_files(self, mock_download_pdf):
        """Test that dry_run=True doesn't create any files."""
        # Set up mock HTML with PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/document.pdf">Document</a>
            </body>
        </html>
        """
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        # Call with dry_run=True
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url='https://example.com',
                recursion_depth=0,
                mode='separate',
                write_dir=temp_dir,
                dry_run=True
            )

            # Assert no files were created in the temp directory
            files_in_dir = os.listdir(temp_dir)
            self.assertEqual(len(files_in_dir), 0, "No files should be created in dry-run mode")

            # Assert download_pdf was NOT called
            mock_download_pdf.assert_not_called()

    @responses.activate
    @patch('fetcharoo.fetcharoo.download_pdf')
    def test_dry_run_false_still_downloads_normally(self, mock_download_pdf):
        """Test that dry_run=False (or not specified) still works normally."""
        # Mock download_pdf to return PDF content
        mock_download_pdf.return_value = self.mock_pdf_content

        # Set up mock HTML with PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/test.pdf">Test PDF</a>
            </body>
        </html>
        """
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        # Call with dry_run=False
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url='https://example.com',
                recursion_depth=0,
                mode='separate',
                write_dir=temp_dir,
                dry_run=False
            )

            # Assert the result is a ProcessResult that evaluates to True
            from fetcharoo import ProcessResult
            self.assertIsInstance(result, ProcessResult)
            self.assertTrue(result)  # Uses __bool__ method
            self.assertTrue(result.success)

            # Assert files were created
            files_in_dir = os.listdir(temp_dir)
            self.assertGreater(len(files_in_dir), 0, "Files should be created when dry_run=False")

            # Assert download_pdf was called
            mock_download_pdf.assert_called()

    @responses.activate
    def test_dry_run_returns_correct_count(self, ):
        """Test that dry_run returns the correct count of PDFs found."""
        # Set up mock HTML with multiple PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/doc1.pdf">Doc 1</a>
                <a href="https://example.com/doc2.pdf">Doc 2</a>
                <a href="https://example.com/doc3.pdf">Doc 3</a>
                <a href="https://example.com/page.html">Not a PDF</a>
            </body>
        </html>
        """
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        # Call with dry_run=True
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url='https://example.com',
                recursion_depth=0,
                mode='separate',
                write_dir=temp_dir,
                dry_run=True
            )

            # Assert correct count
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(result['urls']), 3)

    @responses.activate
    def test_dry_run_with_no_pdfs_found(self):
        """Test that dry_run handles pages with no PDFs correctly."""
        # Set up mock HTML with no PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/page1.html">Page 1</a>
                <a href="https://example.com/page2.html">Page 2</a>
            </body>
        </html>
        """
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        # Call with dry_run=True
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url='https://example.com',
                recursion_depth=0,
                mode='separate',
                write_dir=temp_dir,
                dry_run=True
            )

            # Assert correct empty result
            self.assertEqual(result['count'], 0)
            self.assertEqual(result['urls'], [])

    @responses.activate
    @patch('fetcharoo.fetcharoo.logging')
    def test_dry_run_logs_appropriately(self, mock_logging):
        """Test that dry_run mode logs what would be downloaded."""
        # Set up mock HTML with PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/report.pdf">Report</a>
            </body>
        </html>
        """
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        # Call with dry_run=True
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url='https://example.com',
                recursion_depth=0,
                mode='separate',
                write_dir=temp_dir,
                dry_run=True
            )

            # Assert logging was called with dry-run messages
            # Check that logging.info was called
            self.assertTrue(mock_logging.info.called)

    @responses.activate
    def test_dry_run_with_recursion(self):
        """Test that dry_run works correctly with recursive link following."""
        # Set up mock HTML for main page
        main_html = """
        <html>
            <body>
                <a href="https://example.com/doc1.pdf">Doc 1</a>
                <a href="https://example.com/subpage.html">Subpage</a>
            </body>
        </html>
        """

        # Set up mock HTML for subpage
        subpage_html = """
        <html>
            <body>
                <a href="https://example.com/doc2.pdf">Doc 2</a>
            </body>
        </html>
        """

        responses.add(responses.GET, 'https://example.com', body=main_html, status=200)
        responses.add(responses.GET, 'https://example.com/subpage.html', body=subpage_html, status=200)

        # Call with dry_run=True and recursion_depth=1
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url='https://example.com',
                recursion_depth=1,
                mode='separate',
                write_dir=temp_dir,
                dry_run=True
            )

            # Assert both PDFs are found
            expected_urls = ['https://example.com/doc1.pdf', 'https://example.com/doc2.pdf']
            self.assertEqual(result['urls'], expected_urls)
            self.assertEqual(result['count'], 2)

    @responses.activate
    @patch('fetcharoo.fetcharoo.download_pdf')
    def test_dry_run_with_merge_mode(self, mock_download_pdf):
        """Test that dry_run works with merge mode."""
        # Set up mock HTML with PDF links
        html_content = """
        <html>
            <body>
                <a href="https://example.com/part1.pdf">Part 1</a>
                <a href="https://example.com/part2.pdf">Part 2</a>
            </body>
        </html>
        """
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        # Call with dry_run=True and mode='merge'
        with TemporaryDirectory() as temp_dir:
            result = download_pdfs_from_webpage(
                url='https://example.com',
                recursion_depth=0,
                mode='merge',
                write_dir=temp_dir,
                dry_run=True
            )

            # Assert URLs are returned
            self.assertEqual(result['count'], 2)

            # Assert no files were created (including merged.pdf)
            files_in_dir = os.listdir(temp_dir)
            self.assertEqual(len(files_in_dir), 0)

            # Assert download_pdf was NOT called
            mock_download_pdf.assert_not_called()


if __name__ == '__main__':
    unittest.main()
