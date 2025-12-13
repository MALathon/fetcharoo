"""Tests for User-Agent customization functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import fetcharoo
from fetcharoo import (
    find_pdfs_from_webpage,
    download_pdfs_from_webpage,
    set_default_user_agent,
    get_default_user_agent,
)
from fetcharoo.downloader import download_pdf


class TestDefaultUserAgent:
    """Test default User-Agent behavior."""

    def test_default_user_agent_is_descriptive(self):
        """Test that the default user agent identifies the bot properly."""
        default_ua = get_default_user_agent()
        assert "fetcharoo" in default_ua.lower()
        assert "0.2.0" in default_ua
        assert "github.com/MALathon/fetcharoo" in default_ua

    def test_default_user_agent_format(self):
        """Test that the default user agent follows the expected format."""
        default_ua = get_default_user_agent()
        # Format: "fetcharoo/0.2.0 (+https://github.com/MALathon/fetcharoo)"
        assert default_ua == "fetcharoo/0.2.0 (+https://github.com/MALathon/fetcharoo)"


class TestSetDefaultUserAgent:
    """Test setting default User-Agent."""

    def test_set_default_user_agent_changes_default(self):
        """Test that set_default_user_agent changes the default."""
        original_ua = get_default_user_agent()
        custom_ua = "MyCustomBot/1.0"

        try:
            set_default_user_agent(custom_ua)
            assert get_default_user_agent() == custom_ua
        finally:
            # Restore original default
            set_default_user_agent(original_ua)

    def test_set_default_user_agent_persists_across_calls(self):
        """Test that the custom default persists across multiple function calls."""
        original_ua = get_default_user_agent()
        custom_ua = "PersistentBot/2.0"

        try:
            set_default_user_agent(custom_ua)
            # Multiple calls should all return the same custom UA
            assert get_default_user_agent() == custom_ua
            assert get_default_user_agent() == custom_ua
        finally:
            set_default_user_agent(original_ua)


class TestFindPdfsUserAgent:
    """Test User-Agent in find_pdfs_from_webpage."""

    @patch('fetcharoo.fetcharoo.requests.get')
    def test_find_pdfs_uses_default_user_agent(self, mock_get):
        """Test that find_pdfs_from_webpage uses the default user agent."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><a href="test.pdf">PDF</a></body></html>'
        mock_get.return_value = mock_response

        find_pdfs_from_webpage("https://example.com")

        # Check that the default user agent was used
        call_args = mock_get.call_args
        headers = call_args.kwargs.get('headers', {})
        assert 'User-Agent' in headers
        assert headers['User-Agent'] == "fetcharoo/0.2.0 (+https://github.com/MALathon/fetcharoo)"

    @patch('fetcharoo.fetcharoo.requests.get')
    def test_find_pdfs_accepts_custom_user_agent(self, mock_get):
        """Test that find_pdfs_from_webpage accepts a custom user agent parameter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><a href="test.pdf">PDF</a></body></html>'
        mock_get.return_value = mock_response

        custom_ua = "CustomBot/3.0 (+https://example.com/bot)"
        find_pdfs_from_webpage("https://example.com", user_agent=custom_ua)

        # Check that the custom user agent was used
        call_args = mock_get.call_args
        headers = call_args.kwargs.get('headers', {})
        assert headers['User-Agent'] == custom_ua

    @patch('fetcharoo.fetcharoo.requests.get')
    def test_find_pdfs_custom_overrides_default(self, mock_get):
        """Test that custom user agent parameter overrides the default."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><a href="test.pdf">PDF</a></body></html>'
        mock_get.return_value = mock_response

        original_ua = get_default_user_agent()
        try:
            # Set a default
            set_default_user_agent("DefaultBot/1.0")

            # Use a custom one that should override
            custom_ua = "OverrideBot/1.0"
            find_pdfs_from_webpage("https://example.com", user_agent=custom_ua)

            # Check that the custom (not default) was used
            call_args = mock_get.call_args
            headers = call_args.kwargs.get('headers', {})
            assert headers['User-Agent'] == custom_ua
            assert headers['User-Agent'] != "DefaultBot/1.0"
        finally:
            set_default_user_agent(original_ua)

    @patch('fetcharoo.fetcharoo.requests.get')
    def test_find_pdfs_recursive_propagates_user_agent(self, mock_get):
        """Test that user agent is propagated in recursive calls."""
        # Mock responses for both initial page and linked page
        mock_response_1 = Mock()
        mock_response_1.status_code = 200
        mock_response_1.text = '<html><body><a href="https://example.com/page2">Link</a></body></html>'

        mock_response_2 = Mock()
        mock_response_2.status_code = 200
        mock_response_2.text = '<html><body><a href="test.pdf">PDF</a></body></html>'

        mock_get.side_effect = [mock_response_1, mock_response_2]

        custom_ua = "RecursiveBot/1.0"
        find_pdfs_from_webpage(
            "https://example.com",
            recursion_depth=1,
            user_agent=custom_ua
        )

        # Check that all requests used the custom user agent
        assert mock_get.call_count >= 2
        for call in mock_get.call_args_list:
            headers = call.kwargs.get('headers', {})
            assert headers['User-Agent'] == custom_ua


