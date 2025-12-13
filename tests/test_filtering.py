"""
Tests for PDF filtering functionality.

This module tests the filtering capabilities for PDFs including:
- Filename pattern matching (include/exclude)
- File size filtering (min/max)
- URL pattern filtering
- Combined filter logic

Author: Mark A. Lifson, Ph.D.
"""

import unittest
from dataclasses import dataclass
from typing import Optional, List
from fetcharoo.filtering import (
    FilterConfig,
    matches_filename_pattern,
    matches_size_limits,
    matches_url_pattern,
    apply_filters,
    should_download_pdf
)


class TestFilenamePatternMatching(unittest.TestCase):
    """Test filename pattern matching with include/exclude patterns."""

    def test_matches_simple_pattern(self):
        """Test simple wildcard pattern matching."""
        self.assertTrue(matches_filename_pattern('report.pdf', ['*.pdf'], []))
        self.assertTrue(matches_filename_pattern('report.pdf', ['report*.pdf'], []))
        self.assertTrue(matches_filename_pattern('report_2023.pdf', ['report*.pdf'], []))

    def test_matches_multiple_include_patterns(self):
        """Test matching against multiple include patterns."""
        patterns = ['report*.pdf', 'summary*.pdf', 'annual*.pdf']
        self.assertTrue(matches_filename_pattern('report_q1.pdf', patterns, []))
        self.assertTrue(matches_filename_pattern('summary_final.pdf', patterns, []))
        self.assertTrue(matches_filename_pattern('annual_2023.pdf', patterns, []))
        self.assertFalse(matches_filename_pattern('other_document.pdf', patterns, []))

    def test_exclude_pattern_overrides_include(self):
        """Test that exclude patterns override include patterns."""
        include_patterns = ['*.pdf']
        exclude_patterns = ['*draft*', '*temp*']

        self.assertTrue(matches_filename_pattern('final_report.pdf', include_patterns, exclude_patterns))
        self.assertFalse(matches_filename_pattern('draft_report.pdf', include_patterns, exclude_patterns))
        self.assertFalse(matches_filename_pattern('temp_file.pdf', include_patterns, exclude_patterns))
        self.assertFalse(matches_filename_pattern('report_draft.pdf', include_patterns, exclude_patterns))

    def test_no_patterns_matches_all(self):
        """Test that empty pattern lists match all filenames."""
        self.assertTrue(matches_filename_pattern('any_file.pdf', [], []))
        self.assertTrue(matches_filename_pattern('another_file.pdf', [], []))

    def test_case_insensitive_matching(self):
        """Test case-insensitive pattern matching."""
        self.assertTrue(matches_filename_pattern('REPORT.PDF', ['report*.pdf'], []))
        self.assertTrue(matches_filename_pattern('Report.PDF', ['report*.pdf'], []))
        self.assertFalse(matches_filename_pattern('DRAFT.PDF', ['report*.pdf'], ['*draft*']))

    def test_complex_patterns(self):
        """Test complex filename patterns."""
        # Question mark matches single character
        self.assertTrue(matches_filename_pattern('report1.pdf', ['report?.pdf'], []))
        self.assertFalse(matches_filename_pattern('report12.pdf', ['report?.pdf'], []))

        # Character sets
        self.assertTrue(matches_filename_pattern('reportA.pdf', ['report[A-Z].pdf'], []))
        self.assertFalse(matches_filename_pattern('reporta.pdf', ['report[A-Z].pdf'], []))


