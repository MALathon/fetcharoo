import unittest
from unittest.mock import patch, MagicMock
import responses
from urllib.robotparser import RobotFileParser
from fetcharoo.fetcharoo import check_robots_txt, find_pdfs_from_webpage


class TestRobotsTxt(unittest.TestCase):
    """Test robots.txt compliance functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear the robots.txt cache before each test
        from fetcharoo import fetcharoo
        fetcharoo._robots_cache = {}

    @responses.activate
    def test_robots_txt_allows_crawling(self):
        """Test that check_robots_txt returns True when crawling is allowed."""
        # Mock robots.txt that allows all user agents
        robots_content = """
User-agent: *
Disallow:
"""
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=robots_content,
            status=200,
            content_type='text/plain',
        )

        # Test that crawling is allowed
        result = check_robots_txt('https://example.com/test.pdf', 'fetcharoo-bot')
        self.assertTrue(result)

    @responses.activate
    def test_robots_txt_disallows_crawling(self):
        """Test that check_robots_txt returns False when crawling is disallowed."""
        # Mock robots.txt that disallows all
        robots_content = """
User-agent: *
Disallow: /
"""
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=robots_content,
            status=200,
            content_type='text/plain',
        )

        # Test that crawling is disallowed
        result = check_robots_txt('https://example.com/test.pdf', 'fetcharoo-bot')
        self.assertFalse(result)

    @responses.activate
    def test_robots_txt_disallows_specific_path(self):
        """Test that check_robots_txt respects path-specific rules."""
        # Mock robots.txt that disallows specific paths
        robots_content = """
User-agent: *
Disallow: /private/
Allow: /
"""
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=robots_content,
            status=200,
            content_type='text/plain',
        )

        # Test that public path is allowed
        result_public = check_robots_txt('https://example.com/public/test.pdf', 'fetcharoo-bot')
        self.assertTrue(result_public)

        # Test that private path is disallowed
        result_private = check_robots_txt('https://example.com/private/test.pdf', 'fetcharoo-bot')
        self.assertFalse(result_private)

    @responses.activate
    def test_robots_txt_user_agent_specific(self):
        """Test that check_robots_txt respects user-agent specific rules."""
        # Mock robots.txt with user-agent specific rules
        robots_content = """
User-agent: badbot
Disallow: /

User-agent: *
Allow: /
"""
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=robots_content,
            status=200,
            content_type='text/plain',
        )

        # Test that badbot is disallowed
        result_badbot = check_robots_txt('https://example.com/test.pdf', 'badbot')
        self.assertFalse(result_badbot)

        # Test that other bots are allowed
        result_goodbot = check_robots_txt('https://example.com/test.pdf', 'fetcharoo-bot')
        self.assertTrue(result_goodbot)

    @responses.activate
    def test_missing_robots_txt(self):
        """Test that missing robots.txt allows crawling by default."""
        # Mock 404 response for robots.txt
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            status=404,
        )

        # Test that crawling is allowed when robots.txt is missing
        result = check_robots_txt('https://example.com/test.pdf', 'fetcharoo-bot')
        self.assertTrue(result)

    @responses.activate
    def test_robots_txt_network_error(self):
        """Test that network errors default to allowing crawling."""
        # Mock a connection error
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=Exception("Connection error"),
        )

        # Test that crawling is allowed when there's a network error
        result = check_robots_txt('https://example.com/test.pdf', 'fetcharoo-bot')
        self.assertTrue(result)

    @responses.activate
    def test_robots_txt_caching(self):
        """Test that robots.txt is cached per domain to avoid repeated fetches."""
        # Mock robots.txt
        robots_content = """
User-agent: *
Disallow: /private/
"""
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=robots_content,
            status=200,
            content_type='text/plain',
        )

        # First call - should fetch robots.txt
        result1 = check_robots_txt('https://example.com/test1.pdf', 'fetcharoo-bot')
        self.assertTrue(result1)

        # Second call - should use cached robots.txt (only one request should be made)
        result2 = check_robots_txt('https://example.com/test2.pdf', 'fetcharoo-bot')
        self.assertTrue(result2)

        # Verify only one request was made to robots.txt
        robots_requests = [call for call in responses.calls if 'robots.txt' in call.request.url]
        self.assertEqual(len(robots_requests), 1)

    @responses.activate
    def test_robots_txt_different_domains_separate_cache(self):
        """Test that different domains have separate cache entries."""
        # Mock robots.txt for example.com
        robots_content_example = """
