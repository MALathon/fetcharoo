"""
Cross-feature integration tests for fetcharoo.

These tests verify that different features work correctly when combined:
- robots.txt + user-agent
- dry-run + filtering
- progress bars + filtering
- robots.txt + progress bars
- All features combined

Author: Mark A. Lifson, Ph.D.
"""

import unittest
from unittest.mock import patch, MagicMock
import responses

from fetcharoo import (
    download_pdfs_from_webpage,
    find_pdfs_from_webpage,
    FilterConfig,
    set_default_user_agent,
    get_default_user_agent,
)


class TestDryRunWithFiltering(unittest.TestCase):
    """Test dry_run mode combined with filtering."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_url = 'https://example.com'

    @responses.activate
    def test_dry_run_applies_filename_filter(self):
        """Test that dry_run mode applies filename filtering."""
        # Mock webpage with multiple PDF links
        html_content = '''
        <html><body>
            <a href="report_2023.pdf">Report 2023</a>
            <a href="draft_report.pdf">Draft Report</a>
            <a href="annual_report.pdf">Annual Report</a>
        </body></html>
        '''
        responses.add(responses.GET, self.test_url, body=html_content, status=200)

        # Filter to only include "report" files, exclude "draft"
        filter_config = FilterConfig(
            filename_include=['*report*.pdf'],
            filename_exclude=['*draft*']
        )

        result = download_pdfs_from_webpage(
            self.test_url,
            dry_run=True,
            filter_config=filter_config
        )

        # Should only return report_2023.pdf and annual_report.pdf
        self.assertEqual(result['count'], 2)
        self.assertIn('https://example.com/report_2023.pdf', result['urls'])
        self.assertIn('https://example.com/annual_report.pdf', result['urls'])
        self.assertNotIn('https://example.com/draft_report.pdf', result['urls'])

    @responses.activate
    def test_dry_run_applies_url_filter(self):
        """Test that dry_run mode applies URL filtering."""
        html_content = '''
        <html><body>
            <a href="/docs/report.pdf">Docs Report</a>
            <a href="/temp/report.pdf">Temp Report</a>
        </body></html>
        '''
        responses.add(responses.GET, self.test_url, body=html_content, status=200)

        # Filter to exclude /temp/ URLs
        filter_config = FilterConfig(
            url_exclude=['*/temp/*']
        )

        result = download_pdfs_from_webpage(
            self.test_url,
            dry_run=True,
            filter_config=filter_config
        )

        self.assertEqual(result['count'], 1)
        self.assertIn('https://example.com/docs/report.pdf', result['urls'])

    @responses.activate
    def test_dry_run_no_filter_returns_all(self):
        """Test that dry_run without filter returns all PDFs."""
        html_content = '''
        <html><body>
            <a href="report1.pdf">Report 1</a>
            <a href="report2.pdf">Report 2</a>
        </body></html>
        '''
        responses.add(responses.GET, self.test_url, body=html_content, status=200)

        result = download_pdfs_from_webpage(
            self.test_url,
            dry_run=True
        )

        self.assertEqual(result['count'], 2)


class TestRobotsTxtWithUserAgent(unittest.TestCase):
    """Test robots.txt compliance with custom user-agent."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_url = 'https://example.com'
        # Save original user agent
        self.original_ua = get_default_user_agent()
        # Clear the robots.txt cache before each test
        from fetcharoo import fetcharoo
        fetcharoo._robots_cache = {}

    def tearDown(self):
        """Restore original user agent."""
        set_default_user_agent(self.original_ua)

    @responses.activate
    def test_robots_uses_custom_user_agent(self):
        """Test that robots.txt check uses the custom user-agent."""
        # Mock robots.txt that blocks default agent but allows custom
        robots_txt = '''
User-agent: fetcharoo
Disallow: /

User-agent: MyCustomBot
Allow: /
'''
        responses.add(responses.GET, 'https://example.com/robots.txt',
                      body=robots_txt, status=200)

        html_content = '<html><body><a href="doc.pdf">PDF</a></body></html>'
        responses.add(responses.GET, self.test_url, body=html_content, status=200)

        # With default user agent and respect_robots, should find the PDF
        # (since robots.txt disallows crawling only for 'fetcharoo' but
        # check_robots_txt uses the provided user_agent for the check)
        result = find_pdfs_from_webpage(
            self.test_url,
            respect_robots=True,
            user_agent='MyCustomBot/1.0'
        )

        # The PDF should be found since MyCustomBot is allowed
        self.assertEqual(len(result), 1)

    @responses.activate
    def test_set_default_user_agent_affects_requests(self):
        """Test that set_default_user_agent affects HTTP requests."""
        html_content = '<html><body><a href="doc.pdf">PDF</a></body></html>'
        responses.add(responses.GET, self.test_url, body=html_content, status=200)

        set_default_user_agent('TestBot/2.0')

        find_pdfs_from_webpage(self.test_url)

        # Verify the request used our custom user agent
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.headers['User-Agent'], 'TestBot/2.0')