class TestSizeLimitFiltering(unittest.TestCase):
    """Test file size filtering with min/max limits."""

    def test_within_size_limits(self):
        """Test files within size limits are accepted."""
        self.assertTrue(matches_size_limits(5000, min_size=1000, max_size=10000))
        self.assertTrue(matches_size_limits(1000, min_size=1000, max_size=10000))  # At min
        self.assertTrue(matches_size_limits(10000, min_size=1000, max_size=10000))  # At max

    def test_below_min_size(self):
        """Test files below minimum size are rejected."""
        self.assertFalse(matches_size_limits(500, min_size=1000, max_size=10000))
        self.assertFalse(matches_size_limits(0, min_size=1000, max_size=10000))

    def test_above_max_size(self):
        """Test files above maximum size are rejected."""
        self.assertFalse(matches_size_limits(15000, min_size=1000, max_size=10000))
        self.assertFalse(matches_size_limits(100000, min_size=1000, max_size=10000))

    def test_only_min_size(self):
        """Test filtering with only minimum size specified."""
        self.assertTrue(matches_size_limits(5000, min_size=1000, max_size=None))
        self.assertTrue(matches_size_limits(100000, min_size=1000, max_size=None))
        self.assertFalse(matches_size_limits(500, min_size=1000, max_size=None))

    def test_only_max_size(self):
        """Test filtering with only maximum size specified."""
        self.assertTrue(matches_size_limits(5000, min_size=None, max_size=10000))
        self.assertTrue(matches_size_limits(100, min_size=None, max_size=10000))
        self.assertFalse(matches_size_limits(15000, min_size=None, max_size=10000))

    def test_no_size_limits(self):
        """Test that no size limits accept all file sizes."""
        self.assertTrue(matches_size_limits(0, min_size=None, max_size=None))
        self.assertTrue(matches_size_limits(5000, min_size=None, max_size=None))
        self.assertTrue(matches_size_limits(10000000, min_size=None, max_size=None))

    def test_negative_size(self):
        """Test that negative sizes are rejected."""
        self.assertFalse(matches_size_limits(-100, min_size=None, max_size=None))
        self.assertFalse(matches_size_limits(-1, min_size=0, max_size=10000))


class TestURLPatternMatching(unittest.TestCase):
    """Test URL pattern matching with include/exclude patterns."""

    def test_matches_url_pattern(self):
        """Test basic URL pattern matching."""
        self.assertTrue(matches_url_pattern(
            'https://example.com/reports/annual.pdf',
            ['*/reports/*'],
            []
        ))
        self.assertTrue(matches_url_pattern(
            'https://example.com/2023/report.pdf',
            ['*/2023/*'],
            []
        ))

    def test_multiple_url_include_patterns(self):
        """Test matching against multiple URL include patterns."""
        patterns = ['*/reports/*', '*/documents/*', '*/archives/*']
        self.assertTrue(matches_url_pattern('https://example.com/reports/file.pdf', patterns, []))
        self.assertTrue(matches_url_pattern('https://example.com/documents/file.pdf', patterns, []))
        self.assertTrue(matches_url_pattern('https://example.com/archives/file.pdf', patterns, []))
        self.assertFalse(matches_url_pattern('https://example.com/other/file.pdf', patterns, []))

    def test_url_exclude_pattern(self):
        """Test URL exclude patterns."""
        include_patterns = ['*example.com*']
        exclude_patterns = ['*/drafts/*', '*/temp/*']

        self.assertTrue(matches_url_pattern(
            'https://example.com/final/report.pdf',
            include_patterns,
            exclude_patterns
        ))
        self.assertFalse(matches_url_pattern(
            'https://example.com/drafts/report.pdf',
            include_patterns,
            exclude_patterns
        ))
        self.assertFalse(matches_url_pattern(
            'https://example.com/temp/report.pdf',
            include_patterns,
            exclude_patterns
        ))

    def test_domain_filtering_via_url_pattern(self):
        """Test filtering by domain using URL patterns."""
        patterns = ['https://trusted.com/*', 'https://verified.org/*']
        self.assertTrue(matches_url_pattern('https://trusted.com/file.pdf', patterns, []))
        self.assertTrue(matches_url_pattern('https://verified.org/file.pdf', patterns, []))
        self.assertFalse(matches_url_pattern('https://untrusted.com/file.pdf', patterns, []))

    def test_no_url_patterns_matches_all(self):
        """Test that empty URL pattern lists match all URLs."""
        self.assertTrue(matches_url_pattern('https://example.com/file.pdf', [], []))
        self.assertTrue(matches_url_pattern('https://any-domain.com/path/file.pdf', [], []))


class TestFilterConfig(unittest.TestCase):
    """Test FilterConfig dataclass."""

    def test_filter_config_creation(self):
        """Test creating FilterConfig with various options."""
        config = FilterConfig(
            filename_include=['*.pdf'],
            filename_exclude=['*draft*'],
            min_size=1000,
            max_size=10000,
            url_include=['*/reports/*'],
            url_exclude=['*/temp/*']
        )

        self.assertEqual(config.filename_include, ['*.pdf'])
        self.assertEqual(config.filename_exclude, ['*draft*'])
        self.assertEqual(config.min_size, 1000)
        self.assertEqual(config.max_size, 10000)
        self.assertEqual(config.url_include, ['*/reports/*'])
        self.assertEqual(config.url_exclude, ['*/temp/*'])

    def test_filter_config_defaults(self):
        """Test FilterConfig default values."""
        config = FilterConfig()

        self.assertEqual(config.filename_include, [])
        self.assertEqual(config.filename_exclude, [])
        self.assertIsNone(config.min_size)
        self.assertIsNone(config.max_size)
        self.assertEqual(config.url_include, [])
        self.assertEqual(config.url_exclude, [])