class TestDownloadPdfsUserAgent:
    """Test User-Agent in download_pdfs_from_webpage."""

    @patch('fetcharoo.downloader.requests.get')
    @patch('fetcharoo.fetcharoo.requests.get')
    @patch('fetcharoo.fetcharoo.BeautifulSoup')
    def test_download_pdfs_uses_default_user_agent(self, mock_soup, mock_find_get, mock_download_get):
        """Test that download_pdfs_from_webpage uses the default user agent."""
        # Mock the webpage fetch
        mock_page_response = Mock()
        mock_page_response.status_code = 200
        mock_page_response.text = '<html><body><a href="https://example.com/test.pdf">PDF</a></body></html>'
        mock_find_get.return_value = mock_page_response

        # Mock BeautifulSoup to return PDFs
        mock_anchor = Mock()
        mock_anchor.__getitem__ = Mock(return_value='https://example.com/test.pdf')
        mock_soup_instance = Mock()
        mock_soup_instance.find_all.return_value = [mock_anchor]
        mock_soup.return_value = mock_soup_instance

        # Mock the PDF download
        mock_pdf_response = Mock()
        mock_pdf_response.status_code = 200
        mock_pdf_response.content = b'%PDF-1.4 fake pdf content'
        mock_pdf_response.headers = {'Content-Type': 'application/pdf'}
        mock_download_get.return_value = mock_pdf_response

        download_pdfs_from_webpage("https://example.com", write_dir="/tmp/test_pdfs")

        # Check that both requests used the default user agent
        for call in mock_find_get.call_args_list:
            headers = call.kwargs.get('headers', {})
            assert headers['User-Agent'] == "fetcharoo/0.2.0 (+https://github.com/MALathon/fetcharoo)"

        for call in mock_download_get.call_args_list:
            headers = call.kwargs.get('headers', {})
            assert headers['User-Agent'] == "fetcharoo/0.2.0 (+https://github.com/MALathon/fetcharoo)"

    @patch('fetcharoo.downloader.requests.get')
    @patch('fetcharoo.fetcharoo.requests.get')
    @patch('fetcharoo.fetcharoo.BeautifulSoup')
    def test_download_pdfs_accepts_custom_user_agent(self, mock_soup, mock_find_get, mock_download_get):
        """Test that download_pdfs_from_webpage accepts a custom user agent."""
        # Mock the webpage fetch
        mock_page_response = Mock()
        mock_page_response.status_code = 200
        mock_page_response.text = '<html><body><a href="https://example.com/test.pdf">PDF</a></body></html>'
        mock_find_get.return_value = mock_page_response

        # Mock BeautifulSoup to return PDFs
        mock_anchor = Mock()
        mock_anchor.__getitem__ = Mock(return_value='https://example.com/test.pdf')
        mock_soup_instance = Mock()
        mock_soup_instance.find_all.return_value = [mock_anchor]
        mock_soup.return_value = mock_soup_instance

        # Mock the PDF download
        mock_pdf_response = Mock()
        mock_pdf_response.status_code = 200
        mock_pdf_response.content = b'%PDF-1.4 fake pdf content'
        mock_pdf_response.headers = {'Content-Type': 'application/pdf'}
        mock_download_get.return_value = mock_pdf_response

        custom_ua = "CustomDownloader/4.0"
        download_pdfs_from_webpage(
            "https://example.com",
            write_dir="/tmp/test_pdfs",
            user_agent=custom_ua
        )

        # Check that both webpage and PDF requests used custom user agent
        for call in mock_find_get.call_args_list:
            headers = call.kwargs.get('headers', {})
            assert headers['User-Agent'] == custom_ua

        for call in mock_download_get.call_args_list:
            headers = call.kwargs.get('headers', {})
            assert headers['User-Agent'] == custom_ua


class TestDownloadPdfUserAgent:
    """Test User-Agent in download_pdf."""

    @patch('fetcharoo.downloader.requests.get')
    def test_download_pdf_uses_default_user_agent(self, mock_get):
        """Test that download_pdf uses the default user agent."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'%PDF-1.4 fake pdf content'
        mock_response.headers = {'Content-Type': 'application/pdf'}
        mock_get.return_value = mock_response

        download_pdf("https://example.com/test.pdf")

        call_args = mock_get.call_args
        headers = call_args.kwargs.get('headers', {})
        assert headers['User-Agent'] == "fetcharoo/0.2.0 (+https://github.com/MALathon/fetcharoo)"

    @patch('fetcharoo.downloader.requests.get')
    def test_download_pdf_accepts_custom_user_agent(self, mock_get):
        """Test that download_pdf accepts a custom user agent parameter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'%PDF-1.4 fake pdf content'
        mock_response.headers = {'Content-Type': 'application/pdf'}
        mock_get.return_value = mock_response

        custom_ua = "PDFDownloader/5.0"
        download_pdf("https://example.com/test.pdf", user_agent=custom_ua)

        call_args = mock_get.call_args
        headers = call_args.kwargs.get('headers', {})
        assert headers['User-Agent'] == custom_ua

    @patch('fetcharoo.downloader.requests.get')
    def test_download_pdf_retries_use_same_user_agent(self, mock_get):
        """Test that retries use the same custom user agent."""
        # First call fails with timeout, second succeeds
        from requests.exceptions import Timeout

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.content = b'%PDF-1.4 fake pdf content'
        mock_response_success.headers = {'Content-Type': 'application/pdf'}

        mock_get.side_effect = [Timeout("Timeout error"), mock_response_success]

        custom_ua = "RetryBot/1.0"
        download_pdf("https://example.com/test.pdf", user_agent=custom_ua)

        # Both attempts should use the custom user agent
        assert mock_get.call_count == 2
        for call in mock_get.call_args_list:
            headers = call.kwargs.get('headers', {})
            assert headers['User-Agent'] == custom_ua
