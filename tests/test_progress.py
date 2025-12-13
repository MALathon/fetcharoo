import unittest
from unittest.mock import patch, MagicMock
from fetcharoo.fetcharoo import download_pdfs_from_webpage, process_pdfs, find_pdfs_from_webpage


class TestProgressBars(unittest.TestCase):
    """Test progress bar functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_url = 'https://example.com/test.html'
        self.test_pdf_links = [
            'https://example.com/test1.pdf',
            'https://example.com/test2.pdf',
            'https://example.com/test3.pdf'
        ]
        self.valid_pdf_content = b'%PDF-1.4 test content'

    @patch('fetcharoo.fetcharoo.process_pdfs')
    @patch('fetcharoo.fetcharoo.find_pdfs_from_webpage')
    def test_show_progress_false_by_default(self, mock_find_pdfs, mock_process_pdfs):
        """Test that show_progress defaults to False and no progress bar is shown."""
        mock_find_pdfs.return_value = self.test_pdf_links
        mock_process_pdfs.return_value = True

        # Call without show_progress parameter - should default to False
        result = download_pdfs_from_webpage(self.test_url)

        # Verify process_pdfs was called with show_progress=False (default)
        mock_process_pdfs.assert_called_once()
        call_kwargs = mock_process_pdfs.call_args[1]
        self.assertEqual(call_kwargs.get('show_progress', False), False)

    @patch('fetcharoo.fetcharoo.process_pdfs')
    @patch('fetcharoo.fetcharoo.find_pdfs_from_webpage')
    def test_show_progress_explicit_false(self, mock_find_pdfs, mock_process_pdfs):
        """Test that show_progress=False doesn't show progress bar."""
        mock_find_pdfs.return_value = self.test_pdf_links
        mock_process_pdfs.return_value = True

        # Call with show_progress=False explicitly
        result = download_pdfs_from_webpage(self.test_url, show_progress=False)

        # Verify process_pdfs was called with show_progress=False
        mock_process_pdfs.assert_called_once()
        call_kwargs = mock_process_pdfs.call_args[1]
        self.assertEqual(call_kwargs.get('show_progress'), False)

    @patch('fetcharoo.fetcharoo.tqdm')
    @patch('fetcharoo.fetcharoo.save_pdf_to_file')
    @patch('fetcharoo.fetcharoo.pymupdf.Document')
    @patch('fetcharoo.fetcharoo.download_pdf')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_show_progress_true_uses_tqdm(self, mock_exists, mock_makedirs, mock_download_pdf,
                                          mock_document, mock_save_pdf, mock_tqdm):
        """Test that show_progress=True uses tqdm progress bar."""
        mock_exists.return_value = False
        mock_download_pdf.return_value = self.valid_pdf_content
        mock_document.return_value = MagicMock()
        mock_tqdm.return_value = iter(self.test_pdf_links)

        # Call with show_progress=True
        result = process_pdfs(self.test_pdf_links, mode='separate', show_progress=True)

        # Verify tqdm was called with the PDF links
        mock_tqdm.assert_called_once()
        self.assertTrue(result)

    @patch('fetcharoo.fetcharoo.tqdm')
    @patch('fetcharoo.fetcharoo.save_pdf_to_file')
    @patch('fetcharoo.fetcharoo.pymupdf.Document')
    @patch('fetcharoo.fetcharoo.download_pdf')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_show_progress_false_does_not_use_tqdm(self, mock_exists, mock_makedirs, mock_download_pdf,
                                                    mock_document, mock_save_pdf, mock_tqdm):
        """Test that show_progress=False does not use tqdm."""
        mock_exists.return_value = False
        mock_download_pdf.return_value = self.valid_pdf_content
        mock_document.return_value = MagicMock()

        # Call with show_progress=False
        result = process_pdfs(self.test_pdf_links, mode='separate', show_progress=False)

        # Verify tqdm was NOT called
        mock_tqdm.assert_not_called()
        self.assertTrue(result)

    @patch('fetcharoo.fetcharoo.tqdm')
    @patch('fetcharoo.fetcharoo.save_pdf_to_file')
    @patch('fetcharoo.fetcharoo.pymupdf.Document')
    @patch('fetcharoo.fetcharoo.download_pdf')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_progress_updates_during_download(self, mock_exists, mock_makedirs, mock_download_pdf,
                                               mock_document, mock_save_pdf, mock_tqdm):
        """Test that progress bar updates during PDF downloads."""
        mock_exists.return_value = False
        mock_download_pdf.return_value = self.valid_pdf_content
        mock_document.return_value = MagicMock()
        mock_tqdm.return_value = iter(self.test_pdf_links)

        # Call with show_progress=True
        result = process_pdfs(self.test_pdf_links, mode='separate', show_progress=True)

        # Verify the download was successful
        self.assertTrue(result)
        # Verify that downloads happened for each PDF
        self.assertEqual(mock_download_pdf.call_count, len(self.test_pdf_links))

    @patch('fetcharoo.fetcharoo.logging')
    @patch('fetcharoo.fetcharoo.requests.get')
    def test_find_pdfs_progress_with_show_progress_true(self, mock_get, mock_logging):
        """Test that find_pdfs_from_webpage shows progress when show_progress=True."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.text = '''
            <html>
                <body>
                    <a href="test1.pdf">PDF 1</a>
                    <a href="test2.pdf">PDF 2</a>
                </body>
            </html>
        '''
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Call with show_progress=True
        result = find_pdfs_from_webpage(self.test_url, show_progress=True)

        # Should find PDFs
        self.assertEqual(len(result), 2)
        # Should log finding progress
        mock_logging.info.assert_called()

    @patch('fetcharoo.fetcharoo.process_pdfs')
    @patch('fetcharoo.fetcharoo.find_pdfs_from_webpage')
    def test_download_pdfs_from_webpage_propagates_show_progress(self, mock_find_pdfs, mock_process_pdfs):
        """Test that download_pdfs_from_webpage propagates show_progress to both functions."""
        mock_find_pdfs.return_value = self.test_pdf_links
        mock_process_pdfs.return_value = True

        # Call with show_progress=True
        result = download_pdfs_from_webpage(self.test_url, show_progress=True)

        # Verify both functions were called with show_progress=True
        call_kwargs = mock_find_pdfs.call_args[1]
        self.assertEqual(call_kwargs.get('show_progress'), True)

        call_kwargs = mock_process_pdfs.call_args[1]
        self.assertEqual(call_kwargs.get('show_progress'), True)

    @patch('fetcharoo.fetcharoo.tqdm')
    @patch('fetcharoo.fetcharoo.save_pdf_to_file')
    @patch('fetcharoo.fetcharoo.merge_pdfs')
    @patch('fetcharoo.fetcharoo.download_pdf')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_process_pdfs_merge_mode_with_progress(self, mock_exists, mock_makedirs, mock_download_pdf,
                                                     mock_merge_pdfs, mock_save_pdf, mock_tqdm):
        """Test that progress bar works in merge mode."""
        mock_exists.return_value = False
        mock_download_pdf.return_value = self.valid_pdf_content
        mock_merge_pdfs.return_value = MagicMock()
        mock_tqdm.return_value = iter(self.test_pdf_links)

        # Call with show_progress=True in merge mode
        result = process_pdfs(self.test_pdf_links, mode='merge', show_progress=True)

        # Verify success and tqdm was used
        self.assertTrue(result)
        mock_tqdm.assert_called_once()

    def test_empty_pdf_links_with_progress(self):
        """Test that empty PDF links list handles progress gracefully."""
        # Call with empty list
        result = process_pdfs([], show_progress=True)

        # Should return False (no PDFs to process)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