class TestProgressWithFiltering(unittest.TestCase):
    """Test progress bars combined with filtering."""

    @responses.activate
    @patch('fetcharoo.fetcharoo.download_pdf')
    @patch('fetcharoo.fetcharoo.save_pdf_to_file')
    @patch('fetcharoo.fetcharoo.pymupdf.Document')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_progress_with_filter_shows_correct_count(
        self, mock_exists, mock_makedirs, mock_document,
        mock_save_pdf, mock_download_pdf
    ):
        """Test that progress shows count after filtering."""
        mock_exists.return_value = False
        mock_download_pdf.return_value = b'%PDF-1.4 test content here'
        mock_document.return_value = MagicMock()

        html_content = '''
        <html><body>
            <a href="report1.pdf">Report 1</a>
            <a href="draft.pdf">Draft</a>
            <a href="report2.pdf">Report 2</a>
        </body></html>
        '''
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        filter_config = FilterConfig(
            filename_exclude=['*draft*']
        )

        # This should process only 2 PDFs (excluding draft)
        result = download_pdfs_from_webpage(
            'https://example.com',
            show_progress=True,  # Enabled but won't show actual bar in test
            filter_config=filter_config
        )

        # download_pdf should only be called for non-draft files
        # Due to filtering happening before download, only 2 calls
        self.assertEqual(mock_download_pdf.call_count, 2)


