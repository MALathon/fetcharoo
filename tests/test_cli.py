import unittest
import sys
from unittest.mock import patch, MagicMock
from io import StringIO
import argparse


class TestCLI(unittest.TestCase):
    """Test suite for the fetcharoo CLI interface."""

    def setUp(self):
        """Import the CLI module for each test."""
        # Import here to ensure fresh module state
        from fetcharoo import cli
        self.cli = cli

    def test_cli_parse_url_argument(self):
        """Test that CLI correctly parses URL as positional argument."""
        test_args = ['fetcharoo', 'https://example.com']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify the URL was passed to download function
                mock_download.assert_called_once()
                args, kwargs = mock_download.call_args
                self.assertEqual(args[0], 'https://example.com')

    def test_cli_output_option_short(self):
        """Test that CLI correctly handles -o output option."""
        test_args = ['fetcharoo', 'https://example.com', '-o', 'custom_output']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify the output directory was passed
                args, kwargs = mock_download.call_args
                self.assertEqual(kwargs.get('write_dir'), 'custom_output')

    def test_cli_output_option_long(self):
        """Test that CLI correctly handles --output option."""
        test_args = ['fetcharoo', 'https://example.com', '--output', 'my_pdfs']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify the output directory was passed
                args, kwargs = mock_download.call_args
                self.assertEqual(kwargs.get('write_dir'), 'my_pdfs')

    def test_cli_depth_option_short(self):
        """Test that CLI correctly handles -d depth option."""
        test_args = ['fetcharoo', 'https://example.com', '-d', '2']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify the recursion depth was passed
                args, kwargs = mock_download.call_args
                self.assertEqual(kwargs.get('recursion_depth'), 2)

    def test_cli_depth_option_long(self):
        """Test that CLI correctly handles --depth option."""
        test_args = ['fetcharoo', 'https://example.com', '--depth', '3']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify the recursion depth was passed
                args, kwargs = mock_download.call_args
                self.assertEqual(kwargs.get('recursion_depth'), 3)

    def test_cli_merge_flag_short(self):
        """Test that CLI correctly handles -m merge flag."""
        test_args = ['fetcharoo', 'https://example.com', '-m']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify the mode was set to 'merge'
                args, kwargs = mock_download.call_args
                self.assertEqual(kwargs.get('mode'), 'merge')

    def test_cli_merge_flag_long(self):
        """Test that CLI correctly handles --merge flag."""
        test_args = ['fetcharoo', 'https://example.com', '--merge']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify the mode was set to 'merge'
                args, kwargs = mock_download.call_args
                self.assertEqual(kwargs.get('mode'), 'merge')

    def test_cli_dry_run_flag(self):
        """Test that CLI correctly handles --dry-run flag."""
        test_args = ['fetcharoo', 'https://example.com', '--dry-run']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.find_pdfs_from_webpage') as mock_find:
                mock_find.return_value = ['https://example.com/file1.pdf', 'https://example.com/file2.pdf']
                with patch('sys.stdout', new=StringIO()) as fake_out:
                    self.cli.main()
                    output = fake_out.getvalue()
                    # Verify that PDFs were listed but not downloaded
                    self.assertIn('file1.pdf', output)
                    self.assertIn('file2.pdf', output)

    def test_cli_delay_option(self):
        """Test that CLI correctly handles --delay option."""
        test_args = ['fetcharoo', 'https://example.com', '--delay', '1.5']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify the request delay was passed
                args, kwargs = mock_download.call_args
                self.assertEqual(kwargs.get('request_delay'), 1.5)

    def test_cli_timeout_option(self):
        """Test that CLI correctly handles --timeout option."""
        test_args = ['fetcharoo', 'https://example.com', '--timeout', '60']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify the timeout was passed
                args, kwargs = mock_download.call_args
                self.assertEqual(kwargs.get('timeout'), 60)

    def test_cli_user_agent_option(self):
        """Test that CLI correctly handles --user-agent option."""
        test_args = ['fetcharoo', 'https://example.com', '--user-agent', 'CustomBot/1.0']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                with patch('fetcharoo.cli.set_default_user_agent') as mock_set_ua:
                    mock_download.return_value = True
                    self.cli.main()
                    # Verify set_default_user_agent was called with the custom agent
                    mock_set_ua.assert_called_once_with('CustomBot/1.0')
                    mock_download.assert_called_once()

    def test_cli_respect_robots_flag(self):
        """Test that CLI correctly handles --respect-robots flag."""
        test_args = ['fetcharoo', 'https://example.com', '--respect-robots']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Just verify it runs without error
                mock_download.assert_called_once()

    def test_cli_help_message(self):
        """Test that CLI shows help message with -h option."""
        test_args = ['fetcharoo', '-h']
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                self.cli.main()
            # argparse exits with 0 for help
            self.assertEqual(cm.exception.code, 0)

    def test_cli_default_values(self):
        """Test that CLI uses correct default values."""
        test_args = ['fetcharoo', 'https://example.com']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify defaults
                args, kwargs = mock_download.call_args
                self.assertEqual(kwargs.get('write_dir'), 'output')
                self.assertEqual(kwargs.get('recursion_depth'), 0)
                self.assertEqual(kwargs.get('mode'), 'separate')
                self.assertEqual(kwargs.get('request_delay'), 0.5)
                self.assertEqual(kwargs.get('timeout'), 30)

    def test_cli_combined_options(self):
        """Test that CLI correctly handles multiple options together."""
        test_args = [
            'fetcharoo', 'https://example.com',
            '-o', 'pdfs',
            '-d', '2',
            '-m',
            '--delay', '1.0',
            '--timeout', '45'
        ]
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.download_pdfs_from_webpage') as mock_download:
                mock_download.return_value = True
                self.cli.main()
                # Verify all options were passed correctly
                args, kwargs = mock_download.call_args
                self.assertEqual(args[0], 'https://example.com')
                self.assertEqual(kwargs.get('write_dir'), 'pdfs')
                self.assertEqual(kwargs.get('recursion_depth'), 2)
                self.assertEqual(kwargs.get('mode'), 'merge')
                self.assertEqual(kwargs.get('request_delay'), 1.0)
                self.assertEqual(kwargs.get('timeout'), 45)

    def test_cli_missing_url_argument(self):
        """Test that CLI exits with error when URL is missing."""
        test_args = ['fetcharoo']
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                self.cli.main()
            # argparse exits with 2 for missing required arguments
            self.assertEqual(cm.exception.code, 2)

    def test_cli_invalid_depth_value(self):
        """Test that CLI rejects invalid depth values."""
        test_args = ['fetcharoo', 'https://example.com', '-d', 'invalid']
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                self.cli.main()
            # argparse exits with 2 for invalid argument values
            self.assertEqual(cm.exception.code, 2)

    def test_cli_dry_run_no_pdfs_found(self):
        """Test that CLI handles dry-run when no PDFs are found."""
        test_args = ['fetcharoo', 'https://example.com', '--dry-run']
        with patch.object(sys, 'argv', test_args):
            with patch('fetcharoo.cli.find_pdfs_from_webpage') as mock_find:
                mock_find.return_value = []
                with patch('sys.stdout', new=StringIO()) as fake_out:
                    self.cli.main()
                    output = fake_out.getvalue()
                    # Verify that appropriate message is shown
                    self.assertIn('No PDFs found', output)


if __name__ == '__main__':
    unittest.main()