class TestApplyFilters(unittest.TestCase):
    """Test the main apply_filters function that combines all filter logic."""

    def test_apply_all_filters_pass(self):
        """Test when PDF passes all filters."""
        config = FilterConfig(
            filename_include=['report*.pdf'],
            filename_exclude=['*draft*'],
            min_size=1000,
            max_size=100000,
            url_include=['*/documents/*'],
            url_exclude=['*/temp/*']
        )

        result = apply_filters(
            pdf_url='https://example.com/documents/report_2023.pdf',
            size_bytes=5000,
            filter_config=config
        )
        self.assertTrue(result)

    def test_apply_filters_filename_fail(self):
        """Test when PDF fails filename filter."""
        config = FilterConfig(
            filename_include=['report*.pdf'],
            filename_exclude=['*draft*']
        )

        result = apply_filters(
            pdf_url='https://example.com/documents/summary.pdf',
            size_bytes=5000,
            filter_config=config
        )
        self.assertFalse(result)

    def test_apply_filters_size_fail(self):
        """Test when PDF fails size filter."""
        config = FilterConfig(
            min_size=10000,
            max_size=100000
        )

        result = apply_filters(
            pdf_url='https://example.com/documents/report.pdf',
            size_bytes=5000,  # Too small
            filter_config=config
        )
        self.assertFalse(result)

    def test_apply_filters_url_fail(self):
        """Test when PDF fails URL filter."""
        config = FilterConfig(
            url_include=['*/approved/*'],
            url_exclude=['*/temp/*']
        )

        result = apply_filters(
            pdf_url='https://example.com/temp/report.pdf',
            size_bytes=5000,
            filter_config=config
        )
        self.assertFalse(result)

    def test_apply_filters_no_config(self):
        """Test that None config passes all PDFs."""
        result = apply_filters(
            pdf_url='https://example.com/any/file.pdf',
            size_bytes=5000,
            filter_config=None
        )
        self.assertTrue(result)

    def test_apply_filters_empty_config(self):
        """Test that empty config passes all PDFs."""
        config = FilterConfig()

        result = apply_filters(
            pdf_url='https://example.com/any/file.pdf',
            size_bytes=5000,
            filter_config=config
        )
        self.assertTrue(result)

    def test_apply_filters_exclude_overrides(self):
        """Test that exclude patterns override include patterns."""
        config = FilterConfig(
            filename_include=['*.pdf'],
            filename_exclude=['*draft*'],
            url_include=['*example.com*'],
            url_exclude=['*/temp/*']
        )

        # Should fail on filename exclude
        self.assertFalse(apply_filters(
            'https://example.com/final/draft_report.pdf',
            5000,
            config
        ))

        # Should fail on URL exclude
        self.assertFalse(apply_filters(
            'https://example.com/temp/report.pdf',
            5000,
            config
        ))

    def test_apply_filters_size_none_when_no_size_available(self):
        """Test filtering when size is None (size not available)."""
        config = FilterConfig(
            min_size=1000,
            max_size=100000
        )

        # When size is None, size filters should be skipped
        result = apply_filters(
            pdf_url='https://example.com/report.pdf',
            size_bytes=None,
            filter_config=config
        )
        self.assertTrue(result)


