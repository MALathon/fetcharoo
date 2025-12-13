import os
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
import pymupdf
import responses
from fetcharoo.fetcharoo import find_pdfs_from_webpage, process_pdfs, download_pdfs_from_webpage, is_valid_url

class Testfetcharoo(unittest.TestCase):
    def setUp(self):
        # Create a small PDF document in memory and use its binary content as the mock content
        pdf_doc = pymupdf.open()
        pdf_doc.new_page()
        self.mock_pdf_content = pdf_doc.write()  # Use the binary content directly
        pdf_doc.close()

    def test_is_valid_url(self):
        self.assertTrue(is_valid_url('https://example.com'))
        self.assertFalse(is_valid_url('invalid_url'))

    @patch('fetcharoo.fetcharoo.download_pdf')
    def test_process_pdfs_merge_mode(self, mock_download_pdf):
        # Mock the download_pdf function to return the mock PDF content
        mock_download_pdf.return_value = self.mock_pdf_content

        # Define sample PDF links
        pdf_links = ['https://example.com/test1.pdf', 'https://example.com/test2.pdf']

        # Create a temporary directory for testing
        with TemporaryDirectory() as temp_dir:
            # Test the process_pdfs function in 'merge' mode
            process_pdfs(pdf_links, temp_dir, mode='merge')

            # Check that the merged PDF file exists
            merged_pdf_path = os.path.join(temp_dir, 'merged.pdf')
            self.assertTrue(os.path.exists(merged_pdf_path))

    @patch('fetcharoo.fetcharoo.download_pdf')
    def test_process_pdfs_separate_mode(self, mock_download_pdf):
        # Mock the download_pdf function to return the mock PDF content
        mock_download_pdf.return_value = self.mock_pdf_content

        # Define sample PDF links
        pdf_links = ['https://example.com/test1.pdf', 'https://example.com/test2.pdf']

        # Create a temporary directory for testing
        with TemporaryDirectory() as temp_dir:
            # Test the process_pdfs function in 'separate' mode
            process_pdfs(pdf_links, temp_dir, mode='separate')

            # Check that the individual PDF files exist
            for pdf_link in pdf_links:
                pdf_file_name = os.path.basename(pdf_link)
                pdf_file_path = os.path.join(temp_dir, pdf_file_name)
                self.assertTrue(os.path.exists(pdf_file_path))

    @patch('fetcharoo.fetcharoo.find_pdfs_from_webpage')
    @patch('fetcharoo.fetcharoo.process_pdfs')
    def test_download_pdfs_from_webpage(self, mock_process_pdfs, mock_find_pdfs_from_webpage):
        # Mock the find_pdfs_from_webpage function to return sample PDF links
        mock_find_pdfs_from_webpage.return_value = ['https://example.com/test1.pdf', 'https://example.com/test2.pdf']

        # Test the download_pdfs_from_webpage function
        download_pdfs_from_webpage(url='https://example.com', recursion_depth=1, mode='merge', write_dir='output')

        # Check that the find_pdfs_from_webpage and process_pdfs functions were called
        mock_find_pdfs_from_webpage.assert_called_once()
        mock_process_pdfs.assert_called_once()

    @responses.activate
    def test_find_pdfs_from_webpage(self):
        # Define a sample HTML content with PDF links
        html_content ="""
        <html>
            <body>
                <a href="https://example.com/test1.pdf">Test PDF 1</a>
                <a href="https://example.com/test2.pdf">Test PDF 2</a>
                <a href="https://example.com/subpage.html">Subpage</a>
            </body>
        </html>"""

        # Define a sample HTML content for the subpage with a PDF link
        subpage_html_content = """
        <html>
            <body>
                <a href="https://example.com/test3.pdf">Test PDF 3</a>
            </body>
        </html>
        """

        # Mock the HTTP responses for the main page and the subpage
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)
        responses.add(responses.GET, 'https://example.com/subpage.html', body=subpage_html_content, status=200)

        # Test the find_pdfs_from_webpage function with recursion depth 0
        pdf_links = find_pdfs_from_webpage(url='https://example.com', recursion_depth=0)
        self.assertEqual(pdf_links, ['https://example.com/test1.pdf', 'https://example.com/test2.pdf'])

        # Test the find_pdfs_from_webpage function with recursion depth 1
        pdf_links_recursive = find_pdfs_from_webpage(url='https://example.com', recursion_depth=1)
        self.assertEqual(pdf_links_recursive, ['https://example.com/test1.pdf', 'https://example.com/test2.pdf', 'https://example.com/test3.pdf'])

    @responses.activate
    def test_find_pdfs_from_webpage_invalid_url(self):
        # Define an invalid URL
        invalid_url = 'invalid_url'

        # Test the find_pdfs_from_webpage function with an invalid URL
        pdf_links = find_pdfs_from_webpage(url=invalid_url, recursion_depth=0)
        self.assertEqual(pdf_links, [])

    @responses.activate
    def test_find_pdfs_from_webpage_cyclic_links(self):
        # Define URLs for testing
        base_url = 'https://example.com/'
        subpage1_url = 'https://example.com/subpage1'
        subpage2_url = 'https://example.com/subpage2'
        pdf_url = 'https://example.com/sample.pdf'

        # Mock the base URL response
        responses.add(
            responses.GET,
            base_url,
            body=f'<a href="{subpage1_url}">Subpage 1</a>',
            status=200,
            content_type='text/html',
        )

        # Mock the subpage1 URL response (contains a link to subpage2 and a PDF link)
        responses.add(
            responses.GET,
            subpage1_url,
            body=f'<a href="{subpage2_url}">Subpage 2</a><a href="{pdf_url}">PDF</a>',
            status=200,
            content_type='text/html',
        )

        # Mock the subpage2 URL response (contains a link back to subpage1)
        responses.add(
            responses.GET,
            subpage2_url,
            body=f'<a href="{subpage1_url}">Subpage 1</a>',
            status=200,
            content_type='text/html',
        )

        # Call the find_pdfs_from_webpage function with recursion_depth=2
        pdf_links = find_pdfs_from_webpage(base_url, recursion_depth=2)

        # Check that the PDF link is found and that there are no duplicates
        self.assertEqual(pdf_links, [pdf_url])

if __name__ == '__main__':
    unittest.main()