User-agent: *
Disallow: /private/
"""
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=robots_content_example,
            status=200,
            content_type='text/plain',
        )

        # Mock robots.txt for another.com
        robots_content_another = """
User-agent: *
Disallow: /
"""
        responses.add(
            responses.GET,
            'https://another.com/robots.txt',
            body=robots_content_another,
            status=200,
            content_type='text/plain',
        )

        # Check example.com
        result_example = check_robots_txt('https://example.com/test.pdf', 'fetcharoo-bot')
        self.assertTrue(result_example)

        # Check another.com
        result_another = check_robots_txt('https://another.com/test.pdf', 'fetcharoo-bot')
        self.assertFalse(result_another)

        # Verify two separate requests were made
        robots_requests = [call for call in responses.calls if 'robots.txt' in call.request.url]
        self.assertEqual(len(robots_requests), 2)

    @responses.activate
    def test_find_pdfs_with_robots_respect(self):
        """Test integration of robots.txt checking with find_pdfs_from_webpage."""
        # Mock robots.txt that disallows /private/
        robots_content = """
User-agent: *
Disallow: /private/
"""
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=robots_content,
            status=200,
            content_type='text/plain',
        )

        # Mock HTML content with both public and private PDFs
        html_content = """
        <html>
            <body>
                <a href="https://example.com/public/test1.pdf">Public PDF</a>
                <a href="https://example.com/private/test2.pdf">Private PDF</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            'https://example.com',
            body=html_content,
            status=200,
            content_type='text/html',
        )

        # Test with respect_robots=True
        pdf_links = find_pdfs_from_webpage(
            url='https://example.com',
            recursion_depth=0,
            respect_robots=True
        )

        # Should only include the public PDF
        self.assertEqual(len(pdf_links), 1)
        self.assertIn('https://example.com/public/test1.pdf', pdf_links)
        self.assertNotIn('https://example.com/private/test2.pdf', pdf_links)

    @responses.activate
    def test_find_pdfs_without_robots_respect(self):
        """Test that respect_robots=False includes all PDFs."""
        # Mock robots.txt that disallows /private/
        robots_content = """
User-agent: *
Disallow: /private/
"""
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=robots_content,
            status=200,
            content_type='text/plain',
        )

        # Mock HTML content with both public and private PDFs
        html_content = """
        <html>
            <body>
                <a href="https://example.com/public/test1.pdf">Public PDF</a>
                <a href="https://example.com/private/test2.pdf">Private PDF</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            'https://example.com',
            body=html_content,
            status=200,
            content_type='text/html',
        )

        # Test with respect_robots=False (default)
        pdf_links = find_pdfs_from_webpage(
            url='https://example.com',
            recursion_depth=0,
            respect_robots=False
        )

        # Should include both PDFs
        self.assertEqual(len(pdf_links), 2)
        self.assertIn('https://example.com/public/test1.pdf', pdf_links)
        self.assertIn('https://example.com/private/test2.pdf', pdf_links)

    @responses.activate
    @patch('fetcharoo.fetcharoo.logger')
    def test_robots_txt_logging(self, mock_logger):
        """Test that warnings are logged when URLs are skipped due to robots.txt."""
        # Mock robots.txt that disallows all
        robots_content = """
User-agent: *
Disallow: /
"""
        responses.add(
            responses.GET,
            'https://example.com/robots.txt',
            body=robots_content,
            status=200,
            content_type='text/plain',
        )

        # Mock HTML content with PDFs
        html_content = """
        <html>
            <body>
                <a href="https://example.com/test.pdf">Test PDF</a>
            </body>
        </html>
        """
        responses.add(
            responses.GET,
            'https://example.com',
            body=html_content,
            status=200,
            content_type='text/html',
        )

        # Test with respect_robots=True
        pdf_links = find_pdfs_from_webpage(
            url='https://example.com',
            recursion_depth=0,
            respect_robots=True
        )

        # Verify warning was logged
        mock_logger.warning.assert_called()
        # Check that the warning message contains information about robots.txt
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        robots_warning_found = any('robots.txt' in str(call).lower() for call in warning_calls)
        self.assertTrue(robots_warning_found)


if __name__ == '__main__':
    unittest.main()