class TestShouldDownloadPDF(unittest.TestCase):
    """Test the should_download_pdf convenience function."""

    def test_should_download_with_metadata(self):
        """Test should_download_pdf with size metadata."""
        config = FilterConfig(
            filename_include=['report*.pdf'],
            min_size=1000,
            max_size=100000
        )

        # Should pass all filters
        self.assertTrue(should_download_pdf(
            pdf_url='https://example.com/report_2023.pdf',
            size_bytes=5000,
            filter_config=config
        ))

        # Should fail size filter
        self.assertFalse(should_download_pdf(
            pdf_url='https://example.com/report_2023.pdf',
            size_bytes=500,  # Too small
            filter_config=config
        ))

    def test_should_download_without_size(self):
        """Test should_download_pdf when size is not available."""
        config = FilterConfig(
            filename_include=['report*.pdf'],
            url_include=['*/documents/*']
        )

        # Should pass filename and URL filters (size is None)
        self.assertTrue(should_download_pdf(
            pdf_url='https://example.com/documents/report_2023.pdf',
            size_bytes=None,
            filter_config=config
        ))

    def test_should_download_no_config(self):
        """Test should_download_pdf with no filter config."""
        self.assertTrue(should_download_pdf(
            pdf_url='https://example.com/any_file.pdf',
            size_bytes=5000,
            filter_config=None
        ))


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_filename(self):
        """Test filtering with empty filename."""
        self.assertTrue(matches_filename_pattern('', [], []))
        self.assertFalse(matches_filename_pattern('', ['*.pdf'], []))

    def test_special_characters_in_filename(self):
        """Test filtering with special characters in filenames."""
        self.assertTrue(matches_filename_pattern(
            'report-2023_final[v2].pdf',
            ['report-*.pdf'],
            []
        ))

    def test_url_with_query_parameters(self):
        """Test URL filtering with query parameters."""
        url = 'https://example.com/documents/report.pdf?download=true&token=abc123'
        self.assertTrue(matches_url_pattern(url, ['*/documents/*'], []))

    def test_url_with_fragments(self):
        """Test URL filtering with fragments."""
        url = 'https://example.com/documents/report.pdf#page=5'
        self.assertTrue(matches_url_pattern(url, ['*/documents/*'], []))

    def test_very_large_file_size(self):
        """Test filtering with very large file sizes."""
        # 1GB file
        self.assertTrue(matches_size_limits(1_000_000_000, min_size=None, max_size=None))
        self.assertFalse(matches_size_limits(1_000_000_000, min_size=None, max_size=10_000_000))

    def test_zero_file_size(self):
        """Test filtering with zero file size."""
        self.assertTrue(matches_size_limits(0, min_size=None, max_size=None))
        self.assertTrue(matches_size_limits(0, min_size=0, max_size=1000))
        self.assertFalse(matches_size_limits(0, min_size=1, max_size=1000))


class TestRealWorldScenarios(unittest.TestCase):
    """Test real-world filtering scenarios."""

    def test_annual_reports_only(self):
        """Test filtering to download only annual reports."""
        config = FilterConfig(
            filename_include=['*annual*report*.pdf', '*yearly*report*.pdf'],
            filename_exclude=['*draft*', '*preliminary*'],
            min_size=50000  # Assume annual reports are at least 50KB
        )

        # Should pass
        self.assertTrue(apply_filters(
            'https://company.com/docs/annual_report_2023.pdf',
            75000,
            config
        ))

        # Should fail - draft
        self.assertFalse(apply_filters(
            'https://company.com/docs/annual_report_2023_draft.pdf',
            75000,
            config
        ))

        # Should fail - too small
        self.assertFalse(apply_filters(
            'https://company.com/docs/annual_report_2023.pdf',
            30000,
            config
        ))

    def test_specific_domain_and_path(self):
        """Test filtering PDFs from specific domain and path."""
        config = FilterConfig(
            url_include=['https://trusted-source.org/publications/*'],
            url_exclude=['*/drafts/*', '*/archive/*'],
            max_size=10_000_000  # Max 10MB
        )

        # Should pass
        self.assertTrue(apply_filters(
            'https://trusted-source.org/publications/2023/report.pdf',
            5_000_000,
            config
        ))

        # Should fail - wrong domain
        self.assertFalse(apply_filters(
            'https://untrusted.com/publications/2023/report.pdf',
            5_000_000,
            config
        ))

        # Should fail - in drafts
        self.assertFalse(apply_filters(
            'https://trusted-source.org/publications/drafts/report.pdf',
            5_000_000,
            config
        ))

    def test_size_range_for_specific_type(self):
        """Test filtering PDFs within specific size range."""
        # Looking for presentation PDFs (typically 1-5 MB)
        config = FilterConfig(
            filename_include=['*presentation*.pdf', '*slides*.pdf'],
            min_size=1_000_000,  # 1MB
            max_size=5_000_000   # 5MB
        )

        # Should pass
        self.assertTrue(apply_filters(
            'https://example.com/presentation_q4.pdf',
            2_500_000,
            config
        ))

        # Should fail - too small (likely incomplete)
        self.assertFalse(apply_filters(
            'https://example.com/presentation_q4.pdf',
            500_000,
            config
        ))

        # Should fail - too large
        self.assertFalse(apply_filters(
            'https://example.com/presentation_q4.pdf',
            6_000_000,
            config
        ))


if __name__ == '__main__':
    unittest.main()