class TestRobotsTxtWithProgress(unittest.TestCase):
    """Test robots.txt compliance with progress bars."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear the robots.txt cache before each test
        from fetcharoo import fetcharoo
        fetcharoo._robots_cache = {}

    @responses.activate
    def test_robots_and_progress_together(self):
        """Test that robots.txt and progress work together."""
        robots_txt = '''
User-agent: *
Disallow: /private/
'''
        responses.add(responses.GET, 'https://example.com/robots.txt',
                      body=robots_txt, status=200)

        html_content = '''
        <html><body>
            <a href="/public/doc.pdf">Public</a>
            <a href="/private/secret.pdf">Private</a>
        </body></html>
        '''
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        result = find_pdfs_from_webpage(
            'https://example.com',
            respect_robots=True,
            show_progress=True
        )

        # Only public doc should be found (private blocked by robots.txt)
        self.assertEqual(len(result), 1)
        self.assertIn('https://example.com/public/doc.pdf', result)


class TestAllFeaturesCombined(unittest.TestCase):
    """Test all features working together."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear the robots.txt cache before each test
        from fetcharoo import fetcharoo
        fetcharoo._robots_cache = {}

    @responses.activate
    def test_all_features_dry_run(self):
        """Test dry_run with all other features combined."""
        robots_txt = 'User-agent: *\nAllow: /'
        responses.add(responses.GET, 'https://example.com/robots.txt',
                      body=robots_txt, status=200)

        html_content = '''
        <html><body>
            <a href="report_2023.pdf">Report 2023</a>
            <a href="draft.pdf">Draft</a>
            <a href="annual.pdf">Annual</a>
        </body></html>
        '''
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        filter_config = FilterConfig(
            filename_include=['*report*', '*annual*'],
            filename_exclude=['*draft*']
        )

        result = download_pdfs_from_webpage(
            'https://example.com',
            respect_robots=True,
            user_agent='TestBot/1.0',
            dry_run=True,
            show_progress=True,
            filter_config=filter_config
        )

        # Should find report_2023.pdf and annual.pdf
        self.assertEqual(result['count'], 2)
        self.assertIn('https://example.com/report_2023.pdf', result['urls'])
        self.assertIn('https://example.com/annual.pdf', result['urls'])
        self.assertNotIn('https://example.com/draft.pdf', result['urls'])

    @responses.activate
    @patch('fetcharoo.fetcharoo.download_pdf')
    @patch('fetcharoo.fetcharoo.save_pdf_to_file')
    @patch('fetcharoo.fetcharoo.pymupdf.Document')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_all_features_actual_download(
        self, mock_exists, mock_makedirs, mock_document,
        mock_save_pdf, mock_download_pdf
    ):
        """Test actual download with all features."""
        mock_exists.return_value = False
        mock_download_pdf.return_value = b'%PDF-1.4 test content'
        mock_document.return_value = MagicMock()

        robots_txt = 'User-agent: *\nAllow: /'
        responses.add(responses.GET, 'https://example.com/robots.txt',
                      body=robots_txt, status=200)

        html_content = '''
        <html><body>
            <a href="report.pdf">Report</a>
            <a href="temp.pdf">Temp</a>
        </body></html>
        '''
        responses.add(responses.GET, 'https://example.com', body=html_content, status=200)

        filter_config = FilterConfig(
            filename_exclude=['*temp*']
        )

        result = download_pdfs_from_webpage(
            'https://example.com',
            respect_robots=True,
            user_agent='TestBot/1.0',
            show_progress=True,
            filter_config=filter_config
        )

        self.assertTrue(result)
        # Only report.pdf should be downloaded
        self.assertEqual(mock_download_pdf.call_count, 1)


class TestCLIWithAllOptions(unittest.TestCase):
    """Test CLI with multiple options combined."""

    @patch('fetcharoo.cli.download_pdfs_from_webpage')
    @patch('fetcharoo.cli.set_default_user_agent')
    def test_cli_all_options(self, mock_set_ua, mock_download):
        """Test CLI with all options specified."""
        from fetcharoo.cli import main

        mock_download.return_value = True

        exit_code = main([
            'https://example.com',
            '-o', 'my_output',
            '-d', '2',
            '-m',
            '--delay', '1.0',
            '--timeout', '60',
            '--user-agent', 'MyCLI/1.0',
            '--respect-robots',
            '--progress',
            '--include', 'report*.pdf',
            '--exclude', '*draft*',
            '--min-size', '1000',
            '--max-size', '1000000'
        ])

        self.assertEqual(exit_code, 0)
        mock_set_ua.assert_called_once_with('MyCLI/1.0')
        mock_download.assert_called_once()

        # Verify all arguments were passed
        call_kwargs = mock_download.call_args[1]
        self.assertEqual(call_kwargs['recursion_depth'], 2)
        self.assertEqual(call_kwargs['mode'], 'merge')
        self.assertEqual(call_kwargs['write_dir'], 'my_output')
        self.assertEqual(call_kwargs['request_delay'], 1.0)
        self.assertEqual(call_kwargs['timeout'], 60)
        self.assertTrue(call_kwargs['respect_robots'])
        self.assertTrue(call_kwargs['show_progress'])

        # Verify filter config
        filter_config = call_kwargs['filter_config']
        self.assertIsNotNone(filter_config)
        self.assertEqual(filter_config.filename_include, ['report*.pdf'])
        self.assertEqual(filter_config.filename_exclude, ['*draft*'])
        self.assertEqual(filter_config.min_size, 1000)
        self.assertEqual(filter_config.max_size, 1000000)


if __name__ == '__main__':
    unittest.main()
